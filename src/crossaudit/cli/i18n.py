"""Translation for the CLI, and a fallback nobody can miss.

Why not `gettext`, which is stdlib and would have been the obvious answer
--------------------------------------------------------------------------
Four reasons, in the order they mattered.

1. **Its fallback is silent by design.** `gettext` returns the msgid when a
   translation is missing, which is exactly right for most software and exactly
   wrong here: a partially translated release would be indistinguishable from a
   finished one, and D21 says a half-Chinese wizard is worse than an English
   one. Making that visible means wrapping `gettext` in the very layer this
   module is, at which point `gettext` is carrying only its file format.
2. **The msgid IS the English string.** Reword an English sentence and every
   translation of it silently orphans — invisible drift of exactly the class
   this team keeps finding. Keys here are stable dotted ids, so English copy can
   be edited freely and only a genuinely NEW string can go missing.
3. **`.mo` files are binaries.** They cannot be read in a diff, and the frozen
   PyInstaller app would need them shipped as data with a `bindtextdomain` path
   that differs between source and bundle. That is a packaging seam bought for
   no benefit.
4. **The console already does it this way.** `page.py` carries a `ZH` mapping.
   One vocabulary across two surfaces beats two mechanisms that drift apart.

`gettext`'s real advantages — plural forms and translator tooling — are the two
we need least: Chinese has no plural agreement, and there is no translator
pipeline to feed. Stdlib only either way; this is not a dependency argument.

Recorded as the implementer's decision, with the reasoning exposed so it is
cheap to overturn: swapping the storage while keeping `t()` is a contained
change, because nothing outside this module knows how the catalogue is stored.

What a missing translation does
-------------------------------
It is served in English, **marked inline** and **counted**. Inline, because that
is what makes it visible in a screenshot, a bug report and a terminal recording
— the places a defect is actually noticed. Counted, because that is what makes
it assertable: `fallbacks()` is what the tests read, and the init path asserts
the count is zero. Neither alone is enough. A counter with no marker is
invisible to a person; a marker with no counter is invisible to CI.

It is deliberately not an exception. Crashing setup over a missing sentence
would turn a copy defect into an outage, and the guard that keeps the catalogue
complete is a test, not a traceback.

What is NOT translated, and why the seam is here
------------------------------------------------
* **Rule ids and check names.** `CA-META-001` is an identifier a person uses to
  trace a verdict back to their own constitution and to a receipt. An id is not
  prose.
* **Exit codes, `--json` payloads, and every machine-readable field.** Those are
  a scripting contract (`errors.py`); a human-readable message is not. That seam
  was drawn once already and this module does not move it.
* **Model-generated text.** A drafted rule's title, a provider's reason, the
  person's own words quoted back to them. We did not write it and must not
  pretend to have translated it.
* **Paths, environment variable names, git output, commands to type.**
"""
from __future__ import annotations

import re

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "zh")

#: Prefixed to any string served in English because its translation is missing.
#: ASCII so it survives a terminal that cannot render the copy it is marking.
FALLBACK_MARK = "[en] "
#: Served when a key exists in no catalogue at all — a programming error, shown
#: rather than raised so a typo cannot end somebody's setup.
MISSING_MARK = "[missing:{key}]"

_language = DEFAULT_LANGUAGE
_fallbacks: list[str] = []


def from_environment() -> str | None:
    """The language the person's system already asked for, or None.

    A switch a user has to discover is a switch most users never find, and the
    people who need this one most are the least likely to be reading English
    documentation to find it. `LC_ALL` then `LANG` are the conventional signal
    and the product ignored both, so a Mac set to Chinese got English.

    Only a language we actually have is honoured; anything else returns None so
    the caller keeps its own default rather than being handed a locale the
    catalogue cannot serve.
    """
    import os as _os

    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = (_os.environ.get(name) or "").strip()
        if not raw or raw.upper() in {"C", "POSIX"}:
            continue
        tag = raw.split(".")[0].split("@")[0].replace("_", "-").lower()
        primary = tag.split("-")[0]
        for known in LANGUAGES:
            if tag == known or primary == known:
                return known
        return None
    return None


def language() -> str:
    return _language


def set_language(lang: str) -> str:
    """Select a catalogue. An unknown language is English, and says so."""
    global _language
    _language = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return _language


def fallbacks() -> tuple[str, ...]:
    """Every key served in English because its translation was missing.

    Ordered by first occurrence and de-duplicated, so a test can name the gap
    rather than only count it.
    """
    return tuple(_fallbacks)


def reset_fallbacks() -> None:
    _fallbacks.clear()


def _record(key: str) -> None:
    if key not in _fallbacks:
        _fallbacks.append(key)


def t(key: str, /, **slots: object) -> str:
    """One translated string, with its slots filled.

    Slots are named and formatted by the catalogue entry itself, so a language
    may put them in a different order — which Chinese frequently needs and a
    concatenation cannot express.
    """
    table = CATALOGUE.get(_language, {})
    template = table.get(key)
    marked = ""
    if template is None:
        template = CATALOGUE[DEFAULT_LANGUAGE].get(key)
        if template is None:
            _record(key)
            return MISSING_MARK.format(key=key)
        if _language != DEFAULT_LANGUAGE:
            _record(key)
            marked = FALLBACK_MARK
    try:
        return marked + template.format(**slots)
    except (KeyError, IndexError) as exc:
        # A template asking for a slot the caller did not supply is a defect in
        # this file, not in the caller's flow. Show it; do not end the wizard.
        _record(key)
        return f"{MISSING_MARK.format(key=key)} {template} ({type(exc).__name__})"


