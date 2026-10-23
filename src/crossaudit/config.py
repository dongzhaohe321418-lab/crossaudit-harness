"""`crossaudit.yml`: the one configuration file, schema-validated on load.

Credentials never appear here. The file names the *environment variable* that
carries a key; the value is read at call time and never echoed, never logged,
never written into a receipt.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from .errors import ConfigDenial
from .providers.specs import EFFORT_HINTS
from .repair_guard import DEFAULT_MAX_DOCUMENT_GROWTH

CONFIG_NAME = "crossaudit.yml"

#: Isolation dimensions, in the paper's own terms (I1). Recorded as evidence
#: per deployment, and compared against `isolation.minimum` before admission.
ISOLATION_DIMS = ("parametric", "contextual", "permissive")

_ALLOWED_TOP = {"version", "science_repo", "audit_repo", "constitution", "max_rounds",
                "auditor", "generator", "isolation", "state", "ledger", "scope",
                "checks", "plugins", "resilience", "budgets", "authority", "repair",
                "prices"}
#: The four rates a per-project price override declares, USD per 1M tokens.
PRICE_FIELDS = ("input", "output", "cache_write", "cache_read")
_ALLOWED_ROLE = {"provider", "model", "base_url", "key_env", "vendor",
                 "reasoning_effort", "fallbacks"}
_ALLOWED_GENERATOR = _ALLOWED_ROLE | {"streaming"}
#: Valid ``reasoning_effort`` strings for YAML validation, derived from the one
#: provider effort catalogue so this schema and the model cards cannot drift.
#: ``EFFORT_HINTS`` is the single vocabulary of effort levels the system knows:
#: it is a superset of every CapabilityCard's efforts and additionally documents
#: reserved levels (e.g. "ultra") no shipping card emits yet, so validation stays
#: deliberately as wide as the catalogue. Adding a level in specs.EFFORT_HINTS
#: makes it both describable in the UI and acceptable here, in one edit.
_EFFORT_VALUES = frozenset(EFFORT_HINTS)


@dataclass(frozen=True)
class Role:
    provider: str
    model: str
    vendor: str
    key_env: str
    base_url: str | None = None
    reasoning_effort: str | None = None
    fallbacks: tuple["Role", ...] = ()


@dataclass(frozen=True)
class Resilience:
    """Provider-call recovery policy; retries never spend audit rounds."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 20.0
    retry_after_cap_seconds: float = 120.0
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown_seconds: float = 60.0


@dataclass(frozen=True)
class Budgets:
    """Local guardrails. None means visible metering without a limit."""

    daily_token_warning: int | None = None
    daily_token_limit: int | None = None
    monthly_cost_warning_usd: float | None = None
    monthly_cost_limit_usd: float | None = None


@dataclass(frozen=True)
class AuthorityPolicy:
    """How a blocking finding only the model raised is routed (D148).

    ``block`` (default): bounded automatic revision, recorded as unverified.
    ``escalate``: a person decides at round one; no patch is requested for it.
    """

    lone_model_blocker: str = "block"


@dataclass(frozen=True)
class RepairPolicy:
    """The repair screen after a BLOCKED audit (repair_guard).

    ``mode`` says what a likely defensive edit does: ``caution`` (default)
    surfaces it to the auditor; ``refuse`` rolls the round back.

    ``max_document_growth`` bounds how much of itself one automatic revision
    may add to a document deliverable (words, as a fraction of what was
    committed).  Over it the round is rolled back and re-asked in both modes:
    a revision repairs findings, it does not replace the artefact with a
    longer one.  ``0`` (**the default**) turns the screen off;
    ``repair_guard.DEFAULT_MAX_DOCUMENT_GROWTH`` is the value to start from if
    you switch it on.

    **It is off by default because it was measured and it did not help.** On
    ExpertLongBench T03MaterialSEG it bound growth exactly as intended -- no
    revision round over the bound, against 4 of 14 without it -- and the paired
    within-instance revision delta got *worse*, -7.58 F1 against a control's
    -2.14, six of seven paired instances in the wrong direction
    (``benchmarks/expertlongbench/RESULTS-4.md``).  It prevents the rare
    catastrophic rewrite and makes the median revision worse, and on that task
    the second effect is larger.  The knob stays because the first effect is
    real; the default follows the measurement.
    """

    enabled: bool = True
    mode: str = "caution"
    max_changed_lines: int = 200
    max_document_growth: float = 0.0


