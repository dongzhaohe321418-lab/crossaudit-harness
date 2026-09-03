"""Chinese for the refusals: every `Denial` reason, keyed by its English.

Why this is a separate table and not more `t()` keys
----------------------------------------------------
A denial is raised where the refusal is decided — in the audit core, the
providers, the verifier — and those modules must not know which surface will
print them. `errors.py` draws the seam: `reason` is the machine contract (exit
code, `--json`, the line the macOS shell parses), `human` is an optional
sentence for a person. Only three raise sites carry a `human=`; the other
six hundred carry a reason and nothing else, which is why D130 measured the
refusals as the least-translated strings in the product.

So the table is keyed by the English reason **exactly as the source writes
it**, and the lookup is applied to `Denial.reason` only — never to free text.
That keeps D130's rule intact: the identity of the string comes from its
provenance (it was raised as a Denial by us), not from what it happens to look
like, and a person's own words can never be matched against this table.

Two shapes
----------
* A static reason is an exact entry.
* A reason built with an f-string is a **template**: `{}` marks each part the
  source interpolates, in order. The Chinese side keeps the same `{}` slots
  (or `{0}`, `{1}` … to reorder, which Chinese often needs). The interpolated
  parts — paths, ids, shas, counts, another component's own words — are
  carried through untranslated: they are identifiers, not prose, and a
  translation that drops them says less than the English did.

Style
-----
Plain and short. Terminology follows the catalogues that already exist in
`i18n.CATALOGUE["zh"]` and the console's `ZH` map: 生成者 / 审计者, 收据,
判定, 账本, 准入, 章程, 周期, 轮, 供应商 / 厂商, 凭据, 备用路由, 工作区,
钥匙串, 工作仓库 / 审计仓库, 指导, 技能, 检查. Identifiers, config keys,
flags, commands, verdict words (PASS, BLOCKED) and file names stay Latin.

The table is data; the lookup lives in `i18n.denial_zh()`. The gate in
`tests/test_denial_strings_are_legible.py` pins the residual (the reasons
deliberately left without an entry) and refuses every entry whose English is
raised nowhere, so the table cannot rot in either direction.
"""
from __future__ import annotations