def keys() -> tuple[str, ...]:
    """Every key the English catalogue defines. The completeness test reads this."""
    return tuple(CATALOGUE[DEFAULT_LANGUAGE])


#: The catalogue. English first and complete; every other language is checked
#: against it by `test_cli_i18n.py`, which fails on a key English has and a
#: translation does not.
CATALOGUE: dict[str, dict[str, str]] = {
    "en": {
        'build.done': 'Done. The work passed audit and the ledger has the whole exchange.',
        'build.done.read': 'Read it:  crossaudit watch   ·   Watch live:  crossaudit console',
        'build.interrupted': 'interrupted',
        'run.human_decision_needed': 'a human decision is needed',
        'build.nothing': 'Nothing was written and nothing was audited.',
        'build.nothing.fix': 'To fix: source {path}, or export {envs}',
        'build.nothing.then': 'Then:   crossaudit build "{task}"',
        'build.partial': 'The run stopped before it finished. What was committed is still in the ledger: `crossaudit watch` to read it.',
        'checks.proposal.accept': 'Use the {label} checks',
        'checks.proposal.because': 'So it proposes the {label} automatic checks. They run before any model reads the work, and they never change what your rules say.',
        'checks.proposal.editable': 'You can change these at any time by editing `checks:` in crossaudit.yml. Like the rules, a change takes effect only between cycles.',
        'checks.proposal.ground': '{rule_id} {title} → {checks}',
        'checks.proposal.intro': 'Your rules ask for things CrossAudit can check mechanically:',
        'checks.proposal.keep': 'Keep the {label} checks',
        'checks.proposal.prompt': 'Automatic checks:',
        'checks.proposal.said': 'from what you said: "{said}"',
        'doctor.admission_capable.fix': 'install the built wheel to admit receipts',
        'doctor.admission_capable.label': 'This install cannot admit receipts',
        'doctor.admission_capable.why': 'It can generate, audit and verify; it cannot consume a receipt as admitted evidence.',
        'doctor.auditor_key.fix': 'source {path} or export {env}',
        'doctor.auditor_key.fix.subscription': 'sign in through CrossAudit Settings',
        'doctor.auditor_key.label': 'No auditor API key',
        'doctor.auditor_key.why': 'CrossAudit cannot run an audit without one.',
        'doctor.config.fix': 'run `crossaudit init` to write {name}',
        'doctor.config.label': 'No CrossAudit project here',
        'doctor.config.why': 'There is nothing to check until a project is set up.',
        'console.failed': 'The console did not start ({reason}). Start it yourself with:',
        'console.open_yourself': 'Open that URL when you are ready.',
        'console.opened': 'Opened in your browser.',
        'console.url': 'Console: {url}',
        'doctor.constitution.fix': 'point `constitution:` at your rules markdown',
        'doctor.constitution.label': 'Your rules file is missing',
        'doctor.constitution.why': 'The audit has no standard to judge work against.',
        'doctor.constitution_committed.fix': 'git add {name} && git commit',
        'doctor.constitution_committed.label': 'Your rules are not committed',
        'doctor.constitution_committed.why': 'Audits cite the commit that versioned the rules (I3); an uncommitted file has none.',
        'doctor.constitution_drifted.fix': 'git add {name} && git commit',
        'doctor.constitution_drifted.label': 'Your rules have uncommitted changes',
        'doctor.constitution_drifted.why': 'An audit would cite the committed version, not what is on disk.',
        'doctor.constitution_rules.fix': 'give each rule a `### CA-AREA-NNN` heading',
        'doctor.constitution_rules.label': 'Your rules',
        'doctor.constitution_rules.none': 'no rules yet — nothing is gated until you add one; the automatic checks still run',
        'doctor.constitution_rules.why': 'No rule headings were found, so every citation in an audit would be unknown.',
        'doctor.contracts': '{n} automatic check configured   (they run on your first task)',
        'doctor.contracts.plural': '{n} automatic checks configured   (they run on your first task)',
        'doctor.generator_key.fix': 'source {path} or export {env} — without it `crossaudit build` stops in round one',
        'doctor.generator_key.label': 'No generator API key',
        'doctor.generator_key.why': 'CrossAudit cannot write anything without one.',
        'doctor.gh.fix': 'install gh and run `gh auth login`',
        'doctor.gh.label': 'The GitHub CLI is not available',
        'doctor.gh.why': 'The two-repository plan cannot be created for you.',
        'doctor.git.fix': 'install git',
        'doctor.git.label': 'git is not installed',
        'doctor.git.why': 'The ledger is git, so nothing can be committed or audited.',
        'doctor.git_identity.fix': 'set them with `git config user.name NAME` and `git config user.email EMAIL`',
        'doctor.git_identity.label': 'This clone has no git identity',
        'doctor.git_identity.why': 'Commits cannot be attributed, so the ledger loses provenance.',
        'doctor.heterogeneity.fix': 'declare generator.vendor, and make it differ from auditor.vendor',
        'doctor.heterogeneity.label': 'Generator and auditor are the same vendor (I1)',
        'doctor.heterogeneity.why': 'Same-source supervision is not an independent audit, so the protocol refuses it.',
        'doctor.install.fix': 'reinstall from a wheel',
        'doctor.install.label': 'This install cannot identify itself',
        'doctor.install.why': 'Receipts cannot record which code produced them.',
        'doctor.isolation.fix': 'run the auditor in a separate credential boundary, or deliberately lower isolation.minimum.permissive between cycles',
        'doctor.isolation.label': "Both roles' keys are reachable from one process",
        'doctor.isolation.why': 'Permissive isolation is required here, and this process can reach both.',
        'doctor.not_ready': 'Not ready — {n} thing needs attention.',
        'doctor.not_ready.plural': 'Not ready — {n} things need attention.',
        'doctor.other_passed': '{n} other check passed        (crossaudit doctor --all to list them)',
        'doctor.other_passed.plural': '{n} other checks passed        (crossaudit doctor --all to list them)',
        'doctor.provider.fix': 'set auditor.provider to one of: {providers}',
        'doctor.provider.label': 'The auditor provider is not one CrossAudit knows',
        'doctor.provider.why': 'No audit can be requested from it.',
        'doctor.python.fix': 'install Python 3.10 or newer',
        'doctor.python.label': 'Python is too old',
        'doctor.python.why': 'CrossAudit needs Python 3.10 or newer to run at all.',
        'doctor.ready': 'Ready.',
        'doctor.repo.fix': 'run `git init` here',
        'doctor.repo.label': 'This project is not a git repository',
        'doctor.repo.why': 'The ledger is git, not a directory, so nothing can be committed.',
        'doctor.state.fix': 'make {path} writable',
        'doctor.state.label': 'The controller cannot save its state',
        'doctor.state.why': 'Consumed receipts cannot be recorded, so nothing is durable.',
        'doctor.tier.label': "How much this project's history proves",
        'doctor.tier.standing.enforced': 'nothing to do — a failed audit already refuses the merge',
        'doctor.tier.standing.local': "nothing to change unless you want this history to prove more than self-review; `crossaudit pair` separates the two agents",
        'doctor.tier.standing.verified-notification': 'nothing to change unless you want a failed audit to refuse the merge; make the audit check required on the branch',
        'doctor.tier.standing.paired': 'nothing to change unless you want a failed audit to refuse the merge; that needs branch protection on the audit repository',
        'doctor.tier.standing.remote': 'nothing to change unless you want privilege separation; `crossaudit pair` puts the rules where the generator cannot write',
        'doctor.title': 'crossaudit doctor',
        'doctor.tls.fix': 'pip install certifi, or export SSL_CERT_FILE=/path/to/ca-bundle.pem (macOS python.org builds: run Install Certificates.command)',
        'doctor.tls.label': 'No trusted root certificates',
        'doctor.tls.why': 'Every HTTPS call to a vendor will fail.',
        'done.gh_missing': '{detail} — install from https://cli.github.com first',
        'done.next': 'Next',
        'done.not_ready': 'Setup written — not ready to run yet',
        'done.ready': 'Ready',
        'done.two_repos': 'Two repositories (privilege separation)',
        'editor.failed': 'could not start {editor}: {error}',
        'editor.manual': 'edit it here, then re-run setup: {path}',
        'editor.manual_instead': 'edit it here instead: {path}',
        'file.config_written': '{name} written',
        'file.keys_written': 'keys written to {path} (mode 600)',
        'file.setup_committed': 'setup committed — {sha}',
        'init.banner.subtitle': 'Two models from different vendors, one ledger in git. Four questions, then it runs.',
        'init.banner.title': 'CrossAudit — setting up a supervised project',
        'init.step1.note': 'The model that reviews everything before it counts as done.',
        'init.step1.title': 'Who audits',
        'init.step2.note': 'The model that writes each build round. Its vendor is also recorded so same-source supervision can be refused before either key is used.',
        'init.step2.title': 'Who generates',
        'init.step3.hidden': 'Hidden by default. After entry, only length and the final four characters are shown for paste checking. Set CROSSAUDIT_SHOW_KEYS=1 only when you explicitly want visible input.',
        'init.step3.title': 'API keys',
        'init.step3.where': 'Written to {path} with mode 600, never placed in the repository. Leave blank to export them yourself.',
        'init.step4.note': 'Say it in your own words. You will see the rules before anything is committed, and you choose — you never write markdown.',
        'init.step4.title': 'What this is, and what would be a mistake',
        'next.build': 'say what to build; the loop writes and audits it',
        'next.build.english_only': 'this command still answers in English',
        'next.console': 'two windows in a browser, live, and it outlives the window',
        'next.doctor': 'check everything, offline and read-only',
        'next.doctor_recheck': 're-check once a key is in place; it agrees with this',
        'next.no_key': 'the {role} has no key yet; `crossaudit build` stops without it',
        'next.source_keys': 'load the keys you entered into this shell',
        'next.source_keys.ready': 'load the keys into this shell',
        'option.human': 'human',
        'option.human.hint': 'you write it yourself',
        'option.type_it': 'something else',
        'option.type_it.hint': 'type the id yourself',
        'origin.front_door': 'This is {version}, installed as {mode}, at {path}.',
        'prepare.created': 'created {path}',
        'prepare.git_init': 'git init — the ledger is git, and an audit reads commits',
        'prepare.gitignore': 'ignored CrossAudit local state directories — not the ledger',
        'prompt.auditor_key': '{vendor} key — the auditor',
        'prompt.auditor_vendor': 'Auditor vendor:',
        'prompt.base_url': 'OpenAI-compatible base URL',
        'prompt.description': 'your project, in a sentence or three',
        'prompt.description.placeholder': 'e.g. a review of the PV industry; every figure must trace to a source',
        'prompt.generator_key': '{vendor} key — the generator (leave blank to export it yourself)',
        'prompt.generator_vendor': 'Generator vendor:',
        'prompt.model': '{role} model:',
        'prompt.model_id': 'Model id',
        'prompt.model_id.placeholder': 'exactly as the vendor spells it',
        'prompt.project_name': 'Project name (owner/name, or a label)',
        'refusal.no_project.fix': 'crossaudit init     set one up, right here',
        'refusal.no_project.looked': 'Looked for {name} in {where} and every directory above it.',
        'refusal.no_project.title': 'No CrossAudit project here.',
        'role.auditor': 'auditor',
        'role.generator': 'generator',
        'rules.draft_failed': 'could not draft rules from your description: {reason}',
        'rules.draft_failed.fallback': 'Showing a starting point instead — you can edit it here, or pick a different one.',
        'rules.drafted_header': 'Rules drafted from what you said · {count} rule',
        'rules.drafted_header.plural': 'Rules drafted from what you said · {count} rules',
        'rules.drafted_header.attributed': 'Rules drafted from what you said · {count} rule, {attributed} from your description',
        'rules.drafted_header.attributed.plural': 'Rules drafted from what you said · {count} rules, {attributed} from your description',
        'rules.edits_loaded': 'edits loaded — showing them again before committing',
        'rules.free_to_change': 'You can change these at any time. Changing the rules never changes a decision already made.',
        'rules.gating_frame': 'Before CrossAudit accepts any work, it will check that:',
        'rules.no_key_here': 'there is no key in ${env} yet — export ${env}, or re-run setup with `crossaudit init --force` to store one. The rest of setup does not need it',
        'rules.option.edit': 'Edit them first',
        'rules.option.edit.hint': 'opens the file in your editor',
        'rules.option.show': 'Show the full rules',
        'rules.option.show.hint': 'every rule, in full',
        'rules.option.switch': 'Use a different starting point',
        'rules.option.switch.hint': 'general, science & data, or only what you write',
        'rules.option.use': 'Use these rules',
        'rules.option.use.hint': 'writes and commits them',
        'rules.panel.full': '{name} — in full',
        'rules.prompt': 'These rules:',
        'rules.starting_point_header': 'A starting point — not drafted from your description · {label}',
        'rules.starting_point_prompt': 'Starting point:',
        'rules.written': '{name} written and committed with the rest of setup',
        'select.chose': 'chose {n}) {label}',
        'select.default': '(default)',
        'select.hint': '↑↓ to move · enter to choose · or type 1-{n}',
        'select.hint.single': 'enter to choose',
        'start.general.c1': 'it does what you asked for',
        'start.general.c2': 'it is finished — no TODO or placeholder text left in',
        'start.general.c3': 'nothing it states contradicts the sources you gave it',
        'start.general.hint': 'any deliverable — prose, documents, code',
        'start.general.label': 'General',
        'start.own.c1': 'nothing will be blocked, whatever the work says',
        'start.own.c2': 'the automatic checks still run, and every result is still recorded',
        'start.own.frame': 'There are no rules to check yet, so until you write one:',
        'start.own.hint': 'no rules yet; nothing is gated until you add some',
        'start.own.label': 'Only what I write myself',
        'start.science.c1': 'every result declares the inputs and code version it came from',
        'start.science.c2': 'every number carries a unit and a traceable source',
        'start.science.c3': 'anything reported as converged actually met its threshold',
        'start.science.c4': 'the prose does not disagree with the data files',
        'start.science.hint': 'numerical results with declared inputs and units',
        'start.science.label': 'Science & data',
    },
    "zh": {
        'build.done': '完成。成果已通过审计，账本里保存了完整的往来记录。',
        'build.done.read': '查看它：crossaudit watch   ·   实时观看：crossaudit console',
        'build.interrupted': '已中断',
        'run.human_decision_needed': '需要人工决定',
        'build.nothing': '没有写出任何东西，也没有进行任何审计。',
        'build.nothing.fix': '修复方法：执行 source {path}，或导出 {envs}',
        'build.nothing.then': '然后：  crossaudit build "{task}"',
        'build.partial': '这次运行在完成前停止了。已经提交的部分仍在账本里：用 `crossaudit watch` 查看。',
        'checks.proposal.accept': '使用「{label}」检查',
        'checks.proposal.because': '因此它建议使用「{label}」自动检查。这些检查在任何模型读到成果之前运行，并且不会改变你的规则所说的内容。',
        'checks.proposal.editable': '这些你随时可以通过编辑 crossaudit.yml 里的 `checks:` 来修改。和规则一样，修改只在两个周期之间生效。',
        'checks.proposal.ground': '{rule_id} {title} → {checks}',
        'checks.proposal.intro': '你的规则要求的一些事情，CrossAudit 可以用程序来检查：',
        'checks.proposal.keep': '保持「{label}」检查',
        'checks.proposal.prompt': '自动检查：',
        'checks.proposal.said': '来自你说的话：“{said}”',
        'doctor.admission_capable.fix': '安装构建好的 wheel 才能采信收据',
        'doctor.admission_capable.label': '此安装无法采信收据',
        'doctor.admission_capable.why': '它可以生成、审计和验证；但不能把收据作为已采信的证据使用。',
        'doctor.auditor_key.fix': '执行 source {path}，或导出 {env}',
        'doctor.auditor_key.fix.subscription': '在 CrossAudit 设置中登录',
        'doctor.auditor_key.label': '没有审计方 API 密钥',
        'doctor.auditor_key.why': '没有它 CrossAudit 无法进行审计。',
        'doctor.config.fix': '运行 `crossaudit init` 来写入 {name}',
        'doctor.config.label': '这里没有 CrossAudit 项目',
        'doctor.config.why': '在建立项目之前没有可检查的内容。',
        'console.failed': '控制台未能启动（{reason}）。你可以自己启动它：',
        'console.open_yourself': '准备好后在浏览器中打开该地址。',
        'console.opened': '已在你的浏览器中打开。',
        'console.url': '控制台：{url}',
        'doctor.constitution.fix': '把 `constitution:` 指向你的规则 markdown 文件',
        'doctor.constitution.label': '缺少你的规则文件',
        'doctor.constitution.why': '审计没有可据以判断成果的标准。',
        'doctor.constitution_committed.fix': '执行 git add {name} && git commit',
        'doctor.constitution_committed.label': '你的规则尚未提交',
        'doctor.constitution_committed.why': '审计会引用为规则定版的那次提交（I3）；未提交的文件没有这样的提交。',
        'doctor.constitution_drifted.fix': '执行 git add {name} && git commit',
        'doctor.constitution_drifted.label': '你的规则有未提交的改动',
        'doctor.constitution_drifted.why': '审计会引用已提交的版本，而不是磁盘上的内容。',
        'doctor.constitution_rules.fix': '给每条规则一个 `### CA-AREA-NNN` 标题',
        'doctor.constitution_rules.label': '你的规则',
        'doctor.constitution_rules.none': '暂无规则 — 在你添加之前不会拦截任何东西；自动检查仍会运行',
        'doctor.constitution_rules.why': '没有找到规则标题，因此审计中的每一处引用都无法对应。',
        'doctor.contracts': '已配置 {n} 项自动检查   （它们会在你的第一个任务上运行）',
        'doctor.contracts.plural': '已配置 {n} 项自动检查   （它们会在你的第一个任务上运行）',
        'doctor.generator_key.fix': '执行 source {path}，或导出 {env} — 缺少它 `crossaudit build` 会在第一轮就停下',
        'doctor.generator_key.label': '没有生成方 API 密钥',
        'doctor.generator_key.why': '没有它 CrossAudit 无法写出任何东西。',
        'doctor.gh.fix': '安装 gh 并运行 `gh auth login`',
        'doctor.gh.label': 'GitHub CLI 不可用',
        'doctor.gh.why': '无法为你创建双仓库方案。',
        'doctor.git.fix': '安装 git',
        'doctor.git.label': '未安装 git',
        'doctor.git.why': '账本就是 git，因此没有任何东西能被提交或审计。',
        'doctor.git_identity.fix': '用 `git config user.name NAME` 和 `git config user.email EMAIL` 设置它们',
        'doctor.git_identity.label': '这个克隆没有 git 身份',
        'doctor.git_identity.why': '提交无法归属，账本会失去来源信息。',
        'doctor.heterogeneity.fix': '声明 generator.vendor，并使其不同于 auditor.vendor',
        'doctor.heterogeneity.label': '生成方与审计方是同一厂商（I1）',
        'doctor.heterogeneity.why': '同源监督不是独立审计，协议因此拒绝它。',
        'doctor.install.fix': '从 wheel 重新安装',
        'doctor.install.label': '此安装无法标识自身',
        'doctor.install.why': '收据无法记录是哪份代码产生了它们。',
        'doctor.isolation.fix': '在独立的凭据边界中运行审计方，或在两个周期之间有意调低 isolation.minimum.permissive',
        'doctor.isolation.label': '两个角色的密钥可以被同一个进程读到',
        'doctor.isolation.why': '此处要求宽松隔离，而这个进程两者都能读到。',
        'doctor.not_ready': '尚未就绪 — 有 {n} 项需要处理。',
        'doctor.not_ready.plural': '尚未就绪 — 有 {n} 项需要处理。',
        'doctor.other_passed': '另有 {n} 项检查通过        （用 crossaudit doctor --all 逐条查看）',
        'doctor.other_passed.plural': '另有 {n} 项检查通过        （用 crossaudit doctor --all 逐条查看）',
        'doctor.provider.fix': '把 auditor.provider 设为其中之一：{providers}',
        'doctor.provider.label': '审计方 provider 不是 CrossAudit 认识的',
        'doctor.provider.why': '无法向它请求任何审计。',
        'doctor.python.fix': '安装 Python 3.10 或更高版本',
        'doctor.python.label': 'Python 版本过旧',
        'doctor.python.why': 'CrossAudit 需要 Python 3.10 或更高版本才能运行。',
        'doctor.ready': '已就绪。',
        'doctor.repo.fix': '在这里运行 `git init`',
        'doctor.repo.label': '这个项目不是 git 仓库',
        'doctor.repo.why': '账本是 git 而不是一个目录，因此没有东西能被提交。',
        'doctor.state.fix': '让 {path} 可写',
        'doctor.state.label': '控制器无法保存状态',
        'doctor.state.why': '已采信的收据无法记录，因此没有任何东西是持久的。',
        'doctor.tier.label': '这个项目的历史能证明到什么程度',
        'doctor.tier.standing.enforced': '无需处理——审计失败已经会拒绝合并',
        'doctor.tier.standing.local': '无需更改，除非你希望这段历史能证明的不止是自我审查；`crossaudit pair` 会把两个代理分开',
        'doctor.tier.standing.verified-notification': '无需更改，除非你希望审计失败时拒绝合并；请把该审计检查设为分支的必需项',
        'doctor.tier.standing.paired': '无需更改，除非你希望审计失败时拒绝合并；那需要在审计仓库上启用分支保护',
        'doctor.tier.standing.remote': '无需更改，除非你需要权限分离；`crossaudit pair` 会把规则放到生成者无法写入的地方',
        'doctor.title': 'crossaudit doctor',
        'doctor.tls.fix': '执行 pip install certifi，或导出 SSL_CERT_FILE=/path/to/ca-bundle.pem（macOS 的 python.org 版本：运行 Install Certificates.command）',
        'doctor.tls.label': '没有受信任的根证书',
        'doctor.tls.why': '对厂商的每一次 HTTPS 调用都会失败。',
        'done.gh_missing': '{detail} — 请先从 https://cli.github.com 安装',
        'done.next': '下一步',
        'done.not_ready': '设置已写入 — 但还不能运行',
        'done.ready': '就绪',
        'done.two_repos': '两个仓库（权限分离）',
        'editor.failed': '无法启动 {editor}：{error}',
        'editor.manual': '在这里编辑它，然后重新运行设置：{path}',
        'editor.manual_instead': '改为在这里编辑它：{path}',
        'file.config_written': '{name} 已写入',
        'file.keys_written': '密钥已写入 {path}（权限 600）',
        'file.setup_committed': '设置已提交 — {sha}',
        'init.banner.subtitle': '两个来自不同厂商的模型，一份存放在 git 里的账本。回答四个问题即可运行。',
        'init.banner.title': 'CrossAudit — 正在建立一个受监督的项目',
        'init.step1.note': '这个模型会在任何成果被视为完成之前进行复核。',
        'init.step1.title': '由谁审计',
        'init.step2.note': '这个模型负责撰写每一轮构建。它的厂商也会被记录下来，以便在动用任何密钥之前就拒绝同源监督。',
        'init.step2.title': '由谁生成',
        'init.step3.hidden': '默认隐藏输入。输入后只显示长度和最后四位，用于核对粘贴是否完整。只有在你确实需要可见输入时才设置 CROSSAUDIT_SHOW_KEYS=1。',
        'init.step3.title': 'API 密钥',
        'init.step3.where': '写入 {path}，权限为 600，绝不会放进代码仓库。留空则由你自己导出。',
        'init.step4.note': '用你自己的话说。在任何东西被提交之前，你都会先看到这些规则，并由你来选择——你永远不需要自己写 markdown。',
        'init.step4.title': '这是什么项目，以及什么算是出错',
        'next.build': '说出要构建什么；循环会撰写并审计它',
        'next.build.english_only': '此命令目前仍以英文作答',
        'next.console': '浏览器里的两个窗口，实时更新，关闭窗口后仍继续',
        'next.doctor': '全面检查，离线且只读',
        'next.doctor_recheck': '有密钥之后重新检查；它与这里的结论一致',
        'next.no_key': '{role}还没有密钥；缺少它 `crossaudit build` 会停下',
        'next.source_keys': '把你刚输入的密钥载入这个 shell',
        'next.source_keys.ready': '把密钥载入这个 shell',
        'option.human': '人工',
        'option.human.hint': '由你自己撰写',
        'option.type_it': '其他',
        'option.type_it.hint': '自己输入 id',
        'origin.front_door': '这是 {version}，安装方式为 {mode}，位于 {path}。',
        'prepare.created': '已创建 {path}',
        'prepare.git_init': 'git init — 账本就是 git，审计读取的是提交',
        'prepare.gitignore': '已忽略 CrossAudit 的本地状态目录 — 它们不是账本',
        'prompt.auditor_key': '{vendor} 密钥 — 审计方',
        'prompt.auditor_vendor': '审计方厂商：',
        'prompt.base_url': '兼容 OpenAI 的 base URL',
        'prompt.description': '用一到三句话描述你的项目',
        'prompt.description.placeholder': '例如：一份光伏产业综述；每个数字都必须能追溯到来源',
        'prompt.generator_key': '{vendor} 密钥 — 生成方（留空则由你自己导出）',
        'prompt.generator_vendor': '生成方厂商：',
        'prompt.model': '{role} 模型：',
        'prompt.model_id': '模型 id',
        'prompt.model_id.placeholder': '与厂商的写法完全一致',
        'prompt.project_name': '项目名称（owner/name，或一个标签）',
        'refusal.no_project.fix': 'crossaudit init     就在这里建立一个',
        'refusal.no_project.looked': '已在 {where} 及其每一级上层目录中查找 {name}。',
        'refusal.no_project.title': '这里没有 CrossAudit 项目。',
        'role.auditor': '审计方',
        'role.generator': '生成方',
        'rules.draft_failed': '无法根据你的描述起草规则：{reason}',
        'rules.draft_failed.fallback': '改为显示一个起点 — 你可以在这里编辑它，或另选一个。',
        'rules.drafted_header': '根据你说的话起草的规则 · {count} 条',
        'rules.drafted_header.plural': '根据你说的话起草的规则 · {count} 条',
        'rules.drafted_header.attributed': '根据你说的话起草的规则 · {count} 条，其中 {attributed} 条来自你的描述',
        'rules.drafted_header.attributed.plural': '根据你说的话起草的规则 · {count} 条，其中 {attributed} 条来自你的描述',
        'rules.edits_loaded': '已载入你的修改 — 提交前会再显示一次',
        'rules.free_to_change': '这些规则你随时可以修改。修改规则永远不会改变已经作出的判定。',
        'rules.gating_frame': '在 CrossAudit 接受任何成果之前，它会检查：',
        'rules.no_key_here': '${env} 中还没有密钥 — 请导出 ${env}，或用 `crossaudit init --force` 重新运行设置来保存一个。设置的其余部分并不需要它',
        'rules.option.edit': '先编辑',
        'rules.option.edit.hint': '在你的编辑器中打开该文件',
        'rules.option.show': '显示完整规则',
        'rules.option.show.hint': '逐条完整显示',
        'rules.option.switch': '换一个起点',
        'rules.option.switch.hint': '通用、科学与数据，或只用你自己写的',
        'rules.option.use': '使用这些规则',
        'rules.option.use.hint': '写入并提交',
        'rules.panel.full': '{name} — 完整内容',
        'rules.prompt': '这些规则：',
        'rules.starting_point_header': '一个起点 — 并非根据你的描述起草 · {label}',
        'rules.starting_point_prompt': '起点：',
        'rules.written': '{name} 已写入，并与其余设置一同提交',
        'select.chose': '已选 {n}) {label}',
        'select.default': '（默认）',
        'select.hint': '↑↓ 移动 · 回车选择 · 或直接输入 1-{n}',
        'select.hint.single': '回车选择',
        'start.general.c1': '它完成了你所要求的事',
        'start.general.c2': '它是完整的 — 没有遗留 TODO 或占位文字',
        'start.general.c3': '它所陈述的内容不与你提供的资料相矛盾',
        'start.general.hint': '任何交付物 — 文章、文档、代码',
        'start.general.label': '通用',
        'start.own.c1': '无论成果写了什么，都不会被拦截',
        'start.own.c2': '自动检查仍会运行，每个结果仍会被记录',
        'start.own.frame': '目前还没有可检查的规则，所以在你写下第一条之前：',
        'start.own.hint': '暂无规则；在你添加之前不会拦截任何东西',
        'start.own.label': '只用我自己写的',
        'start.science.c1': '每个结果都声明了它来自哪些输入和哪个代码版本',
        'start.science.c2': '每个数字都带有单位和可追溯的来源',
        'start.science.c3': '任何被报告为已收敛的结果，确实达到了它的阈值',
        'start.science.c4': '文字叙述与数据文件不相冲突',
        'start.science.hint': '带有明确输入与单位的数值结果',
        'start.science.label': '科学与数据',
    },
}