@dataclass(frozen=True)
class Config:
    path: Path
    science_repo: str
    audit_repo: str | None
    constitution: str
    max_rounds: int
    auditor: Role
    generator_vendor: str | None
    generator_provider: str | None
    generator_model: str | None
    generator_key_env: str | None
    generator_base_url: str | None
    generator_reasoning_effort: str | None
    isolation_minimum: dict
    state_dir: str
    ledger_dir: str
    scope_dirs: list[str] | None
    checks: list[str]
    generator_streaming: bool = True
    plugins: list[str] = field(default_factory=list)
    generator_fallbacks: tuple[Role, ...] = ()
    resilience: Resilience = field(default_factory=Resilience)
    budgets: Budgets = field(default_factory=Budgets)
    authority: AuthorityPolicy = field(default_factory=AuthorityPolicy)
    repair: RepairPolicy = field(default_factory=RepairPolicy)
    #: Per-project price overrides: model id -> {input, output, cache_write,
    #: cache_read} in USD per 1M tokens. Used for models the price snapshot
    #: does not carry (or a relay that bills differently); stamped
    #: ``user_priced`` in the usage ledger so the figure's origin stays visible.
    prices: dict = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.path.parent


#: Names a ``key_env`` may never be: variables every child process needs, or
#: that never hold a key. ``child_env`` strips every configured key name, so
#: accepting one of these would break Git, the shell or Python for that config.
_KEY_ENV_RESERVED = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "PWD", "TMPDIR", "TEMP", "TMP",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "PYTHONPATH", "PYTHONHOME",
    "SSH_AUTH_SOCK", "GIT_DIR", "GIT_WORK_TREE", "SYSTEMROOT", "COMSPEC",
    "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA"})
_KEY_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _role(raw: dict, name: str, where: Path, *, allow_fallbacks: bool = True) -> Role:
    unknown = set(raw) - _ALLOWED_ROLE
    if unknown:
        raise ConfigDenial(f"{name}: unknown keys {sorted(unknown)}", file=str(where))
    for req in ("provider", "model", "vendor", "key_env"):
        if not raw.get(req):
            raise ConfigDenial(f"{name}.{req} is required", file=str(where))
    key_env = raw.get("key_env")
    # Every name declared here is stripped from non-provider children
    # (app_keys.child_env, D176), so a name that is not a key variable at all
    # would take PATH or HOME away from Git. Refuse it here, legibly.
    if (not isinstance(key_env, str) or not _KEY_ENV_NAME.match(key_env)
            or key_env.upper() in _KEY_ENV_RESERVED):
        raise ConfigDenial(
            f"{name}.key_env must name a variable that holds only a key; "
            f"{key_env!r} is not one", file=str(where))
    effort = raw.get("reasoning_effort")
    if effort is not None and effort not in _EFFORT_VALUES:
        raise ConfigDenial(
            f"{name}.reasoning_effort must be one of {sorted(_EFFORT_VALUES)}",
            file=str(where))
    fallback_rows = raw.get("fallbacks") or []
    if not allow_fallbacks and fallback_rows:
        raise ConfigDenial(f"{name}.fallbacks cannot contain nested fallbacks", file=str(where))
    if not isinstance(fallback_rows, list):
        raise ConfigDenial(f"{name}.fallbacks must be a list", file=str(where))
    fallbacks = tuple(_role(item, f"{name}.fallbacks[{i}]", where,
                            allow_fallbacks=False)
                      for i, item in enumerate(fallback_rows)
                      if isinstance(item, dict))
    if len(fallbacks) != len(fallback_rows):
        raise ConfigDenial(f"{name}.fallbacks entries must be mappings", file=str(where))
    return Role(provider=raw["provider"], model=raw["model"], vendor=raw["vendor"],
                key_env=raw["key_env"], base_url=raw.get("base_url"),
                reasoning_effort=effort, fallbacks=fallbacks)