#: (english reason or template, chinese). ORDER MATTERS within templates only
#: where one template could match another's rendering: the more specific one
#: goes first. Every entry is anchored to the whole reason, so a shorter
#: template never swallows a longer sentence that merely starts the same way.
ENTRIES: tuple[tuple[str, str], ...] = (
    # ------------------------------------------------------------ app.py
    ("project-console port must be an integer, not {}",
     "project-console 端口必须是整数，而不是 {}"),
    ("project-console port must be between 0 and 65535",
     "project-console 端口必须在 0 到 65535 之间"),
    ("project-console requires DIRECTORY and an optional PORT",
     "project-console 需要 DIRECTORY 参数，PORT 可选"),
    ("project directory does not exist or is not a directory: {}",
     "项目目录不存在或不是目录：{}"),
    ("no {} found in {} — run `crossaudit init` there",
     "在 {1} 中找不到 {0} —— 请先在那里运行 `crossaudit init`"),
    # ----------------------------------------------------- app_doctor.py
    ("Automatic Git tools setup is available only on macOS",
     "自动安装 Git 工具仅在 macOS 上可用"),
    ("Apple Command Line Tools are already installed. Run the check again; if "
     "Git is still unavailable, update macOS or reinstall the tools.",
     "Apple Command Line Tools 已安装。请重新运行检查；如果 Git 仍不可用，请更新 "
     "macOS 或重新安装这些工具。"),
    ("Could not open Apple's installer: {}", "无法打开 Apple 的安装程序：{}"),
    ("Git is not available yet. Install Git, then retry.",
     "Git 尚不可用。请安装 Git 后重试。"),
    ("Git could not initialize this project: {}", "Git 无法初始化此项目：{}"),
    ("Git could not stage the project files: {}", "Git 无法暂存项目文件：{}"),
    ("Enter a Git author name of 100 characters or fewer",
     "请输入不超过 100 个字符的 Git 作者姓名"),
    ("Enter a valid Git author email address", "请输入有效的 Git 作者邮箱地址"),
    ("Git could not save {}: {}", "Git 无法保存 {}：{}"),
    ("That Doctor repair action is not supported", "不支持该 Doctor 修复操作"),
    # ------------------------------------------------------- app_keys.py
    ("macOS Keychain is unavailable on this computer", "此电脑上无法使用 macOS 钥匙串"),
    ("unsupported credential provider {}", "不支持的凭据供应商 {}"),
    ("credential slot must be primary or backup", "凭据槽位必须是 primary 或 backup"),
    ("{} API key is empty or unexpectedly large", "{} API key 为空或过大"),
    ("{} API key contains control characters", "{} API key 含有控制字符"),
    ("macOS Keychain refused the {} key: {}", "macOS 钥匙串拒绝了 {} 密钥：{}"),
    ("settings must be an object", "设置必须是一个对象"),
    # ---------------------------------------------------- auditor/run.py
    ("the frozen application is missing its deterministic-layer identity; "
     "reinstall CrossAudit from a verified build",
     "打包版应用缺少确定性层的身份标识；请从经过验证的构建重新安装 CrossAudit"),
    # ------------------------------------------------------- autonomy.py
    ("choose one primary output format: PDF and Word/DOCX were both requested",
     "请只选择一种主要输出格式：不能同时要求 PDF 和 Word/DOCX"),
    ("the task is empty", "任务为空"),
    # ------------------------------------------------------------ broker/
    ("recovery snapshot is missing; cannot restore", "恢复快照缺失，无法还原"),
    ("a tool must have a name", "工具必须有名称"),
    ("tool {} is already registered", "工具 {} 已经注册"),
    # ------------------------------------------------------- cli/build.py
    ("git returned an unsupported object format: {}", "git 返回了不支持的对象格式：{}"),
    ("git returned an invalid generated blob identity", "git 返回了无效的生成 blob 标识"),
    ("chat id is invalid", "对话 id 无效"),
    ("the Generator exceeded the automatic MCP call limit",
     "生成者超出了自动 MCP 调用上限"),
    ("the Generator exceeded the automatic remote-compute call limit",
     "生成者超出了自动远程计算调用上限"),
    ("document export discarded its authorization receipt",
     "文档导出丢弃了它的授权收据"),
    ('say what to build: crossaudit build "..."',
     '请说明要构建什么：crossaudit build "..."'),
    ("{} is not a git repository; the ledger is git", "{} 不是 git 仓库；账本就是 git"),
    ("connect a provider first: the generator has no credential (`crossaudit doctor` "
     "will ask for it)",
     "请先连接供应商：生成者没有凭据（`crossaudit doctor` 会提示输入）"),
    ("connect a provider first: the auditor has no credential (`crossaudit doctor` "
     "will ask for it)",
     "请先连接供应商：审计者没有凭据（`crossaudit doctor` 会提示输入）"),
    ("connect a provider first: neither the generator nor the auditor has a credential "
     "(`crossaudit doctor` will ask for them)",
     "请先连接供应商：生成者与审计者都没有凭据（`crossaudit doctor` 会提示输入）"),
    ("scope.dirs is not set: the generator must be told where it may write, or it "
     "could rewrite the rules it is judged by",
     "未设置 scope.dirs：必须告诉生成者它可以写入哪里，否则它可能改写用来评判它的规则"),
    # -------------------------------------------------------- cli/main.py
    ("the committed constitution at {} is not valid UTF-8",
     "已提交的章程 {} 不是有效的 UTF-8"),
    ("the committed constitution at {} is empty; an audit cannot apply a missing "
     "standard",
     "已提交的章程 {} 为空；审计无法套用一个不存在的标准"),
    ("committed TASK.md is not UTF-8", "已提交的 TASK.md 不是 UTF-8"),
    ("refusing to read through a symlink: {}", "拒绝通过符号链接读取：{}"),
    ("{} is not a git repository", "{} 不是 git 仓库"),
    ("{} only touches the ledger ({}/): this is an audit artefact, not an "
     "increment. Audit the science commit instead, or move the ledger to the "
     "audit repository (github-pair mode).",
     "{} 只改动了账本（{}/）：这是审计产物，不是增量。请改为审计科学提交，或把账本移到"
     "审计仓库（github-pair 模式）。"),
    ("{} is not committed: an audit must cite the commit that versioned the rules "
     "(I3). Commit it first.",
     "{} 尚未提交：审计必须引用规则所在版本的提交（I3）。请先提交它。"),
    ("build continuation cycle {} no longer exists", "要继续的构建周期 {} 已不存在"),
    ("refusing to continue cycle {}: {} does not descend from its active commit {}",
     "拒绝继续周期 {}：{} 不是其当前提交 {} 的后代"),
    ("{} was already admitted; open a new increment", "{} 已经准入；请开启新的增量"),
    ("{} already has a recorded decision in this cycle ({}); a decision already "
     "made is not replaced by re-running it. Commit a revision to continue the "
     "cycle, or start a new increment to be judged afresh.",
     "{} 在本周期（{}）已有记录在案的决定；已作出的决定不会因重新运行而被替换。请提交"
     "一次修订以继续本周期，或开启新的增量重新接受评判。"),
    ("resolve is a human act; it refuses to run without a terminal",
     "resolve 是人工操作；没有终端时它拒绝运行"),
    ("{} already exists", "{} 已存在"),
    ('say what should change: crossaudit amend "from now on ..."',
     '请说明要改什么：crossaudit amend "from now on ..."'),
    ("{} is not a git repository; the loop audits commits",
     "{} 不是 git 仓库；循环审计的是提交"),
    ("{} ({}) changed no science files — only rules, configuration or ledger. "
     "Commit your experiment, then run again.",
     "{}（{}）没有改动任何科学文件——只有规则、配置或账本。请先提交你的实验，然后再运行。"),
    ("{} is not committed; commit it first (an audit must cite the rules' commit)",
     "{} 尚未提交；请先提交它（审计必须引用规则所在的提交）"),
    # -------------------------------------------------------- cli/pair.py
    ("{} did not respond within {} seconds. Check the network or close any hidden "
     "sign-in prompt, then retry.",
     "{} 在 {} 秒内没有响应。请检查网络或关闭隐藏的登录提示，然后重试。"),
    ("pairing needs the GitHub CLI: install it from https://cli.github.com and run "
     "`gh auth login`. CrossAudit deliberately does not implement its own OAuth "
     "flow or handle your token",
     "配对需要 GitHub CLI：请从 https://cli.github.com 安装，并运行 `gh auth login`。"
     "CrossAudit 有意不实现自己的 OAuth 流程，也不经手你的 token"),
    ("GitHub is not connected. Connect the account in CrossAudit and retry.",
     "尚未连接 GitHub。请在 CrossAudit 中连接账户后重试。"),
    ("GitHub could not verify authorization scopes: {}", "GitHub 无法核实授权范围：{}"),
    ("GitHub could not check {}: {}", "GitHub 无法检查 {}：{}"),
    ("git {} failed: {}", "git {} 失败：{}"),
    ("could not inspect the existing working repository main branch: {}",
     "无法检查现有工作仓库的 main 分支：{}"),
    ("the local working repository has uncommitted changes; commit or stash them "
     "before adopting its remote history",
     "本地工作仓库有未提交的更改；请先提交或暂存（stash），再采用其远程历史"),
    ("the local and remote working repository histories conflict; the merge was "
     "aborted without changing either history. Resolve the local files or choose "
     "a clean matching clone, then retry",
     "本地与远程工作仓库的历史相互冲突；合并已中止，两边的历史均未改动。请解决本地文件"
     "的冲突，或选择一个干净且匹配的克隆，然后重试"),
    ("crossaudit.yml has no science_repo line to update",
     "crossaudit.yml 中没有可更新的 science_repo 行"),
    ("science and audit repositories must be different", "科学仓库与审计仓库必须不同"),
    ("{} repository must be owner/name, got {}", "{} 仓库必须写成 owner/name，实际得到 {}"),
    ("no Constitution at {}; run `crossaudit init` first",
     "{} 处没有章程；请先运行 `crossaudit init`"),
    ("local origin is {}, not {}; refusing to replace it",
     "本地 origin 是 {}，而不是 {}；拒绝替换它"),
    # The two forms the source actually renders, before the template the static
    # reader sees (`{where}` is "staged " or "").
    ("{} has staged changes; commit or restore them before pairing",
     "{} 有已暂存的更改；请先提交或还原它们，再进行配对"),
    ("{} has changes; commit or restore them before pairing",
     "{} 有更改；请先提交或还原它们，再进行配对"),
    ("{} has {}changes; commit or restore them before pairing",
     "{} 有{}更改；请先提交或还原它们，再进行配对"),
    ("repository {} already exists; edit the name or explicitly allow CrossAudit "
     "to use repositories you can access",
     "仓库 {} 已存在；请修改名称，或明确允许 CrossAudit 使用你能访问的仓库"),
    ("could not inspect the repository configuration change", "无法检查仓库配置的改动"),
    ("could not inspect the audit repository staging area", "无法检查审计仓库的暂存区"),
    ("could not upload {}: {}", "无法上传 {}：{}"),
    # -------------------------------------------------------- cli/talk.py
    ("routing ledger escaped the project: {}", "路由账本越出了项目范围：{}"),
    ("this needs your confirmation ({}) but stdin is not a terminal; re-run in a "
     "terminal or pass --yes",
     "这需要你的确认（{}），但 stdin 不是终端；请在终端中重新运行，或传入 --yes"),
    ("the auditor returned an empty reply", "审计者返回了空回复"),
    ("the generator returned an empty reply", "生成者返回了空回复"),
    ("nothing has been audited yet, so nothing can be disputed",
     "尚未审计任何内容，因此没有可申辩的对象"),
    ("{} is a machine check, not an auditor interpretation; fix the artifact or "
     "change `checks:` in crossaudit.yml between cycles",
     "{} 是机器检查，不是审计者的解读；请修复产物，或在两个周期之间修改 crossaudit.yml "
     "里的 `checks:`"),
    ('say something: `crossaudit talk "..."`', '请说点什么：`crossaudit talk "..."`'),
    # ------------------------------------------------------- cli/watch.py
    ("watch needs a terminal; for machines, use `status --json`",
     "watch 需要终端；机器读取请用 `status --json`"),
    # ------------------------------------------------------ cli/wizard.py
    ("could not stage the setup files: {}", "无法暂存初始化文件：{}"),
    ("could not configure the local git identity: {}", "无法配置本地 git 身份：{}"),
    ("could not inspect the staged setup files", "无法检查已暂存的初始化文件"),
    ("could not commit the setup files: {}", "无法提交初始化文件：{}"),
    ("unknown auditor vendor {}", "未知的审计者厂商 {}"),
    ("unknown generator vendor {}", "未知的生成者厂商 {}"),
    ("auditor and generator are both {}: that is same-source supervision, which "
     "the protocol refuses",
     "审计者与生成者都是 {}：这是同源监督，协议拒绝这种配置"),
    ("{} already exists; refusing to overwrite (pass --force if you mean it)",
     "{} 已存在；拒绝覆盖（确定要覆盖请传入 --force）"),
    ("auditor and generator are both {}: that is same-source supervision, which "
     "is the thing this protocol exists to avoid",
     "审计者与生成者都是 {}：这是同源监督，正是本协议要避免的事"),
    ("unknown or unsupported generator vendor {}", "未知或不支持的生成者厂商 {}"),
    # ---------------------------------------------------------- config.py
    ("generator: unknown keys {}", "generator：未知的键 {}"),
    ("resilience: unknown keys {}", "resilience：未知的键 {}"),
    ("budgets: unknown keys {}", "budgets：未知的键 {}"),
    ("authority: unknown keys {}", "authority：未知的键 {}"),
    ("repair: unknown keys {}", "repair：未知的键 {}"),
    ("{}: unknown keys {}", "{}：未知的键 {}"),
    ("{}.{} is required", "必须设置 {}.{}"),
    ("generator.reasoning_effort must be one of {}",
     "generator.reasoning_effort 必须是 {} 之一"),
    ("{}.reasoning_effort must be one of {}", "{}.reasoning_effort 必须是 {} 之一"),
    ("{}.fallbacks cannot contain nested fallbacks", "{}.fallbacks 不能嵌套 fallbacks"),
    ("generator.fallbacks must be a list", "generator.fallbacks 必须是一个列表"),
    ("{}.fallbacks must be a list", "{}.fallbacks 必须是一个列表"),
    ("generator.fallbacks entries must be mappings",
     "generator.fallbacks 的每一项必须是映射"),
    ("{}.fallbacks entries must be mappings", "{}.fallbacks 的每一项必须是映射"),
    ("{} must be between {} and {}", "{} 必须在 {} 到 {} 之间"),
    ("budgets.{} must be a positive number or null", "budgets.{} 必须是正数或 null"),
    ("no {} found from {} upward — run `crossaudit init`",
     "从 {1} 向上找不到 {0} —— 请运行 `crossaudit init`"),
    ("{} is not valid YAML: {}", "{} 不是有效的 YAML：{}"),
    ("generator must be a mapping", "generator 必须是映射"),
    ("resilience must be a mapping", "resilience 必须是映射"),
    ("budgets must be a mapping", "budgets 必须是映射"),
    ("authority must be a mapping", "authority 必须是映射"),
    ("repair must be a mapping", "repair 必须是映射"),
    ("{} must be a mapping", "{} 必须是映射"),
    ("unknown top-level keys {}", "未知的顶层键 {}"),
    ("config version {} unsupported (expected 1)", "不支持的配置版本 {}（应为 1）"),
    ("{} is required", "必须设置 {}"),
    ("generator.streaming must be true or false", "generator.streaming 必须是 true 或 false"),
    ("isolation.minimum keys must be within {}", "isolation.minimum 的键必须在 {} 之内"),
    ("isolation.minimum values must be booleans", "isolation.minimum 的值必须是布尔值"),
    ("max_rounds must be a positive integer", "max_rounds 必须是正整数"),
    ("state.dir ({}) and ledger.dir ({}) overlap: the state store is gitignored "
     "and the ledger must be committable, so one directory cannot serve both",
     "state.dir（{}）与 ledger.dir（{}）重叠：状态存储被 gitignore 忽略，而账本必须可"
     "提交，因此一个目录不能同时充当两者"),
    ("scope.dirs must be a list of directory names", "scope.dirs 必须是目录名列表"),
    ("resilience.max_backoff_seconds cannot be below initial_backoff_seconds",
     "resilience.max_backoff_seconds 不能小于 initial_backoff_seconds"),
    ("daily token warning cannot exceed the hard limit", "每日 token 警告线不能超过硬上限"),
    ("monthly cost warning cannot exceed the hard limit", "每月费用警告线不能超过硬上限"),
    ("authority.lone_model_blocker must be 'block' (bounded revision, the default) "
     "or 'escalate' (a person decides at round one)",
     "authority.lone_model_blocker 必须是 'block'（受限修订，默认值）或 'escalate'"
     "（第一轮就交由人决定）"),
    ("repair.enabled must be true or false", "repair.enabled 必须是 true 或 false"),
    ("repair.max_changed_lines must be an integer from 1 to 10000",
     "repair.max_changed_lines 必须是 1 到 10000 之间的整数"),
    ("repair.mode must be caution or refuse",
     "repair.mode 必须是 caution（提醒）或 refuse（拒绝）"),
    # ----------------------------------------------------- connections.py
    ("the official Codex runtime returned no safe login URL",
     "官方 Codex 运行时没有返回安全的登录 URL"),
    ("{} does not support connection {}", "{} 不支持连接方式 {}"),
    ("unsupported provider vendor {}", "不支持的厂商 {}"),
    # --------------------------------------------------- console/chats.py
    ("chat navigation state is unreadable: {}", "对话导航状态无法读取：{}"),
    ("chat navigation state has an invalid structure", "对话导航状态的结构无效"),
    ("that chat was deleted; create a new chat", "该对话已删除；请新建对话"),
    ("that chat no longer exists; create a new chat", "该对话已不存在；请新建对话"),
    ("that chat was deleted", "该对话已删除"),
    ("that chat no longer exists", "该对话已不存在"),
    ("that chat has a task running; wait for it to finish before deleting",
     "该对话有任务正在运行；请等它完成后再删除"),
    ("that chat has remote compute running; cancel or finish it first",
     "该对话有远程计算正在运行；请先取消或等它完成"),
    # ------------------------------------------------ console/projects.py
    ("choose the local project folder", "请选择本地项目文件夹"),
    ("projects can only be created inside this workspace", "项目只能在此工作区内创建"),
    ("the saved project setup request is invalid", "已保存的项目创建请求无效"),
    ("the saved project setup operation is unsupported", "已保存的项目创建操作不受支持"),
    ("that project setup task is no longer available", "该项目创建任务已不可用"),
    ("that project setup task is still running", "该项目创建任务仍在运行"),
    ("only a stopped project setup task can be retried", "只有已停止的项目创建任务才能重试"),
    ("the workspace controller for this setup no longer exists",
     "此次创建所属的工作区控制器已不存在"),
    ("Install the GitHub CLI before connecting an account", "连接账户前请先安装 GitHub CLI"),
    ("{} has no supported model catalogue", "{} 没有受支持的模型目录"),
    ("model role must be auditor or generator", "模型角色必须是 auditor 或 generator"),
    ("{} returned no models visible to this key", "{} 没有返回此 key 可见的任何模型"),
    ("runtime role must be auditor or generator", "运行时角色必须是 auditor 或 generator"),
    ("{} has no supported runtime catalogue", "{} 没有受支持的运行时目录"),
    ("model ids contain unsupported characters", "模型 id 含有不支持的字符"),
    ("project guidance requires this project to be a git repository",
     "项目指导要求此项目是 git 仓库"),
    ("guidance names use letters, numbers, hyphens or underscores (60 characters max)",
     "指导名称只能使用字母、数字、短横线或下划线（最多 60 个字符）"),
    ("project guidance cannot be empty", "项目指导不能为空"),
    ("project guidance is larger than {} bytes", "项目指导超过 {} 字节"),
    ("guidance paths must be a comma-separated list", "指导路径必须是以逗号分隔的列表"),
    ("guidance paths must be safe project-relative prefixes",
     "指导路径必须是安全的项目相对路径前缀"),
    ("a guidance path is too long", "某个指导路径过长"),
    ("refusing to edit symlinked project guidance", "拒绝编辑通过符号链接指向的项目指导"),
    ("project guidance has uncommitted changes. Commit or discard that edit, then "
     "retry; the UI will not overwrite it.",
     "项目指导有未提交的更改。请先提交或放弃该编辑，然后重试；界面不会覆盖它。"),
    ("{} must use block-style YAML before the UI can edit it",
     "{} 必须使用块式 YAML，界面才能编辑它"),
    ("{}.model is missing from crossaudit.yml", "crossaudit.yml 中缺少 {}.model"),
    ("{} supports up to 8 fallback routes", "{} 最多支持 8 条备用路由"),
    ("{} fallback routes must be objects", "{} 的备用路由必须是对象"),
    ("unsupported fallback provider {}", "不支持的备用供应商 {}"),
    ("fallback model ids contain unsupported characters", "备用模型 id 含有不支持的字符"),
    ("fallback credential must be primary or backup", "备用凭据必须是 primary 或 backup"),
    ("{} must use block-style YAML before fallbacks can be edited",
     "{} 必须使用块式 YAML，才能编辑备用路由"),
    ("{} must be a positive number", "{} 必须是正数"),
    ("{} must be a number", "{} 必须是数字"),
    ("runtime settings require this project to be a git repository",
     "运行时设置要求此项目是 git 仓库"),
    ("crossaudit.yml has uncommitted changes. Commit or discard that edit, then "
     "retry; the UI will not overwrite it.",
     "crossaudit.yml 有未提交的更改。请先提交或放弃该编辑，然后重试；界面不会覆盖它。"),
    ("maximum rounds must be a number between 1 and 10", "最大轮数必须是 1 到 10 之间的数字"),
    ("maximum rounds must be between 1 and 10", "最大轮数必须在 1 到 10 之间"),
    ("{} does not advertise {} for {}. Choose Automatic or one of {}.",
     "{0} 没有为 {2} 提供 {1}。请选择「自动」或 {3} 之一。"),
    ("{} does not expose an adjustable effort for {}. Choose Automatic.",
     "{} 没有为 {} 提供可调的推理强度。请选择「自动」。"),
    ("maximum retry delay cannot be below the initial delay", "最大重试延迟不能小于首次延迟"),
    ("{} is too long", "{} 过长"),
    ("repository must be owner/name, got {}", "仓库必须写成 owner/name，实际得到 {}"),
    ("Choose folder is available in the CrossAudit macOS app",
     "「选择文件夹」仅在 CrossAudit macOS 应用中可用"),
    ("The application support folder is unavailable", "应用支持文件夹不可用"),
    ("Work and audit repositories must use different names",
     "工作仓库与审计仓库必须使用不同的名称"),
    ("project name may use letters, numbers, dots, dashes and underscores",
     "项目名称只能使用字母、数字、点、短横线和下划线"),
    ("project type must be general or science", "项目类型必须是 general 或 science"),
    ("choose a supported auditor vendor", "请选择受支持的审计者厂商"),
    ("choose a supported generator vendor", "请选择受支持的生成者厂商"),
    ("auditor and generator must use different vendors", "审计者与生成者必须使用不同的厂商"),
    ("Connect {} API key in Settings before creating this project",
     "创建此项目前，请先在设置中连接 {} 的 API key"),
    ("Connect {} subscription in Settings before creating this project",
     "创建此项目前，请先在设置中连接 {} 订阅"),
    # The template the static reader sees (`{'API key' if … else 'subscription'}`
    # is our own conditional literal); never reached, the two forms above sort
    # first. It exists so the reader's rendering has an entry.
    ("Connect {} {} in Settings before creating this project",
     "创建此项目前，请先在设置中连接 {} {}"),
    ("The workspace changed in another window. Review the selected folder and "
     "create the project again.",
     "工作区已在另一个窗口中更改。请重新核对所选文件夹，然后再次创建项目。"),
    ("{} is already a CrossAudit project", "{} 已经是一个 CrossAudit 项目"),
    ("selected local folder uses origin {}, not {}; choose the matching working "
     "repository",
     "所选本地文件夹的 origin 是 {}，而不是 {}；请选择匹配的工作仓库"),
    ("the selected working repository has uncommitted changes; commit or stash "
     "them, then choose Try again. CrossAudit will not alter or discard your work",
     "所选工作仓库有未提交的更改；请先提交或暂存（stash），再选择「重试」。CrossAudit "
     "不会改动或丢弃你的工作"),
    ("the selected project folder is not empty and is not the matching Git "
     "working repository",
     "所选项目文件夹不为空，也不是匹配的 Git 工作仓库"),
    ("maximum audit rounds must be a number", "最大审计轮数必须是数字"),
    ("maximum audit rounds must be between 1 and 10", "最大审计轮数必须在 1 到 10 之间"),
    ("that project is outside this workspace", "该项目不在此工作区内"),
    ("this project has no recoverable GitHub setup", "此项目没有可恢复的 GitHub 设置"),
    ("the failed setup did not record an audit repository", "失败的创建过程没有记录审计仓库"),
    ("that project is outside your selected workspaces", "该项目不在你选定的工作区内"),
    ("return to the main Projects window before deleting the project that is open",
     "请先回到主「项目」窗口，再删除当前打开的项目"),
    ("the CrossAudit application controller cannot be deleted",
     "CrossAudit 应用控制器不能被删除"),
    ("type {} exactly to confirm project deletion", "请准确输入 {} 以确认删除项目"),
    ("this project has no configured working GitHub repository",
     "此项目没有配置工作 GitHub 仓库"),
    ("this project has no configured audit GitHub repository",
     "此项目没有配置审计 GitHub 仓库"),
    ("type DELETE GITHUB to confirm permanent repository deletion",
     "请输入 DELETE GITHUB 以确认永久删除仓库"),
    ("Authorize GitHub repository deletion, then submit this dialog again. "
     "CrossAudit will request only the delete_repo scope through the official "
     "GitHub device flow.",
     "请先授权删除 GitHub 仓库，然后再次提交此对话框。CrossAudit 只会通过官方 GitHub "
     "设备流程申请 delete_repo 范围。"),
    # -------------------------------------------------- console/server.py
    ("the selected PASS carries a signature that does not verify: {}; the receipt "
     "or its signature was altered after it was minted",
     "所选 PASS 的签名无法通过验证：{}；收据或其签名在签发之后被改动过"),
    ("the human continuation cycle id is invalid", "人工继续的周期 id 无效"),
    ("that audit cycle is not waiting for a human-authorized revision",
     "该审计周期并不在等待人工授权的修订"),
    ("the audit cycle belongs to a different chat", "该审计周期属于另一个对话"),
    ("the project no longer descends from the cycle being revised",
     "项目当前状态已不是正在修订的周期的后代"),
    ("project task action must be retry or dismiss", "项目任务操作必须是 retry 或 dismiss"),
    ("project delete action must be preview or delete", "项目删除操作必须是 preview 或 delete"),
    ("unsupported GitHub authorization scope", "不支持的 GitHub 授权范围"),
    ("A loop is running. Model and effort changes apply between provider calls, "
     "so wait for this task to finish and save again.",
     "有循环正在运行。模型与推理强度的更改在两次供应商调用之间生效，请等此任务完成后再保存。"),
    ("A loop is running. Project guidance is captured at the start of a provider "
     "call, so wait for this task to finish and save again.",
     "有循环正在运行。项目指导在供应商调用开始时读取，请等此任务完成后再保存。"),
    ("A loop started while guidance was being saved. Retry when it finishes.",
     "保存指导时有循环启动了。请等它完成后重试。"),
    ("Keychain settings are available in the macOS app", "钥匙串设置仅在 macOS 应用中可用"),
    ("Onboarding is managed by the macOS app", "首次引导由 macOS 应用管理"),
    ("onboarding action must be complete or skip", "首次引导操作必须是 complete 或 skip"),
    ("Application Doctor repairs are available in the macOS app",
     "应用 Doctor 修复仅在 macOS 应用中可用"),
    ("unsupported HPC action", "不支持的 HPC 操作"),
    ("unsupported MCP action", "不支持的 MCP 操作"),
    ("provider login is available in the macOS app", "供应商登录仅在 macOS 应用中可用"),
    ("Credential checks are available in the macOS app", "凭据检查仅在 macOS 应用中可用"),
    ("an approval needs the run it applies to", "批准必须指明它所针对的运行"),
    ("that action is no longer waiting for a decision", "该操作已不再等待决定"),
    ("run action must be cancel", "运行操作必须是 cancel"),
    ("only a provider-failure escalation can be retried directly",
     "只有供应商失败引起的升级才能直接重试"),
    ("the stopped task predates direct retry; copy it into the composer and choose "
     "Revise and continue",
     "该已停止的任务早于直接重试功能；请把它复制到输入框，并选择「修订并继续」"),
    ("there is no interrupted task to recover", "没有可恢复的中断任务"),
    ("the interrupted task was already handled", "该中断任务已经处理过了"),
    ("interrupted task action must be retry or dismiss",
     "中断任务的操作必须是 retry 或 dismiss"),
    # ---------------------------------------------------- constitution.py
    ("rule id {} is not of the form CA-AREA-NNN", "规则 id {} 不符合 CA-AREA-NNN 的格式"),
    ("rule {}: severity must be one of {}", "规则 {}：severity 必须是 {} 之一"),
    ("rule {}: a rule with no criterion is not a rule", "规则 {}：没有判据的规则不是规则"),
    ("a Constitution with no rules cannot audit anything", "没有规则的章程无法审计任何东西"),
    ("duplicate rule id {}", "重复的规则 id {}"),
    ("the drafting model returned an unusable shape: {}", "起草模型返回了无法使用的结构：{}"),
    ("the drafting model returned no JSON object", "起草模型没有返回 JSON 对象"),
    ("the drafting model returned malformed JSON: {}", "起草模型返回了格式错误的 JSON：{}"),
    ("that is too short to draft rules from — say what the project is and what "
     "you are most afraid of getting wrong",
     "这太短了，不足以起草规则——请说明项目是什么，以及你最怕出错的地方"),
    ("an amendment needs an instruction", "修正需要一条指令"),
    ("the amendment produced no changes", "这次修正没有产生任何改动"),
    ("unknown amendment action {}", "未知的修正操作 {}"),
    ("amendment names an invalid rule id {}", "修正指向了无效的规则 id {}"),
    # ------------------------------------------------- controller/state.py
    ("state file is corrupt: {}", "状态文件已损坏：{}"),
    ("state file has no cycles map", "状态文件没有 cycles 映射"),
    ("could not acquire the controller lock; another verifier is mid-transaction",
     "无法获取控制器锁；另一个验证器正处于事务之中"),
    ("unknown continuation cycle", "未知的继续周期"),
    ("continuation cycle belongs to another repository", "要继续的周期属于另一个仓库"),
    ("cycle is {}, not BLOCKED or human-reopened; it cannot accept a build revision",
     "周期状态是 {}，不是 BLOCKED 也未被人工重开；它不能接受构建修订"),
    ("a build revision must create a new commit", "构建修订必须创建新的提交"),
    ("unknown cycle", "未知的周期"),
    ("cycle is {}; it cannot be escalated", "周期状态是 {}；它不能被升级"),
    ("an escalated build must have attempted a round", "被升级的构建必须至少尝试过一轮"),
    ("build escalation cycle has a conflicting sha", "构建升级所属周期的 sha 相互冲突"),
    ("cycle is {}; a recorded verdict cannot be overwritten with an escalation",
     "周期状态是 {}；已记录的判定不能被升级覆盖"),
    ("this cycle is judged against {}, but the round was audited against {}; a "
     "decision cannot name a standard its cycle does not",
     "本周期依据 {} 评判，但这一轮是依据 {} 审计的；决定所引用的标准不能与其周期不一致"),
    ("round {} of this cycle already recorded a verdict; a decision already made "
     "cannot be replaced",
     "本周期第 {} 轮已记录判定；已作出的决定不能被替换"),
    ("cycle status is {}, not PASSED", "周期状态是 {}，不是 PASSED"),
    ("stale: receipt sha {} is not the cycle's active {}",
     "已过期：收据 sha {} 不是该周期当前的 {}"),
    ("receipt already consumed (replay)", "收据已核销（重放）"),
    ("receipt is not the cycle's recorded latest receipt", "该收据不是此周期记录的最新收据"),
    ("unknown resolution {}; use reopen or close", "未知的裁定 {}；请使用 reopen 或 close"),
    ("a resolution must state its reason; it becomes ledger",
     "裁定必须说明理由；它会被记入账本"),
    ("cycle is {}, not ESCALATED; only an escalated cycle needs a human ruling",
     "周期状态是 {}，不是 ESCALATED；只有已升级的周期才需要人工裁决"),
    # --------------------------------------------------------------- dcl/
    ("unknown checks {}; available: {}", "未知的检查 {}；可用的有：{}"),
    ("check pack {} is named in plugins: but is not installed; available: {}",
     "检查包 {} 列在 plugins: 中但未安装；可用的有：{}"),
    ("check pack {} declares dcl api {}, this build speaks {}; refusing rather "
     "than guessing",
     "检查包 {} 声明的 dcl api 是 {}，而本构建使用的是 {}；拒绝执行而非猜测"),
    ("check pack {} exposes no register_checks()", "检查包 {} 没有提供 register_checks()"),
    ("check pack {} has no source file to hash (namespace or frozen import); "
     "refusing to mint a receipt that cannot pin the check code that ran",
     "检查包 {} 没有可供哈希的源文件（命名空间包或打包版中的导入）；拒绝签发无法锁定所运行"
     "检查代码的收据"),
    ("check pack {} source at {} is unreadable ({}); refusing to mint a receipt "
     "that cannot pin the check code that ran",
     "检查包 {} 位于 {} 的源文件无法读取（{}）；拒绝签发无法锁定所运行检查代码的收据"),
    ("unknown check profile {}; choose one of {} or list check names explicitly",
     "未知的检查方案 {}；请从 {} 中选择，或明确列出检查名称"),
    ("checks must be a profile name or a list of check names",
     "checks 必须是方案名称或检查名称列表"),
    # ---------------------------------------------------------- dispute.py
    ("that cycle's report records no findings to dispute",
     "该周期的报告没有记录任何可申辩的发现"),
    ("a dispute needs grounds: say what the auditor misread, and why",
     "申辩需要理由：请说明审计者误读了什么，以及为什么"),
    ("adjudication returned an unusable ruling {}", "裁决返回了无法使用的结论 {}"),
    # -------------------------------------------------- document_export.py
    ("the task contains conflicting document export formats",
     "任务包含相互冲突的文档导出格式"),
    ("document export requires one safe *{} source path",
     "文档导出需要一个安全的 *{} 源路径"),
    ("document export source has no output file name", "文档导出源没有输出文件名"),
    ("{} export requires exactly one temporary Markdown source; the Generator "
     "returned {} files",
     "{} 导出恰好需要一个临时 Markdown 源文件；生成者返回了 {} 个文件"),
    ("temporary export source already exists and will not be overwritten: {}",
     "临时导出源文件已存在，不会被覆盖：{}"),
    ("refusing to overwrite a document not previously generated by CrossAudit: {}",
     "拒绝覆盖并非由 CrossAudit 生成的文档：{}"),
    ("document Markdown contains an unclosed code fence",
     "文档 Markdown 中有未闭合的代码围栏"),
    ("document Markdown table has inconsistent columns",
     "文档 Markdown 表格的列数不一致"),
    ("document export source is empty", "文档导出源为空"),
    ("document export received an unexpected file set", "文档导出收到了意料之外的文件集合"),
    ("document export source contains no readable content", "文档导出源没有可读内容"),
    ("rendered {} failed validation: {}", "渲染出的 {} 未通过校验：{}"),
    ("rendered {} did not preserve enough source text", "渲染出的 {} 没有保留足够的源文本"),
    ("local {} rendering failed: {}: {}", "本地 {} 渲染失败：{}：{}"),
    # ----------------------------------------------------- file_identity.py
    ("could not restore the complete pre-round filesystem state",
     "无法完整还原本轮开始前的文件系统状态"),
    ("could not remove generated round transaction material",
     "无法移除本轮生成的事务材料"),
    # -------------------------------------------------------- generator.py
    ("the generator returned no files; nothing to commit",
     "生成者没有返回任何文件；没有可提交的内容"),
    ("the generator returned an unusable shape: {}", "生成者返回了无法使用的结构：{}"),
    ("the generator returned duplicate file request {}", "生成者返回了重复的文件请求 {}"),
    ("refusing file identities bound to a different project or scope",
     "拒绝绑定到其他项目或范围的文件身份"),
    ("the generator must return exactly one compute request and no files",
     "生成者必须恰好返回一个计算请求，且不带任何文件"),
    ("the compute request envelope must be the entire reply", "计算请求信封必须是整个回复"),
    ("the generator returned invalid compute JSON: {}",
     "生成者返回了无效的计算请求 JSON：{}"),
    ("the generator compute request must be a JSON object",
     "生成者的计算请求必须是 JSON 对象"),
    ("the generator must return exactly one MCP tool request and no other envelope",
     "生成者必须恰好返回一个 MCP 工具请求，且不带其他信封"),
    ("the MCP tool request envelope must be the entire reply",
     "MCP 工具请求信封必须是整个回复"),
    ("the generator returned invalid MCP tool JSON: {}",
     "生成者返回了无效的 MCP 工具请求 JSON：{}"),
    ("the generator MCP tool request must be a JSON object",
     "生成者的 MCP 工具请求必须是 JSON 对象"),
    ("the generator replied in prose instead of the required file envelope",
     "生成者回复的是普通文字，而不是要求的文件信封"),
    ("the generator returned malformed file blocks: the opening file marker is "
     "missing its path",
     "生成者返回了格式错误的文件块：文件起始标记缺少路径"),
    ("the generator needs a task; say what you want built",
     "生成者需要一个任务；请说明你想要构建什么"),
    ("refusing file identities bound to a different project",
     "拒绝绑定到其他项目的文件身份"),
    # ------------------------------------------------------------ gitio.py
    ("git {} did not finish within {}s and was abandoned (a stale index.lock, a "
     "blocking hook, or a credential/GPG prompt can hang git); raise "
     "CROSSAUDIT_GIT_TIMEOUT if this is a legitimately large operation",
     "git {} 在 {} 秒内没有完成，已被放弃（残留的 index.lock、阻塞的钩子或凭据/GPG 提示"
     "都可能让 git 挂起）；如果这确实是一次大型操作，请调高 CROSSAUDIT_GIT_TIMEOUT"),
    ("git {} did not finish within {}s and was abandoned",
     "git {} 在 {} 秒内没有完成，已被放弃"),
    ("git returned an invalid tree entry for committed artifact {}",
     "git 为已提交产物 {} 返回了无效的树条目"),
    ("committed artifact {} does not identify exactly one file in {}",
     "已提交产物 {} 在 {} 中没有对应到恰好一个文件"),
    ("committed artifact {} is not a regular file in {}",
     "已提交产物 {} 在 {} 中不是常规文件"),
    ("could not resolve {} to a full commit sha", "无法把 {} 解析为完整的提交 sha"),
    ("git ls-tree failed: {}", "git ls-tree 失败：{}"),
    ("cannot read blob {}", "无法读取 blob {}"),
    ("increment contains a symlink: {}", "增量中含有符号链接：{}"),
    ("increment contains a submodule: {}", "增量中含有子模块：{}"),
    # -------------------------------------------------------------- hpc.py
    ("{} must be an absolute normalized POSIX path", "{} 必须是绝对且规范化的 POSIX 路径"),
    ("output path is not a safe relative path", "输出路径不是安全的相对路径"),
    ("{} must be a whole number", "{} 必须是整数"),
    ("wall time must look like HH:MM:SS or D-HH:MM:SS",
     "运行时限必须写成 HH:MM:SS 或 D-HH:MM:SS"),
    ("memory must look like 16G, 8000M, or 1T", "内存必须写成 16G、8000M 或 1T 这样的形式"),
    ("SSH alias must start with a letter, number, dot or underscore; the remaining "
     "characters may also include dashes",
     "SSH 别名必须以字母、数字、点或下划线开头；其余字符还可以包含短横线"),
    ("HPC input must be a regular local file", "HPC 输入必须是本地常规文件"),
    ("that compute host is not registered in this project", "该计算主机未注册在此项目中"),
    ("invalid compute job identifier", "无效的计算作业标识符"),
    ("that compute job does not exist", "该计算作业不存在"),
    ("host details must be at most {} characters", "主机详情最多 {} 个字符"),
    ("Generator {} contains unsupported characters", "生成者 {} 含有不支持的字符"),
    ("cancel or finish this host's active jobs before removing it",
     "移除此主机前，请先取消或完成它上面正在运行的作业"),
    ("that compute host is not registered", "该计算主机未注册"),
    ("job name may use letters, numbers, spaces, dots, dashes and underscores",
     "作业名称只能使用字母、数字、空格、点、短横线和下划线"),
    ("{} contains unsupported characters", "{} 含有不支持的字符"),
    ("job script is required", "必须提供作业脚本"),
    ("job script must be at most {} UTF-8 bytes", "作业脚本最多 {} 个 UTF-8 字节"),
    ("the latest host probe did not find Slurm sbatch", "最近一次主机探测没有找到 Slurm sbatch"),
    ("this host has reached its configured concurrent job limit",
     "此主机已达到配置的并发作业上限"),
    ("this workstation does not provide setsid, so CrossAudit cannot guarantee "
     "that a detached process and its children can be managed safely",
     "此工作站不提供 setsid，因此 CrossAudit 无法保证能安全管理分离进程及其子进程"),
    ("Generator compute inputs must be a list of project paths",
     "生成者的计算输入必须是项目路径列表"),
    ("Generator compute input {} is outside project work scope",
     "生成者的计算输入 {} 在项目工作范围之外"),
    ("Generator compute input escapes the project", "生成者的计算输入越出了项目"),
    ("Generator compute input {} resolves outside project work scope",
     "生成者的计算输入 {} 解析到了项目工作范围之外"),
    ("Generator compute input {} is not a regular file",
     "生成者的计算输入 {} 不是常规文件"),
    ("Generator compute inputs must have unique file names",
     "生成者的计算输入文件名必须唯一"),
    ("Generator compute request must be an object", "生成者的计算请求必须是一个对象"),
    ("this host is not enabled as an automatic Generator compute tool",
     "此主机未启用为生成者的自动计算工具"),
    ("the Generator reached this host's automatic jobs-per-task limit",
     "生成者已达到此主机的每任务自动作业上限"),
    ("Generator compute outputs must be a list of relative paths",
     "生成者的计算输出必须是相对路径列表"),
    ("Generator compute output paths must be unique", "生成者的计算输出路径必须唯一"),
    ("Generator requested {} {}; this host allows {}",
     "生成者请求了 {} {}；此主机允许 {}"),
    ("Generator memory request exceeds this host's policy",
     "生成者请求的内存超出了此主机的策略"),
    ("Generator wall time exceeds this host's policy",
     "生成者请求的运行时限超出了此主机的策略"),
    ("stored remote job identifier is invalid", "已保存的远程作业标识符无效"),
    ("remote output is not a regular file", "远程输出不是常规文件"),
    # ------------------------------------------------------ ledger/chain.py
    ("evidence payload must be a mapping", "证据载荷必须是映射"),
    ("evidence kind must be a non-empty string", "证据类型必须是非空字符串"),
    ("the evidence ledger is locked by another writer", "证据账本已被另一个写入者锁定"),
    # -------------------------------------------------------------- mcp.py
    ("{} must be valid JSON", "{} 必须是有效的 JSON"),
    ("{} exceeds the {}-byte safety limit", "{} 超出了 {} 字节的安全上限"),
    ("MCP server returned HTTP {}", "MCP 服务器返回了 HTTP {}"),
    ("MCP calls per task must be between 1 and {}", "MCP 每任务调用次数必须在 1 到 {} 之间"),
    # The MCP refusals below already have console entries; the Chinese is the
    # console's, verbatim, so the two surfaces never disagree on a sentence.
    ("Generator MCP request must be an object", "生成者的 MCP 请求必须是一个对象"),
    ("MCP URL must be a plain HTTP(S) endpoint without credentials, query or fragment",
     "MCP URL 必须是不含凭据、查询串或片段的纯 HTTP(S) 端点"),
    ("MCP {} failed: {}", "MCP {} 失败：{}"),
    ("MCP {} returned an invalid result", "MCP {} 返回了无效结果"),
    ("MCP arguments are unexpectedly large", "MCP 参数过大"),
    ("MCP arguments must be a list", "MCP 参数必须是一个列表"),
    ("MCP bearer token contains control characters", "MCP bearer token 含有控制字符"),
    ("MCP bearer token is empty or unexpectedly large", "MCP bearer token 为空或过大"),
    ("MCP calls per task must be a whole number", "MCP 每任务调用次数必须是整数"),
    ("MCP endpoint redirects are refused; register the final HTTPS URL",
     "MCP 端点重定向会被拒绝；请直接登记最终的 HTTPS 地址"),
    ("MCP event stream ended without the requested response",
     "MCP 事件流在返回所请求的响应前已结束"),
    ("MCP executable {} was not found or is not executable",
     "未找到 MCP 可执行文件 {}，或它不可执行"),
    ("MCP executable is required", "必须填写 MCP 可执行文件"),
    ("MCP request timed out", "MCP 请求超时"),
    ("MCP server advertised an invalid tool", "MCP 服务器公布了无效的工具"),
    ("MCP server advertised more than 1000 tools", "MCP 服务器公布了超过 1000 个工具"),
    ("MCP server connection failed: {}", "MCP 服务器连接失败：{}"),
    ("MCP server could not start: {}", "MCP 服务器无法启动：{}"),
    ("MCP server name uses unsupported characters", "MCP 服务器名称包含不支持的字符"),
    ("MCP server negotiated unsupported protocol {}", "MCP 服务器协商了不受支持的协议 {}"),
    ("MCP server requires authorization. Add a valid bearer token; interactive MCP "
     "OAuth is not configured for this server.",
     "MCP 服务器需要授权。请添加有效的 bearer token；此服务器未配置交互式 MCP OAuth。"),
    ("MCP server response exceeded the safety limit", "MCP 服务器响应超出安全上限"),
    ("MCP server returned a non-object JSON-RPC message",
     "MCP 服务器返回了非对象的 JSON-RPC 消息"),
    ("MCP server returned an invalid pagination cursor", "MCP 服务器返回了无效的分页游标"),
    ("MCP server returned invalid JSON", "MCP 服务器返回了无效的 JSON"),
    ("MCP server settings must be an object", "MCP 服务器设置必须是一个对象"),
    ("MCP server wrote non-JSON data to stdout", "MCP 服务器向标准输出写入了非 JSON 数据"),
    ("MCP timeout must be a whole number", "MCP 超时必须是整数"),
    ("MCP timeout must be between 1 and 300 seconds", "MCP 超时必须在 1 到 300 秒之间"),
    ("MCP tool arguments must be an object", "MCP 工具参数必须是一个对象"),
    ("MCP tools/list returned an invalid tool list", "MCP tools/list 返回了无效的工具列表"),
    ("MCP transport must be stdio or Streamable HTTP",
     "MCP 传输方式必须是 stdio 或 Streamable HTTP"),
    ("allowed MCP tools must be a list", "允许的 MCP 工具必须是一个列表"),
    ("an MCP argument is invalid or too long", "某个 MCP 参数无效或过长"),
    ("an allowed MCP tool is not advertised by this server",
     "某个已允许的 MCP 工具并未由此服务器公布"),
    ("approve the exact local MCP command before it runs",
     "请先批准将要运行的这条本地 MCP 命令"),
    ("connect the MCP server without Generator access first, review the advertised "
     "tool list, then configure and enable it",
     "请先在不开放生成者访问的情况下连接 MCP 服务器，复核其公布的工具列表，然后再配置并启用它"),
    ("invalid MCP server identifier", "无效的 MCP 服务器标识符"),
    ("macOS Keychain is unavailable for the MCP credential",
     "无法使用 macOS 钥匙串保存 MCP 凭据"),
    ("macOS Keychain refused the MCP credential: {}", "macOS 钥匙串拒绝了 MCP 凭据：{}"),
    ("remote MCP servers require HTTPS; HTTP is allowed only on loopback",
     "远程 MCP 服务器必须使用 HTTPS；仅回环地址允许使用 HTTP"),
    ("select at least one MCP tool before enabling Generator access",
     "启用生成者访问前，请至少选择一个 MCP 工具"),
    ("that MCP server is not registered in this project", "该 MCP 服务器未注册在此项目中"),
    ("the Generator reached this MCP server's calls-per-task limit",
     "生成者已达到此 MCP 服务器的每任务调用上限"),
    ("the MCP hostname could not be resolved", "无法解析该 MCP 主机名"),
    ("the MCP hostname resolves to a private or reserved address; enable "
     "private-network access only for a verified enterprise server",
     "该 MCP 主机名解析到专用或保留地址；请仅对已核实的企业服务器启用专用网络访问"),
    ("this MCP server is not enabled for the Generator", "此 MCP 服务器未对生成者启用"),
    ("this MCP tool is not approved for automatic use", "此 MCP 工具未被批准自动使用"),
    # --------------------------------------------------------- providers/
    ("unexpected Anthropic response shape: {}", "Anthropic 返回了意料之外的响应结构：{}"),
    ("Anthropic returned an empty completion", "Anthropic 返回了空回复"),
    ("provider stopped sending before the response body completed within the time "
     "budget",
     "供应商在时间预算内未发送完响应正文就停止了"),
    ("provider response exceeded the size cap", "供应商响应超出了大小上限"),
    ("provider attempted a redirect to {}; refused (a redirect can move a key to "
     "another host)",
     "供应商试图重定向到 {}；已拒绝（重定向可能把密钥送到另一台主机）"),
    ("provider endpoint {} is not an absolute URL", "供应商端点 {} 不是绝对 URL"),
    ("refusing plaintext {}:// to {}; only HTTPS is allowed (loopback needs "
     "--allow-insecure-localhost)",
     "拒绝以明文 {}:// 访问 {}；只允许 HTTPS（回环地址需要 --allow-insecure-localhost）"),
    ("endpoint {} is not this provider's built-in origin ({}); pass "
     "--allow-custom-endpoint to send a key there",
     "端点 {} 不是此供应商的内置源（{}）；要把密钥发到那里，请传入 --allow-custom-endpoint"),
    ("provider returned non-JSON: {}", "供应商返回了非 JSON 内容：{}"),
    ("provider unreachable: {}", "无法连接供应商：{}"),
    ("${} is not set in this process, though {} has it. Load it with `source {}`, "
     "or restart whatever is running so it picks the file up",
     "当前进程没有设置 ${}，但 {} 里有它。请用 `source {}` 加载，或重启正在运行的程序让它"
     "读取该文件"),
    ("no API key in ${}. Run `crossaudit init` to store one, or export it yourself "
     "— it never goes in crossaudit.yml",
     "${} 中没有 API key。请运行 `crossaudit init` 保存一个，或自行 export——它绝不会写进 "
     "crossaudit.yml"),
    ("ChatGPT subscription access needs the official Codex runtime. Install Codex "
     "or use the CrossAudit macOS app, which bundles it.",
     "使用 ChatGPT 订阅需要官方 Codex 运行时。请安装 Codex，或使用内置了它的 CrossAudit "
     "macOS 应用。"),
    ("could not start the official Codex runtime: {}", "无法启动官方 Codex 运行时：{}"),
    ("the official Codex runtime is not running", "官方 Codex 运行时没有在运行"),
    ("the official Codex runtime connection closed", "与官方 Codex 运行时的连接已关闭"),
    ("the official Codex runtime did not answer {} in time",
     "官方 Codex 运行时没有及时响应 {}"),
    ("the official Codex runtime refused {}: {}", "官方 Codex 运行时拒绝了 {}：{}"),
    ("the official Codex runtime returned an unexpected login origin",
     "官方 Codex 运行时返回了意料之外的登录源"),
    ("the official Codex runtime returned no thread id",
     "官方 Codex 运行时没有返回 thread id"),
    ("ChatGPT subscription completion timed out", "ChatGPT 订阅回复超时"),
    ("ChatGPT subscription access uses the official Codex service and cannot be "
     "redirected to a custom endpoint",
     "ChatGPT 订阅访问使用官方 Codex 服务，不能重定向到自定义端点"),
    ("Sign in with ChatGPT in Settings before refreshing models",
     "刷新模型前，请先在设置中使用 ChatGPT 登录"),
    ("ChatGPT returned no Codex models for this subscription",
     "ChatGPT 没有为此订阅返回任何 Codex 模型"),
    ("Sign in with ChatGPT in Settings before reading model options",
     "读取模型选项前，请先在设置中使用 ChatGPT 登录"),
    ("provider returned invalid UTF-8 in completion stream: {}",
     "供应商在回复流中返回了无效的 UTF-8：{}"),
    ("provider returned malformed completion stream data: {}",
     "供应商返回了格式错误的回复流数据：{}"),
    ("provider returned a non-object completion stream event",
     "供应商返回了非对象的回复流事件"),
    ("provider returned non-text completion stream content",
     "供应商返回了非文本的回复流内容"),
    ("provider completion stream ended without a terminal marker",
     "供应商的回复流在没有结束标记的情况下结束了"),
    ("provider returned an empty completion", "供应商返回了空回复"),
    ("unexpected chat-completions response shape: {}",
     "chat-completions 返回了意料之外的响应结构：{}"),
    ("unknown provider {}; available: {}", "未知的供应商 {}；可用的有：{}"),
    ("provider 'replay' needs ${} pointing at a transcript directory",
     "供应商 'replay' 需要 ${} 指向一个对话记录目录"),
    ("${} is not a directory: {}", "${} 不是目录：{}"),
    ("no recorded reply for this exact prompt ({}); the transcript cannot answer a "
     "question it was not asked",
     "没有为这条提示（{}）录制的回复；对话记录无法回答它未被问过的问题"),
    ("this project selected a human generator: make and commit the change, then "
     "run `crossaudit run`",
     "此项目选择了由人担任生成者：请自行完成并提交更改，然后运行 `crossaudit run`"),
    ("the generator provider and model must be configured", "必须配置生成者的供应商和模型"),
    # The role is our own word (generator / auditor); the specific forms sort
    # first, the `{}` forms exist for the static reader's rendering.
    ("all configured generator provider routes are cooling down; retry in {}s",
     "已配置的所有生成者供应商路由都在冷却中；请在 {} 秒后重试"),
    ("all configured auditor provider routes are cooling down; retry in {}s",
     "已配置的所有审计者供应商路由都在冷却中；请在 {} 秒后重试"),
    ("all configured {} provider routes are cooling down; retry in {}s",
     "已配置的所有 {} 供应商路由都在冷却中；请在 {} 秒后重试"),
    # The summary after the full stop is `vendor:model — first line of the
    # route's own refusal`, `; `-joined: a COMPOSITE, so each route's reason
    # is translated in turn and the route id is carried through.
    ("all configured generator provider routes failed. {}",
     "已配置的所有生成者供应商路由都失败了。{}"),
    ("all configured auditor provider routes failed. {}",
     "已配置的所有审计者供应商路由都失败了。{}"),
    ("all configured {} provider routes failed. {}",
     "已配置的所有 {} 供应商路由都失败了。{}"),
    ("{} credential ${} is not configured", "未配置 {} 凭据 ${}"),
    # cli/build.py wraps the round's provider refusal for the ledger and the
    # Decision Center: "<role> provider failure in round N: <refusal>". The
    # keyless first run, spelled out in full so it can never be answered by
    # a generic template; then the composite prefix for every other refusal.
    ("generator provider failure in round {}: all configured generator provider "
     "routes failed. {} — {} credential ${} is not configured",
     "生成者在第 {} 轮失败：已配置的所有生成者供应商路由都失败了。{} — 未配置 {} 凭据 ${}"),
    ("auditor provider failure in round {}: all configured auditor provider "
     "routes failed. {} — {} credential ${} is not configured",
     "审计者在第 {} 轮失败：已配置的所有审计者供应商路由都失败了。{} — 未配置 {} 凭据 ${}"),
    ("generator provider failure in round {}: {}", "生成者在第 {} 轮失败：{}"),
    ("auditor provider failure in round {}: {}", "审计者在第 {} 轮失败：{}"),
    # ----------------------------------------------------- receipt/build.py
    # Raised through a constant (`f"{EVIDENCE_BROKEN_REASON}: {reason}"`), so
    # the static reader sees only `{}: {}`; this is the sentence a person meets.
    ("the evidence ledger for this project is present and does not verify, so a "
     "receipt cannot be signed for it: omitting the block would state, over a "
     "valid signature, that this audit used no tools: {}",
     "此项目的证据账本存在但无法通过验证，因此无法为它签署收据：省略该区块就等于在有效"
     "签名之下声称本次审计没有使用任何工具：{}"),
    # ---------------------------------------------------- receipt/schema.py
    ("receipt {} is missing {}", "收据 {} 缺少 {}"),
    ("receipt is not a JSON object", "收据不是 JSON 对象"),
    ("receipt has no receipt_schema; pre-v2 receipts are inspectable with "
     "--legacy-inspect but are never admissible",
     "收据没有 receipt_schema；v2 之前的收据可以用 --legacy-inspect 查看，但永远不能准入"),
    ("receipt schema {} is not supported by this verifier (expects {})",
     "此验证器不支持收据 schema {}（需要 {}）"),
    ("verdict {} is not one of {}", "判定 {} 不是 {} 之一"),
    ("retention mode must be one of {}", "留存模式必须是 {} 之一"),
    ("subject.sha must be a full 40-character commit sha",
     "subject.sha 必须是完整的 40 位提交 sha"),
    ("inputs.manifest must be a mapping of path to digest",
     "inputs.manifest 必须是路径到摘要的映射"),
    ("isolation must be a mapping", "isolation 必须是映射"),
    ("isolation.{} must be present and boolean", "isolation.{} 必须存在且为布尔值"),
    ("isolation.{} evidence is missing", "缺少 isolation.{} 的证据"),
    ("tool_evidence must be a mapping", "tool_evidence 必须是映射"),
    ("tool_evidence.ledger_head must be a non-empty string",
     "tool_evidence.ledger_head 必须是非空字符串"),
    ("tool_evidence.entries must be a positive integer", "tool_evidence.entries 必须是正整数"),
    ("reproduction must be a mapping", "reproduction 必须是映射"),
    ("reproduction.bundle_sha256 must be a non-empty string",
     "reproduction.bundle_sha256 必须是非空字符串"),
    ("reproduction.locks must be a positive integer", "reproduction.locks 必须是正整数"),
    ("reproduction.lock_kinds must be a list", "reproduction.lock_kinds 必须是列表"),
    ("sources must be a mapping", "sources 必须是映射"),
    ("sources.set_sha256 must be a non-empty string", "sources.set_sha256 必须是非空字符串"),
    ("sources.count must be a positive integer", "sources.count 必须是正整数"),
    ("sources.origins must be a list", "sources.origins 必须是列表"),
    ("sources present without tool_evidence to bind it",
     "存在 sources 却没有绑定它的 tool_evidence"),
    ("authority workflow verdict {} differs from audit verdict {}",
     "收据 authority 区块的工作流判定 {} 与审计判定 {} 不一致"),
    # ---------------------------------------------------- receipt/verify.py
    ("skill {} is {} bytes, over the {}-byte limit skills.load enforces",
     "技能 {} 有 {} 字节，超过了 skills.load 强制的 {} 字节上限"),
    ("the committed skills total more than {} bytes", "已提交的技能总量超过 {} 字节"),
    ("skill {} is not UTF-8: {}", "技能 {} 不是 UTF-8：{}"),
    ("receipt unreadable: {}", "收据无法读取：{}"),
    ("evidence ledger failed re-derivation: {}", "证据账本重新推导失败：{}"),
    ("receipt tool_evidence head does not match the evidence ledger",
     "收据的 tool_evidence 头与证据账本不匹配"),
    ("cycle-bound receipt verification needs the project's controller state",
     "验证绑定周期的收据需要项目的控制器状态"),
    ("receipt cycle is absent from the controller state", "控制器状态中没有该收据的周期"),
    ("receipt cycle does not match its pinned constitution", "收据的周期与其锁定的章程不匹配"),
    ("receipt verdict is not recorded for its cycle round",
     "收据的判定未记录在其周期的对应轮次中"),
    ("receipt is not the controller's recorded verdict", "该收据不是控制器记录的判定"),
    ("science_repo {} != expected {}", "science_repo 是 {}，与预期的 {} 不符"),
    ("receipt sha {} != expected {}", "收据 sha 是 {}，与预期的 {} 不符"),
    ("audited commit is not in the science repository", "受审的提交不在科学仓库中"),
    ("science tree {} != receipt tree {}", "科学仓库的树 {} 与收据中的树 {} 不符"),
    ("manifest says ABSENT but {} is in the tree", "清单标记为 ABSENT，但 {} 在树中存在"),
    ("manifest lists {}, absent from the tree", "清单列出了 {}，但树中没有它"),
    ("manifest mismatch for {}", "{} 与清单不匹配"),
    ("receipt declares the constitution unversioned", "收据声明章程未受版本控制"),
    ("constitution content differs from the receipt's hash", "章程内容与收据中的哈希不一致"),
    ("report missing at {}/report.md", "{}/report.md 处缺少报告"),
    ("report blob hash mismatch", "报告 blob 哈希不匹配"),
    ("bound report has no machine-readable verdict row", "绑定的报告没有机器可读的判定行"),
    ("receipt verdict {} differs from bound report verdict {}",
     "收据判定 {} 与绑定报告的判定 {} 不一致"),
    ("bound report has no evidence-route row", "绑定的报告没有证据路由行"),
    ("receipt evidence route {} differs from bound report route {}",
     "收据的证据路由 {} 与绑定报告的路由 {} 不一致"),
    ("cycle directory {} does not belong to {}", "周期目录 {} 不属于 {}"),
    ("report commit is not an ancestor of the audit head", "报告提交不是审计仓库 head 的祖先"),
    ("report commit named by the receipt is not in the audit repo",
     "收据指名的报告提交不在审计仓库中"),
    ("reproduction bundle digest does not match the receipt", "复现包摘要与收据不匹配"),
    ("reproduction lock count does not match the audited manifest",
     "复现锁数量与受审清单不匹配"),
    ("receipt claims governed sources but none re-derive from the evidence ledger",
     "收据声称有受管来源，但没有任何一个能从证据账本重新推导出来"),
    ("governed-source set does not match the evidence ledger", "受管来源集合与证据账本不匹配"),
    ("verdict is {}, not PASS — nothing to admit", "判定是 {}，不是 PASS——没有可准入的内容"),
    ("audit integrity: {}", "审计完整性：{}"),
    ("bound report names an evidence route this verifier does not know: {}",
     "绑定的报告指明了一个此验证器不认识的证据路由：{}"),
    ("isolation evidence is weaker than this deployment requires: missing {}",
     "隔离证据弱于此部署的要求：缺少 {}"),
    ("install mode {} may verify but never admit: its code can change under the "
     "digest it reports",
     "安装模式 {} 可以验证但永远不能准入：它的代码可能在它所报告的摘要之下被改动"),
    ("the verifier that minted this receipt is not the one admitting it; re-verify "
     "with the recorded version before admitting",
     "签发此收据的验证器与准入它的不是同一个；请先用记录的版本重新验证，再准入"),
    # ------------------------------------------------------------ router.py
    ("router returned an unknown lane {}", "路由器返回了未知的通道 {}"),
    ("name a recipient and include the instruction after it",
     "请指明接收方，并在其后写上指令"),
    # --------------------------------------------------- runtime/workspaces
    ("workspace runtime manager is busy; retry shortly", "工作区运行时管理器正忙；请稍后重试"),
    ("this project already owns a workspace build slot", "此项目已占有一个工作区构建槽位"),
    ("workspace build capacity is {}; wait for {}", "工作区构建容量为 {}；请等 {} 完成"),
    # ------------------------------------------------------------ skills.py
    ("refusing a symlinked skill: {}", "拒绝通过符号链接指向的技能：{}"),
    ("skill {} is {} bytes (limit {}); a skill is guidance, and one this long "
     "crowds out the work itself",
     "技能 {} 有 {} 字节（上限 {}）；技能是指导，这么长会挤占工作本身"),
    ("the skills total more than {} bytes; trim them, or scope them with "
     "applies_to so each round loads only what it needs",
     "技能总量超过 {} 字节；请精简它们，或用 applies_to 限定范围，让每一轮只加载所需的部分"),
    # --------------------------------------------------------- workspace.py
    ("CrossAudit could not save the setup state. Check access to the application "
     "support folder and try again",
     "CrossAudit 无法保存设置状态。请检查应用支持文件夹的访问权限后重试"),
    ("Choose a local folder for CrossAudit projects", "请为 CrossAudit 项目选择一个本地文件夹"),
    ("That workspace folder no longer exists; choose it again",
     "该工作区文件夹已不存在；请重新选择"),
    ("The selected workspace is not a folder", "所选工作区不是文件夹"),
    ("CrossAudit cannot read and write the selected folder. Choose another folder "
     "or grant your account access in Finder",
     "CrossAudit 无法读写所选文件夹。请选择其他文件夹，或在 Finder 中为你的账户授予访问权限"),
    ("CrossAudit could not create a project in that folder. Choose a writable "
     "folder or update its Finder permissions",
     "CrossAudit 无法在该文件夹中创建项目。请选择可写的文件夹，或更新它在 Finder 中的权限"),
    ("CrossAudit could not save the workspace choice. Check access to the "
     "application support folder and try again",
     "CrossAudit 无法保存工作区选择。请检查应用支持文件夹的访问权限后重试"),
    # -------------------------------------------- console/server.py (admit)
    ("the selected PASS receipt is missing — no receipt file was minted for this "
     "cycle (sample data never mints one)",
     "所选 PASS 的收据缺失——本周期没有签发任何收据文件（示例数据从不签发收据）"),
    ("there is no unconsumed passing result to admit", "没有尚未核销的 PASS 结果可供准入"),
    # ------------------------------------------------- broker/routing.py
    # D130's one string, as the console carries it: the verifier's reason is
    # carried through after the colon rather than swallowed.
    ("evidence ledger cannot be shown to the Auditor: {}", "证据账本无法出示给审计者：{}"),
    # ================================================================
    # Review round 2: the Denial SUBCLASSES (ToolError, TokenError,
    # LedgerError, SSHFailure), the reasons assembled from a constant or a
    # variable, and the specific sentences that a generic template would
    # otherwise half-translate.
    # ================================================================
    # ------------------------------------------ broker/ (ToolError)
    ("self-installation is not permitted; a candidate build is reviewed by the "
     "independent auditor and installed only by the user",
     "不允许自行安装；候选构建由独立审计者复核，且只能由用户安装"),
    ("run_check needs 'command' as a non-empty list of argv strings",
     "run_check 需要 'command'：一个非空的 argv 字符串列表"),
    ("command {} is not in this project's allowed commands",
     "命令 {} 不在此项目允许的命令列表中"),
    ("command could not run: {}", "命令无法运行：{}"),
    ("path {} is outside the grant", "路径 {} 超出了授权范围"),
    ("git_commit needs a non-empty 'message'", "git_commit 需要非空的 'message'"),
    ("commit refused: the staged changes appear to contain {}; remove the secret "
     "(or add the file to .gitignore) and try again",
     "提交被拒绝：暂存的更改似乎含有{}；请移除该机密（或把文件加入 .gitignore）后重试"),
    ("repo_create needs a 'name'", "repo_create 需要 'name'"),
    ("hpc_status needs a 'job_id'", "hpc_status 需要 'job_id'"),
    ("hpc_output needs a 'job_id'", "hpc_output 需要 'job_id'"),
    ("hpc_submit needs a non-empty 'manifest'", "hpc_submit 需要非空的 'manifest'"),
    ("mcp_call needs a request with 'server_id' and 'tool'",
     "mcp_call 需要包含 'server_id' 和 'tool' 的请求"),
    ("this tool needs a 'path' argument", "此工具需要 'path' 参数"),
    ("{} is not in the committed tree", "{} 不在已提交的树中"),
    ("this tool needs a 'query' argument", "此工具需要 'query' 参数"),
    ("the hostname {} resolves to a private or reserved address; only public web "
     "hosts can be fetched",
     "主机名 {} 解析到专用或保留地址；只能抓取公网主机"),
    ("the hostname {} could not be resolved", "无法解析主机名 {}"),
    ("web_fetch needs a plain public https:// URL without credentials or fragment",
     "web_fetch 需要不含凭据和片段的纯公网 https:// URL"),
    ("the server answered HTTP {}", "服务器返回了 HTTP {}"),
    ("the fetch failed: {}", "抓取失败：{}"),
    ("the response exceeded the 5 MiB fetch cap", "响应超出了 5 MiB 的抓取上限"),
    ("the service returned malformed JSON", "服务返回了格式错误的 JSON"),
    ("the service returned an unexpected JSON shape", "服务返回了意料之外的 JSON 结构"),
    ("arXiv returned malformed XML", "arXiv 返回了格式错误的 XML"),
    ("paper_search needs a non-empty 'query'", "paper_search 需要非空的 'query'"),
    ("unknown source {}; choose one of {}", "未知的来源 {}；请从 {} 中选择"),
    ("the PDF could not be parsed", "无法解析该 PDF"),
    ("file_write needs a 'path' argument", "file_write 需要 'path' 参数"),
    ("file_write 'content' must be a string", "file_write 的 'content' 必须是字符串"),
    ("content exceeds the {}-byte write limit", "内容超出了 {} 字节的写入上限"),
    ("path {} escapes the workspace", "路径 {} 越出了工作区"),
    ("old_string was not found; it must match the file exactly, whitespace and all "
     "(read the file first)",
     "找不到 old_string；它必须与文件内容完全一致，包括空白字符（请先读取文件）"),
    ("old_string matches {} places; make it unique with more surrounding context, "
     "or pass replace_all=true",
     "old_string 匹配到 {} 处；请加入更多上下文使其唯一，或传入 replace_all=true"),
    ("file_edit needs a 'path' argument", "file_edit 需要 'path' 参数"),
    ("file_edit needs string 'old_string' and 'new_string'",
     "file_edit 需要字符串类型的 'old_string' 和 'new_string'"),
    ("file_edit 'old_string' and 'new_string' are identical",
     "file_edit 的 'old_string' 与 'new_string' 相同"),
    ("file_edit 'old_string' must not be empty", "file_edit 的 'old_string' 不能为空"),
    ("file {} does not exist; use file_write to create it",
     "文件 {} 不存在；请用 file_write 创建它"),
    ("file {} could not be read as UTF-8 text: {}", "文件 {} 无法作为 UTF-8 文本读取：{}"),
    ("the edited file exceeds the {}-byte limit", "编辑后的文件超出了 {} 字节上限"),
    # ------------------------------------------ policy/tokens.py (TokenError)
    ("a capability token needs a project_id and run_id", "能力令牌需要 project_id 和 run_id"),
    ("a capability token must be a mapping", "能力令牌必须是映射"),
    ("invalid path pattern in token: {}", "令牌中的路径模式无效：{}"),
    ("unparseable token expiry: {}", "无法解析的令牌过期时间：{}"),
    ("unknown token fields: {}", "未知的令牌字段：{}"),
    # ------------------------------------------ ledger/chain.py (LedgerError)
    ("the evidence ledger has an incomplete final entry (a crash left a torn tail); "
     "refusing to append onto a damaged chain until it is recovered",
     "证据账本的最后一条记录不完整（崩溃留下了残缺的尾部）；在恢复之前拒绝向受损的链上追加记录"),
    # ------------------------------------------ hpc.py (SSHFailure and labels)
    ("This host is not trusted yet. Verify the hostname, then choose Trust first "
     "key & connect. CrossAudit will use OpenSSH trust-on-first-use.",
     "此主机尚未受信任。请核实主机名，然后选择「信任首个密钥并连接」。CrossAudit 将使用 "
     "OpenSSH 的首次使用信任机制。"),
    ("The saved SSH host key changed. CrossAudit will not replace it. Contact the "
     "cluster administrator and repair known_hosts outside the app.",
     "已保存的 SSH 主机密钥发生了变化。CrossAudit 不会替换它。请联系集群管理员，并在应用之外"
     "修复 known_hosts。"),
    ("SSH authentication was refused. Add the correct key to ssh-agent or fix "
     "IdentityFile/User in ~/.ssh/config.",
     "SSH 认证被拒绝。请把正确的密钥加入 ssh-agent，或修正 ~/.ssh/config 中的 IdentityFile/User。"),
    ("The SSH hostname could not be resolved. Check the alias and any ProxyJump "
     "entry in ~/.ssh/config.",
     "无法解析 SSH 主机名。请检查 ~/.ssh/config 中的别名和 ProxyJump 条目。"),
    ("The SSH connection timed out. Connect the required VPN and retry.",
     "SSH 连接超时。请连接所需的 VPN 后重试。"),
    ("The SSH host is unreachable from this Mac.", "从这台 Mac 无法访问该 SSH 主机。"),
    ("OpenSSH could not connect to the host", "OpenSSH 无法连接到该主机"),
    ("OpenSSH was not found on this computer", "此电脑上找不到 OpenSSH"),
    ("OpenSSH could not resolve that host alias", "OpenSSH 无法解析该主机别名"),
    ("The remote operation timed out", "远程操作超时"),
    ("The remote input transfer timed out", "远程输入传输超时"),
    ("the remote scheduler returned an invalid job identifier",
     "远程调度器返回了无效的作业标识符"),
    ("remote path must be an absolute normalized POSIX path",
     "远程路径必须是绝对且规范化的 POSIX 路径"),
    ("remote input path must be an absolute normalized POSIX path",
     "远程输入路径必须是绝对且规范化的 POSIX 路径"),
    ("scratch directory must be an absolute normalized POSIX path",
     "临时目录必须是绝对且规范化的 POSIX 路径"),
    ("concurrent job limit must be a whole number", "并发作业上限必须是整数"),
    ("concurrent job limit must be between {} and {}", "并发作业上限必须在 {} 到 {} 之间"),
    ("Generator jobs per task must be a whole number", "生成者每任务作业数必须是整数"),
    ("Generator jobs per task must be between {} and {}",
     "生成者每任务作业数必须在 {} 到 {} 之间"),
    ("Generator node limit must be a whole number", "生成者节点上限必须是整数"),
    ("Generator node limit must be between {} and {}", "生成者节点上限必须在 {} 到 {} 之间"),
    ("Generator CPU limit must be a whole number", "生成者 CPU 上限必须是整数"),
    ("Generator CPU limit must be between {} and {}", "生成者 CPU 上限必须在 {} 到 {} 之间"),
    ("Generator GPU limit must be a whole number", "生成者 GPU 上限必须是整数"),
    ("Generator GPU limit must be between {} and {}", "生成者 GPU 上限必须在 {} 到 {} 之间"),
    ("nodes must be a whole number", "节点数必须是整数"),
    ("nodes must be between {} and {}", "节点数必须在 {} 到 {} 之间"),
    ("CPUs per task must be a whole number", "每任务 CPU 数必须是整数"),
    ("CPUs per task must be between {} and {}", "每任务 CPU 数必须在 {} 到 {} 之间"),
    ("GPUs must be a whole number", "GPU 数必须是整数"),
    ("GPUs must be between {} and {}", "GPU 数必须在 {} 到 {} 之间"),
    # ------------------------------------------ mcp.py (labels and composed)
    ("MCP server closed its input. {}", "MCP 服务器关闭了它的输入。{}"),
    ("MCP server exited before replying. {}", "MCP 服务器在回复之前退出了。{}"),
    ("MCP message must be valid JSON", "MCP 消息必须是有效的 JSON"),
    ("MCP message exceeds the {}-byte safety limit", "MCP 消息超出了 {} 字节的安全上限"),
    ("MCP tool metadata must be valid JSON", "MCP 工具元数据必须是有效的 JSON"),
    ("MCP tool metadata exceeds the {}-byte safety limit",
     "MCP 工具元数据超出了 {} 字节的安全上限"),
    ("MCP tool arguments must be valid JSON", "MCP 工具参数必须是有效的 JSON"),
    ("MCP tool arguments exceeds the {}-byte safety limit",
     "MCP 工具参数超出了 {} 字节的安全上限"),
    ("MCP structured result must be valid JSON", "MCP 结构化结果必须是有效的 JSON"),
    ("MCP structured result exceeds the {}-byte safety limit",
     "MCP 结构化结果超出了 {} 字节的安全上限"),
    # ------------------------------------------ cli/pair.py (composed)
    ("gh {} failed: {}.{}", "gh {} 失败：{}。{}"),
    ("science repository must be owner/name, got {}",
     "科学仓库必须写成 owner/name，实际得到 {}"),
    ("audit repository must be owner/name, got {}", "审计仓库必须写成 owner/name，实际得到 {}"),
    # ------------------------------------------ console/projects.py (composed, labels)
    ("Already exists: {}. Edit the names, or explicitly allow CrossAudit to use "
     "repositories you can access.",
     "已存在：{}。请修改名称，或明确允许 CrossAudit 使用你能访问的仓库。"),
    ("project cannot be deleted while {}", "存在以下活动时无法删除项目：{}"),
    ("GitHub connection unavailable: {}", "GitHub 连接不可用：{}"),
    ("name is required", "必须填写名称"),
    ("name is too long", "名称过长"),
    ("description is required", "必须填写描述"),
    ("description is too long", "描述过长"),
    ("auditor vendor is required", "必须选择审计者厂商"),
    ("auditor vendor is too long", "审计者厂商过长"),
    ("generator vendor is required", "必须选择生成者厂商"),
    ("generator vendor is too long", "生成者厂商过长"),
    ("auditor model is required", "必须填写审计者模型"),
    ("auditor model is too long", "审计者模型过长"),
    ("generator model is required", "必须填写生成者模型"),
    ("generator model is too long", "生成者模型过长"),
    ("max attempts must be a number", "最大尝试次数必须是数字"),
    ("max attempts must be between {} and {}", "最大尝试次数必须在 {} 到 {} 之间"),
    ("initial backoff seconds must be a number", "首次退避秒数必须是数字"),
    ("initial backoff seconds must be between {} and {}", "首次退避秒数必须在 {} 到 {} 之间"),
    ("max backoff seconds must be a number", "最大退避秒数必须是数字"),
    ("max backoff seconds must be between {} and {}", "最大退避秒数必须在 {} 到 {} 之间"),
    ("retry after cap seconds must be a number", "Retry-After 上限秒数必须是数字"),
    ("retry after cap seconds must be between {} and {}",
     "Retry-After 上限秒数必须在 {} 到 {} 之间"),
    ("circuit breaker failures must be a number", "熔断失败次数必须是数字"),
    ("circuit breaker failures must be between {} and {}",
     "熔断失败次数必须在 {} 到 {} 之间"),
    ("circuit breaker cooldown seconds must be a number", "熔断冷却秒数必须是数字"),
    ("circuit breaker cooldown seconds must be between {} and {}",
     "熔断冷却秒数必须在 {} 到 {} 之间"),
    ("daily token warning must be a positive number", "每日 token 警告线必须是正数"),
    ("daily token limit must be a positive number", "每日 token 上限必须是正数"),
    ("monthly cost warning usd must be a positive number", "每月费用警告线（美元）必须是正数"),
    ("monthly cost limit usd must be a positive number", "每月费用上限（美元）必须是正数"),
    # ------------------------------------------ console/daemon.py (via projects)
    ("the console on port {} (pid {}) did not stop; its record is kept so it can "
     "be found again",
     "端口 {} 上的控制台（pid {}）没有停止；其记录已保留，以便再次找到它"),
    # ------------------------------------------ console/server.py (composed)
    ("the selected PASS is not ready for admission: {}", "所选的 PASS 尚未达到准入条件：{}"),
    # ------------------------------------------ dispute.py (composed)
    ("{} was raised against {} artefacts; name one: {}",
     "{} 针对 {} 个产物被提出；请指定其中一个：{}"),
    ("name the finding to dispute by its rule id: {}", "请用规则 id 指定要申辩的发现：{}"),
    # ------------------------------------------ config.py heterogeneity (variable)
    ("the generator's provider is not declared, so independent review cannot be "
     "asserted; choose one in Project controls",
     "未声明生成者的供应商，因此无法断言独立审查；请在项目控制里选择一个"),
    ("The generator and the auditor must use different providers — independent review "
     "is the core of the protocol. Change one of them in Project controls. Their routes "
     "overlap at {}.",
     "生成者与审计者必须使用不同的供应商——独立审查是协议的核心。请在项目控制里更改其中一个。"
     "两者的路由在 {} 处重叠。"),
    # ------------------------------------------ connections.py (variable)
    ("that provider login method is not supported", "不支持该供应商的登录方式"),
    ("Official ChatGPT subscription sign-in is available through the bundled Codex "
     "runtime; CrossAudit never receives its OAuth token.",
     "可通过内置 Codex 运行时使用官方 ChatGPT 订阅登录；CrossAudit 绝不会接收其 OAuth token。"),
    ("Anthropic does not permit Claude consumer subscriptions to be bound to "
     "third-party apps. Use an Anthropic API key or a separately implemented "
     "enterprise cloud route.",
     "Anthropic 不允许把 Claude 消费者订阅绑定到第三方应用。请使用 Anthropic API key，或单独"
     "实现的企业云路由。"),
    ("A Gemini consumer subscription is not an API credential. Google AI Studio "
     "API/auth keys are supported; Vertex AI IAM is a separate cloud connection.",
     "Gemini 消费者订阅不是 API 凭据。支持 Google AI Studio 的 API/auth key；Vertex AI IAM "
     "是另一种云连接。"),
    ("Qwen Code offers its own official Coding Plan login, but CrossAudit does not "
     "reuse CLI session files as general inference credentials. Use a Model Studio "
     "API key here.",
     "Qwen Code 提供自己的官方 Coding Plan 登录，但 CrossAudit 不会把 CLI 会话文件当作通用推理"
     "凭据复用。请在此使用 Model Studio API key。"),
    ("xAI's inference API supports API credentials (and documented OAuth tokens for "
     "approved integrations), but an X consumer subscription is not automatically "
     "an inference entitlement. API key is enabled here.",
     "xAI 的推理 API 支持 API 凭据（以及面向已批准集成的、有文档说明的 OAuth token），但 X "
     "消费者订阅并不自动等于推理权限。此处启用的是 API key。"),
    # ------------------------------------------ app.py (variable)
    ("CrossAudit could not prepare its private application data in {} — grant "
     "access in System Settings › Privacy & Security › Files and Folders, then retry.",
     "CrossAudit 无法在 {} 准备其私有应用数据 —— 请在「系统设置 › 隐私与安全性 › 文件和文件夹」"
     "中授予访问权限，然后重试。"),
    ("CrossAudit could not create its workspace in {} — grant access in System "
     "Settings › Privacy & Security › Files and Folders, or choose another location.",
     "CrossAudit 无法在 {} 创建工作区 —— 请在「系统设置 › 隐私与安全性 › 文件和文件夹」中授予"
     "访问权限，或选择其他位置。"),
    ("CrossAudit could not read its saved connection settings — unlock the login "
     "Keychain and retry.",
     "CrossAudit 无法读取已保存的连接设置 —— 请解锁登录钥匙串后重试。"),
    ("CrossAudit could not start its private local console — allow local "
     "connections and retry.",
     "CrossAudit 无法启动其私有本地控制台 —— 请允许本地连接后重试。"),
    # ------------------------------------------ usage.py (composed)
    ("Local usage guardrail paused provider calls. {} Open Project controls to "
     "raise or clear the limit, then retry.",
     "本地用量保护线已暂停供应商调用。{}请打开「项目控制」提高或清除该上限，然后重试。"),
    # ------------------------------------------ providers/ (composed)
    ("provider returned HTTP {}\n  it said: {}\n  {}", "供应商返回了 HTTP {}\n  它说：{}\n  {}"),
    ("provider returned HTTP {}\n  it said: {}", "供应商返回了 HTTP {}\n  它说：{}"),
    ("provider returned HTTP {}\n  {}", "供应商返回了 HTTP {}\n  {}"),
    ("provider returned HTTP {}", "供应商返回了 HTTP {}"),
    ("provider stream failed: {}", "供应商的流式响应失败：{}"),
    ("ChatGPT subscription completion failed{}", "ChatGPT 订阅请求失败{}"),
    ("ChatGPT subscription completion failed", "ChatGPT 订阅请求失败"),
    ("ChatGPT subscription completion failed: {}", "ChatGPT 订阅请求失败：{}"),
    ("ChatGPT subscription returned an empty completion{}", "ChatGPT 订阅返回了空回复{}"),
    ("ChatGPT subscription returned an empty completion", "ChatGPT 订阅返回了空回复"),
    ("ChatGPT subscription returned an empty completion; its tool request was "
     "safely blocked, but it did not recover with a text answer",
     "ChatGPT 订阅返回了空回复；它的工具请求已被安全拦截，但之后没有恢复为文本回答"),
    # ------------------------------------------ console/daemon.py, runtime/commands.py
    # The escalation sentence the Decision Center leads with; its slot is the
    # provider refusal itself, translated in turn (COMPOSITE).
    ("provider failure left this task waiting for a person: {}",
     "供应商失败，该任务正在等待人工处理：{}"),
    ("no provider route is available", "没有可用的供应商路由"),
    # runtime/runs.py raises RuntimeError; runtime/commands.py re-wraps it as
    # ConfigDenial(str(exc)) — the one variable-carried reason the review's
    # runtime log still showed in English.
    ("there is no active run to cancel", "没有可取消的活动运行"),
    ("the run stopped for a person before its decision record was written",
     "运行在写入决定记录之前就停下来等人处理了"),
    # ------------------------------------------ receipt/ (composed)
    ("authority block does not validate: {}", "authority 区块未通过校验：{}"),
    # ------------------------------------------ file_identity.py (_path_denial)
    ("refusing an empty or invalid generated file path", "拒绝空的或无效的生成文件路径"),
    ("refusing a generated file path with directory syntax: {}",
     "拒绝带有目录语法的生成文件路径：{}"),
    ("refusing a path that escapes the project: {}", "拒绝越出项目的路径：{}"),
    ("refusing an unusable generated file path: {}", "拒绝无法使用的生成文件路径：{}"),
    ("the project root is not a directory", "项目根不是目录"),
    ("refusing generated files whose physical identity changed before apply",
     "拒绝在应用前物理身份已改变的生成文件"),
    ("generated payloads do not match their authorized targets",
     "生成的内容与其授权目标不匹配"),
    ("generated file authorization receipt is no longer active",
     "生成文件的授权凭证已失效"),
    ("generated file staging receipt is not available", "生成文件的暂存凭证不可用"),
    ("cannot transfer a generated file authorization receipt",
     "无法转移生成文件的授权凭证"),
    ("resolved target is outside the project: {}", "解析后的目标在项目之外：{}"),
    ("could not establish one directory identity for {}", "无法为 {} 确定唯一的目录身份"),
    ("could not resolve generated file path {}", "无法解析生成文件路径 {}"),
    ("could not inspect generated file target {}", "无法检查生成文件的目标 {}"),
    ("working directory {} resolves outside the project", "工作目录 {} 解析到了项目之外"),
    ("working directory is not a directory: {}", "工作目录不是目录：{}"),
    ("could not establish filename identity rules on the project filesystem",
     "无法在项目文件系统上确定文件名身份规则"),
    ("could not establish the physical project directory", "无法确定项目的物理目录"),
    ("{} resolves outside the project to {}", "{} 解析到了项目之外的 {}"),
    ("{} resolves outside the authorized working directories; the generator may "
     "not write rules, ledger or configuration",
     "{} 解析到了授权工作目录之外；生成者不得写入规则、账本或配置"),
    ("refusing a hidden physical target: {}", "拒绝隐藏的物理目标：{}"),
    ("refusing to edit scaffold template {}; create a new increment directory instead",
     "拒绝编辑脚手架模板 {}；请改为创建新的增量目录"),
    ("refusing filesystem-equivalent generated paths: {} and {}",
     "拒绝在文件系统上等价的生成路径：{} 和 {}"),
    ("the physical project directory changed before apply", "项目的物理目录在应用前发生了变化"),
    ("could not atomically apply the generated file round", "无法原子地应用本轮生成的文件"),
    ("generated file identity changed before staging: {}",
     "生成文件的身份在暂存前发生了变化：{}"),
    ("could not establish physical file identity for {}", "无法确定 {} 的物理文件身份"),
    ("refusing dangling symlink target {}", "拒绝悬空的符号链接目标 {}"),
    ("generated file parent is not a directory: {}", "生成文件的上级不是目录：{}"),
    ("generated file target is not a regular file: {}", "生成文件的目标不是常规文件：{}"),
    ("refusing hardlinked file target with non-unique identity: {}",
     "拒绝身份不唯一的硬链接文件目标：{}"),
    ("refusing two generated paths for one physical file: {} and {}",
     "拒绝指向同一物理文件的两个生成路径：{} 和 {}"),
    ("refusing generated paths where one physical target contains another",
     "拒绝一个物理目标包含另一个的生成路径"),
    ("refusing a generated file created after authorization: {}",
     "拒绝在授权之后才创建的生成文件：{}"),
    ("refusing a generated file that changed before publish: {}",
     "拒绝在发布前发生变化的生成文件：{}"),
    ("refusing dangling symlink parent {}", "拒绝悬空的符号链接上级 {}"),
    ("could not establish a parent for {}", "无法确定 {} 的上级目录"),
    ("refusing a generated file that changed during apply: {}",
     "拒绝在应用过程中发生变化的生成文件：{}"),
)