# ------------------------------------------------------------------ denials
# A refusal is raised where it is decided and printed where it is met; the
# raise site cannot call `t()` because it does not know the surface. So the
# refusals are translated at the seam where a person meets them, by the
# English `reason` — see `denials_zh.py` for why that is not the text-matching
# D130 forbids: the lookup is applied to `Denial.reason` only, never to text a
# person could have authored.
_denial_exact: dict[str, str] = {}
_denial_patterns: list[tuple[re.Pattern[str], str]] = []


def _compile(entries, exact: dict[str, str],
             patterns: list[tuple[re.Pattern[str], str]]) -> None:
    """Split a text-keyed table into exact entries and `{}` templates."""
    for english, chinese in entries:
        if "{}" not in english:
            exact[english] = chinese
            continue
        parts = english.split("{}")
        pattern = re.compile("^" + "(.*?)".join(re.escape(p) for p in parts) + "$",
                             re.S)
        if "{}" in chinese:
            # Sequential slots become numbered ones so `format` can fill them
            # from the captured groups in order.
            pieces = chinese.split("{}")
            chinese = "".join(piece + ("{%d}" % i if i < len(pieces) - 1 else "")
                              for i, piece in enumerate(pieces))
        patterns.append((pattern, chinese))
    # First match wins, so the most specific template must be tried first: the
    # fewest slots, then the most literal text. Without this, `MCP {} failed:
    # {}` swallows "MCP server connection failed: …" into a half-translated
    # sentence — the exact defect the console's ZH_PATTERNS comment records.
    patterns.sort(key=lambda item: (item[0].pattern.count("(.*?)"),
                                    -len(item[0].pattern)))