def _register_key_names(auditor: Role, generator_vendor: object,
                        generator_key_env: object,
                        generator_fallbacks: tuple[Role, ...]) -> None:
    """Tell ``app_keys`` every variable name this file says holds a key.

    ``key_env`` accepts any non-empty name, so ``app_keys.child_env()`` cannot
    recognise a configured key by its shape alone. Registering the names here,
    as soon as the roles are parsed (before the rest of the file is validated,
    so a load that is refused later still registers them), means every
    non-provider child launched afterwards in this process is started without
    them, whether or not its caller holds this ``Config``. Covered: the
    ``key_env`` of the auditor, the generator and every fallback row, and the
    backup slot of every vendor named by any of them.
    """
    from . import app_keys
    roles = (auditor, *auditor.fallbacks, *generator_fallbacks)
    vendors = {role.vendor for role in roles}
    if isinstance(generator_vendor, str):
        vendors.add(generator_vendor)
    app_keys.register_key_names(
        *(role.key_env for role in roles), generator_key_env,
        *(app_keys.backup_env_for_vendor(vendor.strip().lower())
          for vendor in vendors if isinstance(vendor, str) and vendor.strip()))


def _number(raw: dict, key: str, default: float, low: float, high: float,
            where: Path) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ConfigDenial(f"{key} must be between {low:g} and {high:g}", file=str(where))
    return float(value)


def _positive_optional(raw: dict, key: str, where: Path, *, integer: bool = False):
    value = raw.get(key)
    if value is None:
        return None
    valid_type = isinstance(value, int) if integer else isinstance(value, (int, float))
    if isinstance(value, bool) or not valid_type or value <= 0:
        raise ConfigDenial(f"budgets.{key} must be a positive number or null", file=str(where))
    return int(value) if integer else float(value)


def _prices(raw: object, where: Path) -> dict:
    """Validate ``prices:`` — model id to four non-negative rates, plus a flag.

    ``trust_origin: true`` is the project saying it knows what a non-vendor
    endpoint (a relay, a gateway) charges. Without it an override prices only
    calls that went to the vendor itself, so a monthly cost *limit* — which
    fails closed the moment anything is unpriced — cannot be reopened by a
    guess about a route CrossAudit cannot see.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigDenial("prices must be a mapping", file=str(where))
    out: dict[str, dict] = {}
    for model, row in raw.items():
        name = str(model).strip()
        if not name or len(name) > 160:
            raise ConfigDenial("prices: model ids must be 1 to 160 characters",
                               file=str(where))
        if not isinstance(row, dict) or set(row) - set(PRICE_FIELDS) - {"trust_origin"}:
            raise ConfigDenial(
                f"prices.{name} must be a mapping of input, output, cache_write, "
                "cache_read, trust_origin",
                file=str(where))
        trust = row.get("trust_origin", False)
        if not isinstance(trust, bool):
            raise ConfigDenial(
                f"prices.{name}.trust_origin must be true or false (it declares that "
                "this project knows what a non-vendor endpoint charges)",
                file=str(where))
        rates = {"trust_origin": trust} if trust else {}
        for key in PRICE_FIELDS:
            value = row.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ConfigDenial(
                    f"prices.{name}.{key} must be a non-negative number (USD per 1M tokens)",
                    file=str(where))
            rates[key] = float(value)
        out[name] = rates
    return out


def find(start: Path | None = None) -> Path:
    """Nearest crossaudit.yml from `start` upward. Absent = denial, not a default."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / CONFIG_NAME).is_file():
            return d / CONFIG_NAME
    # The "and every directory above it" clause is kept deliberately: it is what
    # tells someone standing in a subdirectory why their existing project was
    # not found, and dropping it for brevity would cost a real diagnosis.
    # `reason` is the machine contract — `as_dict()`, `--json` and every script
    # that greps it — so it stays English. `human` is the sentence a person
    # reads and is deliberately kept OUT of `as_dict()`, which is exactly what
    # makes it safe to translate. The seam was already here; wave 2 uses it.
    from .cli.i18n import t
    raise ConfigDenial(
        f"no {CONFIG_NAME} found from {cur} upward — run `crossaudit init`",
        human=(t("refusal.no_project.title") + "\n\n"
               + "    " + t("refusal.no_project.looked",
                            name=CONFIG_NAME, where=cur) + "\n\n"
               + "    " + t("refusal.no_project.fix")))