#: Sentences of ours that only ever appear INSIDE another refusal's slot —
#: never raised on their own, so they are not in ENTRIES (the orphan guard
#: would rightly reject them there). They are looked up only from the slots
#: of the templates in COMPOSITES.
CLAUSES: tuple[tuple[str, str], ...] = (
    # broker/secretscan.py — the KIND of secret a refused commit carried.
    ("a private key block", "私钥块"),
    ("an AWS access key id", "AWS 访问密钥 ID"),
    ("a GitHub token", "GitHub token"),
    ("a GitHub fine-grained token", "GitHub 细粒度 token"),
    ("a Slack token", "Slack token"),
    ("a Google API key", "Google API key"),
    ("a Stripe secret key", "Stripe 密钥"),
    ("a private OpenAI key", "OpenAI 私密密钥"),
    ("an environment file that may contain secrets", "可能含有机密的环境文件"),
    # cli/pair.py — the hint after a failed `gh` command.
    ("Authorize GitHub CLI for the organisation's SSO, then retry.",
     "请为该组织的 SSO 授权 GitHub CLI，然后重试。"),
    ("GitHub rate-limited this account; wait for the reset, then retry.",
     "GitHub 对此账户限流了；请等待重置后重试。"),
    ("The connected account lacks repository or organisation permission.",
     "已连接的账户缺少仓库或组织权限。"),
    ("The name exists but may not be visible to this account; verify ownership.",
     "该名称已存在，但此账户可能看不到它；请核实归属。"),
    # console/projects.py — what is still running when a delete is refused.
    ("project setup is still running", "项目创建仍在运行"),
    ("a Generator/Auditor task is running", "有生成者/审计者任务正在运行"),
    ("{} remote compute job(s) are active", "有 {} 个远程计算作业处于活动状态"),
    # receipt/verify.py — admission shortfalls.
    ("verdict is {}, not PASS", "判定是 {}，不是 PASS"),
    ("audit integrity is {}", "审计完整性是 {}"),
    ("evidence route is {}, not receipt", "证据路由是 {}，不是 receipt"),
    ("isolation evidence is missing {}", "缺少隔离证据 {}"),
    ("this receipt is not the one recorded for the cycle — re-run the audit",
     "此收据不是该周期记录的那份 —— 请重新运行审计"),
    # usage.py — why the guardrail paused.
    ("Daily token limit reached: {} / {}.", "已达到每日 token 上限：{} / {}。"),
    ("Monthly API-value limit reached: ${} / ${}.", "已达到每月 API 费用上限：${} / ${}。"),
    ("The monthly cost limit cannot be proven because one or more calls use an "
     "unpriced model. Remove the cost limit or select priced models.",
     "由于一次或多次调用使用了未定价的模型，无法证明每月费用上限。请移除费用上限，或选择已定价"
     "的模型。"),
    ("The next request is estimated to exceed the daily token limit: {} used + "
     "approximately {} input > {}.",
     "下一次请求预计会超出每日 token 上限：已用 {} + 约 {} 输入 > {}。"),
    # providers/base.py — the advice under an HTTP status.
    ("the key was rejected. Check the one in your keys file is for this vendor "
     "and not truncated — re-enter it if the paste may be incomplete",
     "密钥被拒绝。请检查密钥文件中的这把密钥属于该厂商且未被截断 —— 如果粘贴可能不完整，"
     "请重新输入"),
    ("the key is valid but not permitted here — often a workspace or a region "
     "restriction on the account",
     "密钥有效但在此处不被允许 —— 通常是账户上的工作区或区域限制"),
    ("the endpoint does not exist. If you set a custom base URL, check it",
     "该端点不存在。如果你设置了自定义 base URL，请检查它"),
    ("rate limited or out of credit. This is the vendor's limit, not ours",
     "被限流或额度用尽。这是厂商的限制，不是我们的"),
    ("that is the model id, not your key. Set a model this account can use — "
     "`crossaudit init` lists the current ones, or edit `model:` in crossaudit.yml",
     "问题出在模型 id，不是你的密钥。请设置此账户可用的模型 —— `crossaudit init` 会列出当前"
     "可用的模型，或编辑 crossaudit.yml 里的 `model:`"),
    # auditor/authority.py — why an authority block does not validate.
    ("authority block carries unknown keys {}", "authority 区块含有未知的键 {}"),
    ("authority policy version {} is not one this verifier knows ({})",
     "authority 策略版本 {} 不是此验证器认识的版本（{}）"),
    ("authority workflow verdict {} is unknown", "authority 工作流判定 {} 未知"),
    ("authority route {} is unknown", "authority 路由 {} 未知"),
    ("authority route {} does not follow from verdict {}",
     "authority 路由 {} 与判定 {} 不相符"),
    ("authority requires_human disagrees with its route",
     "authority 的 requires_human 与其路由不一致"),
    ("authority lone_model_blocker names an unknown policy dial",
     "authority 的 lone_model_blocker 指定了未知的策略档位"),
    ("authority evidence is not a list", "authority 的 evidence 不是列表"),
    ("authority evidence digest does not match its records",
     "authority 的证据摘要与其记录不匹配"),
    ("authority evidence ids are not unique, one per record",
     "authority 的证据 id 不唯一（每条记录应有一个）"),
    ("authority {} is not a list", "authority 的 {} 不是列表"),
    ("authority {} repeats an id", "authority 的 {} 重复了某个 id"),
    ("authority {} names evidence not in the block: {}",
     "authority 的 {} 指向了区块中不存在的证据：{}"),
    ("authority rationale is empty", "authority 的 rationale 为空"),
    ("authority decision_id does not re-derive from the block: a partition, "
     "sentence, dial or route was edited",
     "authority 的 decision_id 无法从区块重新推导出来：某个分区、句子、档位或路由被改动过"),
)

#: The templates whose slot carries our OWN clause(s) rather than a path, an
#: id or a person's words. Only these slots are looked up in CLAUSES; every
#: other slot is carried through untouched (D130: never match text a person
#: could have authored).
COMPOSITES: frozenset[str] = frozenset({
    "commit refused: the staged changes appear to contain {}; remove the secret "
    "(or add the file to .gitignore) and try again",
    "gh {} failed: {}.{}",
    "project cannot be deleted while {}",
    "the selected PASS is not ready for admission: {}",
    "Local usage guardrail paused provider calls. {} Open Project controls to "
    "raise or clear the limit, then retry.",
    "provider returned HTTP {}\n  it said: {}\n  {}",
    "provider returned HTTP {}\n  {}",
    "authority block does not validate: {}",
    "all configured generator provider routes failed. {}",
    "all configured auditor provider routes failed. {}",
    "all configured {} provider routes failed. {}",
    "provider failure left this task waiting for a person: {}",
    "generator provider failure in round {}: {}",
    "auditor provider failure in round {}: {}",
})