def _compile_denials() -> None:
    from .denials_zh import ENTRIES

    _compile(ENTRIES, _denial_exact, _denial_patterns)


def _lookup(text: str, exact: dict[str, str],
            patterns: list[tuple[re.Pattern[str], str]],
            slot=None) -> str | None:
    match_exact = exact.get(text)
    if match_exact is not None:
        return match_exact
    for pattern, chinese in patterns:
        match = pattern.match(text)
        if match:
            groups = match.groups()
            if slot is not None:
                groups = tuple(slot(g) for g in groups)
            return chinese.format(*groups)
    return None


def denial_zh(reason: str) -> str | None:
    """The Chinese for a `Denial.reason`, or None when the table has none.

    Exact entries first, then templates, first match wins. The interpolated
    parts of a templated reason — paths, ids, another component's words — are
    carried through untranslated, so the sentence never says less than the
    English one did.

    None rather than the English, deliberately: the caller decides how to
    mark and count a gap, the same way `t()` does for keyed strings.
    """
    if not _denial_exact and not _denial_patterns:
        _compile_denials()
    return _lookup(reason, _denial_exact, _denial_patterns)


# ------------------------------------------------ evidence-authority sentences
# The sentences the evidence-authority decision writes for a person (D148,
# `auditor/authority.py`): the route in plain words, each audit integrity as a
# clause, and the one-or-two-sentence rationale. They are composed in the
# audit core, which does not know the surface, so like the denials they are
# translated at the seam by their English text — applied ONLY to those
# sentences (`authority["rationale"]`, `ROUTE_LABELS`, the CLI's escalate
# sentence), never to text a person or a model authored. A `{}` slot is a
# count, or a clause from this same table, which is translated in turn.
SENTENCES_ZH: tuple[tuple[str, str], ...] = (
    # ROUTE_LABELS — the route row of the report, in words.
    ("admission", "准入"),
    ("another revision round", "再一轮修订"),
    ("your decision", "由你决定"),
    ("a model audit is still needed", "仍需模型审计"),
    # INTEGRITY_IN_WORDS and its fallback.
    ("nothing was audited: the scope holds no work yet",
     "没有审计任何内容：范围内尚无工作"),
    ("the audit prompt exceeded its size bound, so the auditor did not see everything",
     "审计提示超出了大小上限，因此审计者没有看到全部内容"),
    ("the auditor's reply was not valid", "审计者的回复无效"),
    ("the model audit could not run", "模型审计无法运行"),
    ("a fixture provider exercised the loop, and a fixture cannot bless a commit",
     "本轮循环由测试桩供应商驱动，而测试桩不能为提交背书"),
    ("the audit did not complete cleanly", "审计未能完整完成"),
    # _rationale — first sentences.
    ("An earlier escalation holds this cycle under human jurisdiction (the "
     "escalation lock), so nothing here routes around it.",
     "较早的一次升级已将此周期置于人工裁决之下（升级锁定），因此这里的任何路由都不会绕过它。"),
    ("Nothing was audited: the scope holds no work yet, so a person owns this round.",
     "没有审计任何内容：范围内尚无工作，因此本轮由人来负责。"),
    ("The only block rests on a model reading without reproduced evidence, so it "
     "goes to a person rather than to automatic revision.",
     "唯一的阻断仅依据模型的判读、没有可复现的证据，因此交由人来处理，而不是自动修订。"),
    ("{} deterministic check failure(s) on committed bytes block this round; the "
     "block rests on reproduced evidence.",
     "已提交内容上有 {} 项确定性检查失败阻断了本轮；该阻断基于可复现的证据。"),
    ("The block rests on the auditor's reading, which no deterministic check "
     "reproduced; it enters bounded revision by policy and is recorded as unverified.",
     "该阻断基于审计者的判读，没有任何确定性检查复现它；按策略进入受限修订，并记录为未验证。"),
    ("A model audit is still needed before this round can pass.",
     "本轮通过之前仍需一次模型审计。"),
    ("No finding blocks this round; the deterministic checks and the model audit "
     "both completed.",
     "没有发现阻断本轮；确定性检查和模型审计均已完成。"),
    ("The auditor asked for human judgment on this round.",
     "审计者要求对本轮进行人工判断。"),
    # _rationale — composed from an integrity clause (translated in turn).
    ("{}, so a person owns this round.", "{}，因此本轮由人来负责。"),
    ("{}, so the receipt is not admissible.", "{}，因此该收据不可准入。"),
    ("{} further blocking concern(s) from the auditor remain unverified.",
     "审计者提出的另外 {} 项阻断性疑虑仍未验证。"),
    # cli/main.py CONTESTED_MODEL_BLOCKER_REASON — the escalate-dial stop.
    ("the auditor raised a concern that no deterministic check reproduces; it "
     "needs your judgment",
     "审计者提出了一项没有任何确定性检查能复现的疑虑；需要你来判断"),
)
_sentence_exact: dict[str, str] = {}
_sentence_patterns: list[tuple[re.Pattern[str], str]] = []