def load(path: Path | None = None) -> Config:
    p = path or find()
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigDenial(f"{CONFIG_NAME} is not valid YAML: {exc}", file=str(p)) from exc
    if not isinstance(raw, dict):
        raise ConfigDenial(f"{CONFIG_NAME} must be a mapping", file=str(p))

    unknown = set(raw) - _ALLOWED_TOP
    if unknown:
        raise ConfigDenial(f"unknown top-level keys {sorted(unknown)}", file=str(p))
    if raw.get("version") != 1:
        raise ConfigDenial(f"config version {raw.get('version')!r} unsupported (expected 1)",
                           file=str(p))
    for req in ("science_repo", "constitution", "auditor"):
        if not raw.get(req):
            raise ConfigDenial(f"{req} is required", file=str(p))
    # D156. The two roles a markdown file can hold here are exclusive. A skill
    # is the owner's guidance to the GENERATOR and is deliberately kept out of
    # the audited increment; the Constitution is the standard the AUDITOR judges
    # against and is read separately, by commit, whatever the scope says. Point
    # `constitution:` inside the guidance directory and the same bytes are both
    # — the increment filter drops the file and `_committed_constitution` hands
    # it to the auditor as law. That is not an audit boundary anyone can reason
    # about, so it is refused at configuration time rather than qualified in a
    # docstring. Requires deliberate owner configuration; it is refused because
    # it is incoherent, not because it is an attack.
    #
    # NORMALISE FIRST. The first version compared `PurePosixPath(value).parts`
    # raw, which neither folds case nor collapses `..`: `SKILLS/house.md` and
    # `work/../skills/house.md` both walked past it. Neither reached the auditor
    # — the committed-file reader denies them later — but a guard that a
    # different spelling of the same path steps over is not a guard.
    # Case is folded on EVERY host, not only case-insensitive ones: a
    # constitution spelled `SKILLS/...` is never legitimate, and a rule that
    # depends on the developer's filesystem is not a rule.
    from .skills import SKILLS_DIR as _skills_dir
    const_raw = str(raw["constitution"])
    const_norm = posixpath.normpath(const_raw)
    # ABSOLUTE FIRST, before anything reasons about components. `/abs/skills/x`
    # has `/` as its first component, so the guidance comparison below misses it
    # and the traversal check below never looked at it either — an absolute path
    # walked past both. A Constitution is always a path INSIDE the tree, cited
    # by commit; an absolute one names a file on somebody's disk, which no
    # receipt can bind and no verifier can re-read.
    if posixpath.isabs(const_norm) or PureWindowsPath(const_raw).drive:
        raise ConfigDenial(
            f"constitution {const_raw!r} is an absolute path. The Constitution "
            f"is a file committed in this repository and cited by commit, so it "
            f"is written as a path inside the project — not a location on one "
            f"machine's disk.", file=str(p))
    if const_norm == ".." or const_norm.startswith("../"):
        raise ConfigDenial(
            f"constitution {const_raw!r} points outside the project. The "
            f"Constitution is a committed file in this repository, cited by "
            f"commit; a path that leaves the project cannot be.", file=str(p))
    const_parts = PurePosixPath(const_norm).parts
    if const_parts and const_parts[0].lower() == _skills_dir.lower():
        raise ConfigDenial(
            f"constitution {const_raw!r} is inside {_skills_dir!r}. "
            f"Guidance shapes how the generator writes; the Constitution is what "
            f"the auditor judges against. One file cannot be both — move the "
            f"rules out of {_skills_dir!r}.", file=str(p))
    # STORE THE NORMALISED PATH. The guard is about where the file is, not how
    # the path was typed — so `skills/../AUDIT_RULES.md` passes it. But the
    # committed reader is strict (`does not identify exactly one file`), so
    # keeping the raw spelling left a value that passed configuration and failed
    # the auditor: accepted and unusable. `normpath` is a no-op on a canonical
    # path, so nothing that works today changes; what it fixes is every
    # equivalent spelling of a legitimate location, `./AUDIT_RULES.md` included.
    # Downstream — the receipt's `constitution_path`, the git pathspec, the
    # console — all then see the one canonical tree path.

    auditor = _role(raw["auditor"] or {}, "auditor", p)
    gen = raw.get("generator") or {}
    if not isinstance(gen, dict):
        raise ConfigDenial("generator must be a mapping", file=str(p))
    gen_unknown = set(gen) - _ALLOWED_GENERATOR
    if gen_unknown:
        raise ConfigDenial(f"generator: unknown keys {sorted(gen_unknown)}", file=str(p))
    generator_vendor = gen.get("vendor")
    # D150 (owner directive): streaming is on unless a project turns it off.
    # Perceived latency is the only latency there is to win, and a silent
    # generation is the whole complaint.
    generator_streaming = gen.get("streaming", True)
    if not isinstance(generator_streaming, bool):
        raise ConfigDenial("generator.streaming must be true or false", file=str(p))
    generator_effort = gen.get("reasoning_effort")
    if generator_effort is not None and generator_effort not in _EFFORT_VALUES:
        raise ConfigDenial(
            f"generator.reasoning_effort must be one of {sorted(_EFFORT_VALUES)}",
            file=str(p))
    generator_fallbacks_raw = gen.get("fallbacks") or []
    if not isinstance(generator_fallbacks_raw, list):
        raise ConfigDenial("generator.fallbacks must be a list", file=str(p))
    generator_fallbacks = tuple(
        _role(item, f"generator.fallbacks[{i}]", p, allow_fallbacks=False)
        for i, item in enumerate(generator_fallbacks_raw) if isinstance(item, dict))
    if len(generator_fallbacks) != len(generator_fallbacks_raw):
        raise ConfigDenial("generator.fallbacks entries must be mappings", file=str(p))
    _register_key_names(auditor, generator_vendor, gen.get("key_env"),
                        generator_fallbacks)

    iso_raw = raw.get("isolation") or {}
    minimum = iso_raw.get("minimum") or {}
    if set(minimum) - set(ISOLATION_DIMS):
        raise ConfigDenial(f"isolation.minimum keys must be within {list(ISOLATION_DIMS)}",
                           file=str(p))
    if not all(isinstance(v, bool) for v in minimum.values()):
        raise ConfigDenial("isolation.minimum values must be booleans", file=str(p))

    rounds = raw.get("max_rounds", 3)
    if not isinstance(rounds, int) or rounds < 1:
        raise ConfigDenial("max_rounds must be a positive integer", file=str(p))

    # State is mutable and local (gitignored); the ledger is immutable and
    # committed. They must not share a directory: one has to be ignored and the
    # other has to be committable, and a single path cannot be both.
    state_dir = (raw.get("state") or {}).get("dir", ".crossaudit")
    ledger_dir = (raw.get("ledger") or {}).get("dir", "cycles")
    s, l = Path(state_dir), Path(ledger_dir)
    if s == l or s in l.parents or l in s.parents:
        raise ConfigDenial(
            f"state.dir ({state_dir}) and ledger.dir ({ledger_dir}) overlap: the state "
            f"store is gitignored and the ledger must be committable, so one directory "
            f"cannot serve both", file=str(p))

    scope_dirs = (raw.get("scope") or {}).get("dirs")
    if scope_dirs is not None and (not isinstance(scope_dirs, list)
                                   or not all(isinstance(d, str) and d for d in scope_dirs)):
        raise ConfigDenial("scope.dirs must be a list of directory names", file=str(p))

    # `checks:` selects the deterministic rigor: a named profile ("general" —
    # the light default; "science"; "off"), or an explicit list of check names
    # (a custom mix). Missing → the light general profile; an explicit empty list
    # means exactly "no checks".
    from .dcl.profiles import DEFAULT_PROFILE, resolve as _resolve_checks
    try:
        checks = _resolve_checks(raw["checks"] if "checks" in raw else DEFAULT_PROFILE)
    except ConfigDenial as exc:
        raise ConfigDenial(str(exc), file=str(p)) from exc

    resilience_raw = raw.get("resilience") or {}
    if not isinstance(resilience_raw, dict):
        raise ConfigDenial("resilience must be a mapping", file=str(p))
    allowed_resilience = {"max_attempts", "initial_backoff_seconds",
                          "max_backoff_seconds", "retry_after_cap_seconds",
                          "circuit_breaker_failures", "circuit_breaker_cooldown_seconds"}
    if set(resilience_raw) - allowed_resilience:
        raise ConfigDenial(
            f"resilience: unknown keys {sorted(set(resilience_raw) - allowed_resilience)}",
            file=str(p))
    resilience = Resilience(
        max_attempts=int(_number(resilience_raw, "max_attempts", 3, 1, 10, p)),
        initial_backoff_seconds=_number(
            resilience_raw, "initial_backoff_seconds", 1, 0, 60, p),
        max_backoff_seconds=_number(
            resilience_raw, "max_backoff_seconds", 20, 0, 300, p),
        retry_after_cap_seconds=_number(
            resilience_raw, "retry_after_cap_seconds", 120, 0, 900, p),
        circuit_breaker_failures=int(_number(
            resilience_raw, "circuit_breaker_failures", 3, 1, 20, p)),
        circuit_breaker_cooldown_seconds=_number(
            resilience_raw, "circuit_breaker_cooldown_seconds", 60, 1, 3600, p),
    )
    if resilience.max_backoff_seconds < resilience.initial_backoff_seconds:
        raise ConfigDenial(
            "resilience.max_backoff_seconds cannot be below initial_backoff_seconds",
            file=str(p))
    budgets_raw = raw.get("budgets") or {}
    if not isinstance(budgets_raw, dict):
        raise ConfigDenial("budgets must be a mapping", file=str(p))
    allowed_budgets = {"daily_token_warning", "daily_token_limit",
                       "monthly_cost_warning_usd", "monthly_cost_limit_usd"}
    if set(budgets_raw) - allowed_budgets:
        raise ConfigDenial(f"budgets: unknown keys {sorted(set(budgets_raw) - allowed_budgets)}",
                           file=str(p))
    budgets = Budgets(
        daily_token_warning=_positive_optional(
            budgets_raw, "daily_token_warning", p, integer=True),
        daily_token_limit=_positive_optional(
            budgets_raw, "daily_token_limit", p, integer=True),
        monthly_cost_warning_usd=_positive_optional(
            budgets_raw, "monthly_cost_warning_usd", p),
        monthly_cost_limit_usd=_positive_optional(
            budgets_raw, "monthly_cost_limit_usd", p),
    )
    if (budgets.daily_token_warning and budgets.daily_token_limit and
            budgets.daily_token_warning > budgets.daily_token_limit):
        raise ConfigDenial("daily token warning cannot exceed the hard limit", file=str(p))
    if (budgets.monthly_cost_warning_usd and budgets.monthly_cost_limit_usd and
            budgets.monthly_cost_warning_usd > budgets.monthly_cost_limit_usd):
        raise ConfigDenial("monthly cost warning cannot exceed the hard limit", file=str(p))

    authority_raw = raw.get("authority") or {}
    if not isinstance(authority_raw, dict):
        raise ConfigDenial("authority must be a mapping", file=str(p))
    if set(authority_raw) - {"lone_model_blocker"}:
        raise ConfigDenial(
            f"authority: unknown keys {sorted(set(authority_raw) - {'lone_model_blocker'})}",
            file=str(p))
    lone_model_blocker = authority_raw.get("lone_model_blocker", "block")
    if lone_model_blocker not in ("block", "escalate"):
        raise ConfigDenial(
            "authority.lone_model_blocker must be 'block' (bounded revision, the "
            "default) or 'escalate' (a person decides at round one)", file=str(p))
    authority = AuthorityPolicy(lone_model_blocker=lone_model_blocker)
    repair_raw = raw.get("repair") or {}
    if not isinstance(repair_raw, dict):
        raise ConfigDenial("repair must be a mapping", file=str(p))
    allowed_repair = {"enabled", "mode", "max_changed_lines", "max_document_growth"}
    if set(repair_raw) - allowed_repair:
        raise ConfigDenial(
            f"repair: unknown keys {sorted(set(repair_raw) - allowed_repair)}", file=str(p))
    repair_enabled = repair_raw.get("enabled", True)
    if not isinstance(repair_enabled, bool):
        raise ConfigDenial("repair.enabled must be true or false", file=str(p))
    repair_mode = repair_raw.get("mode", "caution")
    if repair_mode not in ("caution", "refuse"):
        raise ConfigDenial("repair.mode must be caution or refuse", file=str(p))
    repair_lines = repair_raw.get("max_changed_lines", 200)
    if (isinstance(repair_lines, bool) or not isinstance(repair_lines, int)
            or not 1 <= repair_lines <= 10000):
        raise ConfigDenial(
            "repair.max_changed_lines must be an integer from 1 to 10000", file=str(p))
    repair_growth = repair_raw.get("max_document_growth", 0.0)
    if (isinstance(repair_growth, bool)
            or not isinstance(repair_growth, (int, float))
            or not 0 <= float(repair_growth) <= 100):
        raise ConfigDenial(
            "repair.max_document_growth must be a number from 0 to 100 "
            "(a fraction of the committed document; 0 turns the screen off)",
            file=str(p))
    repair = RepairPolicy(enabled=repair_enabled, mode=repair_mode,
                          max_changed_lines=repair_lines,
                          max_document_growth=float(repair_growth))
    prices = _prices(raw.get("prices"), p)

    return Config(
        path=p,
        science_repo=raw["science_repo"],
        audit_repo=raw.get("audit_repo"),
        constitution=const_norm,
        max_rounds=rounds,
        auditor=auditor,
        generator_vendor=generator_vendor,
        generator_provider=gen.get("provider"),
        generator_model=gen.get("model"),
        generator_key_env=gen.get("key_env"),
        generator_base_url=gen.get("base_url"),
        generator_reasoning_effort=generator_effort,
        isolation_minimum={d: bool(minimum.get(d, False)) for d in ISOLATION_DIMS},
        state_dir=state_dir,
        ledger_dir=ledger_dir,
        scope_dirs=scope_dirs,
        checks=checks,
        generator_streaming=generator_streaming,
        plugins=raw.get("plugins") or [],
        generator_fallbacks=generator_fallbacks,
        resilience=resilience,
        budgets=budgets,
        authority=authority,
        repair=repair,
        prices=prices,
    )