def _sentence_slot(part: str) -> str:
    """A slot is a count (carried through) or a clause that begins a sentence
    with its first letter raised; the clause is looked up in its own case."""
    if not part:
        return part
    lowered = part[0].lower() + part[1:]
    found = _lookup(lowered, _sentence_exact, _sentence_patterns)
    return part if found is None else found


def sentence_zh(text: str) -> str | None:
    """The Chinese for one evidence-authority sentence, or None."""
    if not _sentence_exact and not _sentence_patterns:
        _compile(SENTENCES_ZH, _sentence_exact, _sentence_patterns)
    return _lookup(text, _sentence_exact, _sentence_patterns, slot=_sentence_slot)


def sentence_text(text: str) -> str:
    """`text` in the selected language — the `denial_text` contract for the
    evidence-authority sentences: English verbatim; in Chinese a sentence
    without an entry is served marked and counted under `sentence:`."""
    if _language == DEFAULT_LANGUAGE:
        return text
    translated = sentence_zh(text)
    if translated is None:
        _record("sentence:" + text)
        return FALLBACK_MARK + text
    return translated


def denial_text(reason: str) -> str:
    """`reason` in the selected language, marked and counted when missing.

    English is served verbatim. In Chinese a reason without an entry is served
    in English behind FALLBACK_MARK and recorded under `denial:` so the
    end-of-run notice can name it — the same contract as `t()`.
    """
    if _language == DEFAULT_LANGUAGE:
        return reason
    translated = denial_zh(reason)
    if translated is None:
        _record("denial:" + reason)
        return FALLBACK_MARK + reason
    return translated