#: Where a person changes a role's provider, by surface: the CLI edits the
#: file, the console has Project controls. A sentence that names a screen the
#: reader does not have is a sentence they cannot act on.
HETEROGENEITY_PLACE = {"cli": "crossaudit.yml", "console": "Project controls"}


def heterogeneity(cfg: Config, surface: str = "cli") -> tuple[bool, str]:
    """I1 asserted from configuration. Unknown generator vendor cannot assert it.

    The sentence returned is the one a person reads — in the CLI, the console's
    project controls and the doctor — so it says what to do, on the surface
    that will print it; the invariant's name (I1) stays in the code, the
    ledger and the tests.
    """
    if not cfg.generator_vendor:
        if surface == "console":
            return False, ("the generator's provider is not declared, so independent "
                           "review cannot be asserted; choose one in Project controls")
        return False, ("the generator's provider is not declared, so independent "
                       "review cannot be asserted; choose one in crossaudit.yml")
    generator_vendors = {cfg.generator_vendor.strip().lower(),
                         *(r.vendor.strip().lower() for r in cfg.generator_fallbacks)}
    auditor_vendors = {cfg.auditor.vendor.strip().lower(),
                       *(r.vendor.strip().lower() for r in cfg.auditor.fallbacks)}
    overlap = sorted(generator_vendors & auditor_vendors)
    if overlap:
        where = ", ".join(overlap)
        if surface == "console":
            return False, ("The generator and the auditor must use different providers "
                           "— independent review is the core of the protocol. Change one "
                           f"in Project controls; their routes overlap at {where}.")
        return False, ("The generator and the auditor must use different providers "
                       "— independent review is the core of the protocol. Change one "
                       f"in crossaudit.yml; their routes overlap at {where}.")
    return True, f"{cfg.generator_vendor} -> {cfg.auditor.vendor}"
