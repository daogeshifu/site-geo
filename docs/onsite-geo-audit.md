# 通用站内 GEO 审计：onsite-geo-v3

## 任务与兼容性

| task_type | 任务 | 评分 |
|---|---|---|
| `site_geo_only_audit` | 网站 GEO 审计，页面首位并默认选中 | 新版站内六维 `onsite-geo-v3`（27项） |
| `site_seo_audit` | 网站 SEO 审计，API省略类型时的兼容默认 | 原SEO六维，`seo-audit-v1` |
| `site_geo_audit` | 网站 SGEO 诊断，沿用旧标识 | 六维、30项唯一检查、统一总分，见[SGEO规则](onsite-sgeo-audit.md) |
| `site_content_audit` | 网站内容审计 | 保留单篇内容评分 |

GEO与SGEO不调用外链服务；独立SEO可取得外链支持数据。OG/Twitter卡片保留在SEO技术支持分中；外链保留在SEO品牌权威支持信号中，并非独立一级SEO维度。两者均不参与新版GEO或SGEO。

同步新版端点为 `POST /api/v1/audit/geo`，支持已有 `discovery`。历史 `/audit/full`、`/audit/visibility`、`/audit/technical`、`/audit/content`、`/audit/schema`、`/audit/platform` 仍保留 `geo-audit-v3` 模块算法，不可和新版分数横向比较。

单页 `audit_scope=page` 仍为 `single-page-checks-v2` 的适用必检项通过率，不是站点GEO分。GEO/组合任务在网站范围默认最多采样8页，Full Audit按 `max_pages` 扩展。

## 六维和27项唯一计分规则

以下括号内分值为全局满分分配，总计100。页面适用性和未知状态会影响有效分母，不能直接把缺失证据记为失败。

| 维度 | 权重 | 规则 |
|---|---:|---|
| 可获取：访问与抓取可达性 | 20% | GEO-001 HTTP状态/HTTPS/主域与重定向规范(5)；002 Robots.txt与AI检索爬虫精细化放行(6)；003 CDN/WAF放行与AI爬虫访问挑战(5)；025 页面加载速度/TTFB与HTML获取(4) |
| 可获取：页面发现与可索引性 | 15% | GEO-005 可抓取导航与语义化内链(2)；006 XML Sitemap质量与页面发现覆盖(3)；007 Canonical规范链接与跳转一致(2)；008 索引与摘要指令(2)；024 llms.txt与Markdown纯文本直出(4)；026 URL静态化与语义规范(2) |
| 可理解：正文读取与信息提取 | 18% | GEO-009 初始HTML核心正文直出与反CSR空壳(7)；010 关键信息载体与标准HTML语义表格(5)；011 原始HTML与渲染后DOM一致性(4)；027 HTML正文信噪比与响应体量(2) |
| 可理解：元数据与实体语义 | 12% | GEO-021 页面TDK与语言元数据(2)；022 实体命名、@id与权威关联(3)；023 适用Schema.org及正文一致性(5)；028 多语言与区域标记hreflang(2) |
| 可引用：内容价值与答案适配 | 20% | GEO-012 Title/H1意图聚焦与正文对应(5)；013 首段结论前置与问答摘要结构(5)；014 标题层级规范与段落自包含性(4)；015 页面任务核心信息完备度(4)；016 具象量化表达与低冗余(2) |
| 可推荐：站内可信度与时效性 | 15% | GEO-017 官方发布主体、作者与责任团队(4)；018 关键主张与数据出处可追溯(5)；019 机器可读时效性与版本价格明确度(4)；020 跨页面关键实体与事实一致性(2) |

规则定义集中在 `app/services/audit/geo.py` 的 `RULES`，每个ID唯一归属一个维度。SEO继续保留自己的权重，不使用GEO分替换SEO支持分。

v3 保留四大阶段（可获取 35%、可理解 30%、可引用 20%、可推荐 15%）与六项诊断骨架，将 `semantics` 从 5% 提级至 12%，移出单次扫描恒未知的 `GEO-004` 至持续观测层，新增 `GEO-027`（HTML正文信噪比与体量）和 `GEO-028`（条件适用 `hreflang`），并同步升级 WAF AI 爬虫实测、反 CSR 空壳、Sitemap 质量、`llms-full.txt`/Markdown 直出、Schema 实体关联与自动化跨页一致性初筛。缓存自动与旧版 v1/v2 隔离。

## 六维与“可获取、可理解、可引用、可推荐”的关系

四阶段描述AI使用内容的过程，六维描述可以落实到检查项的评价依据，两者是多对多关系。四阶段用于解释，不另算四个分数，也不把同一规则重复计分。

展示标题采用主要归属：访问/发现→可获取，正文/语义→可理解，答案适配→可引用，可信度与时效性→可推荐。该前缀仅表示主要优化目标，不把“可推荐”当成已取得真实推荐。维度内检查展示具体诊断对象，多个对象用 ` / ` 分隔；GEO编号保留在覆盖清单和数据标识中用于追溯。

| 阶段 | 主要对应六维 | 当前能够判断的范围 |
|---|---|---|
| 可获取 | 访问与抓取可达性、页面发现与可索引性 | 页面能否被发现和抓取，包含robots、Sitemap、llms.txt、速度及URL规范；实际搜索收录仍需外部验证 |
| 可理解 | 正文读取与信息提取、元数据与实体语义；内容价值与答案适配也提供支持 | 正文、信息载体、渲染一致性、标题层级和Schema等结构信号；不等于完整语义理解 |
| 可引用 | 内容价值与答案适配、站内可信度与时效性；提取与语义也提供支持 | 答案位置、自包含段落、来源、日期版本等引用准备度；实际引用需问答样本验证 |
| 可推荐 | 六维共同提供基础，尤其答案适配、可信度与时效性 | 当前只能评价站内准备条件；真实推荐还需目标问题、竞品比较、多平台答案中的提及/推荐位置及持续监测 |

“可推荐”不能由前三阶段分数推定为已达成。当前GEO总分始终为站内就绪度，实际提及、引用与推荐表现放在独立观测中核验。

## 单项证据与判定

- 每条检查返回 `id / dimension / max_points / status / value / evidence / evidence_type / blocker / recommendation`。
- `pass / partial / fail` 分别表示完全、部分和未满足，`value`在0–1之间；覆盖型使用比例。确定性检查为0或1。
- `unknown` 表示尚未测量或证据不足，`value=null`；`na`表示不适用，必须由规则条件确定。未知不能冒充不适用。
- robots按目标路径及查询参数检查主流国际检索爬虫（Googlebot、bingbot、OAI-SearchBot、ChatGPT-User、PerplexityBot、Perplexity-User、Claude-SearchBot、Claude-User），中文/国内站自动补充 Baiduspider、Bytespider、Kimi-SearchBot；解析 `Content-Signal`（仅当显式误设 `search=no`/`ai-input=no` 时告警/扣分）与 `LLM-Policy`，并对误屏蔽 `Google-Extended` 输出 Gemini 引用风险提示。训练许可不计分。
- CDN/WAF 放行与访问挑战检查（GEO-003）既检查常规抓取响应与挑战 DOM/响应头（含 `cf-mitigated`），也对代表性采样页使用真实 AI 爬虫 UA 发送轻量探针，避免普通抓取掩盖 Cloudflare/WAF 默认拦截 AI 爬虫的问题。
- 持续稳定性监测（原 GEO-004）移入持续观测层，不再在单次扫描中硬编码 unknown 卡死就绪结论。
- 正文从main/article/role=main或body取得，排除导航、页脚、脚本、样式和隐藏节点；GEO-009 同步识别并阻断空 `#root/#app`、`<noscript>` JS 提示与 `Loading...` 等 CSR 空壳占位页。
- GEO-010 检查实际 DOM 中的表格、列表、代码与图片替代文本，并核验 `<table>` 是否含语义表头（`<thead>`/`<th>`/`<caption>`）及规格页是否缺失语义表格；源码截断时未知。
- GEO-011 在允许抓取、启用 Playwright 且浏览器测量有效时，综合比对渲染后正文词元、H1/H2 标题、表格与关键内链在原始 HTML 中的留存率。停用、失败或截断时 unknown。
- GEO-027 检查单页 HTML 字节体量（250KB / 500KB / 1MB 启发式预算）与有效正文信噪比，抑制超大内联脚本/状态 JSON 带来的抓取截断与 RAG Token 噪音。
- GEO-012至016明确标注 `structural_proxy`：题文主题词覆盖与单 H1 规范、首块结论/问答标题/TL;DR 摘要、段落指代与标题跳级、页面类型结构要求（含对比选型页）、量化表达与重复/空泛词。不鼓励刻意切碎长文或堆砌关键词。
- GEO-017 区分页面可见署名与 JSON-LD `author`/`publisher`/`Organization` 双信号；GEO-018 排除购买/登录等非来源链接，支持行内来源、标准编号与文末参考来源区；GEO-019 支持 ISO/中文/英文日期、机器可读 `datePublished`/`dateModified`、版本号与产品明确报价。
- GEO-020 对 ≥2 个含结构化实体/报价的采样页自动初筛组织名、`@id` 与产品价格冲突，单页或无结构化实体时记为 na；不替代人工深度事实核查。
- GEO-021 检查页面 Title、Meta Description（含跨页唯一性）与 `<html lang>`；GEO-022 核验实体名称可见一致、稳定 `@id` 与 `sameAs`/`about`/`mentions` 等标准实体关联；GEO-023 按全页面类型检查标准 Schema.org（Organization/WebSite、Product/Offer、Service、Article、TechArticle/HowTo、FAQPage）及正文词元对齐，不要求非标准字段。
- GEO-028 检查多语言与区域标记 `hreflang`（含语法、自引用、`x-default` 及与 `html lang` 一致性）；单语种无多语言路径站点自动判 na，不误扣分。
- GEO-024（4分）对完整 `llms.txt` 评估基础分（2.5分：可读纯文本、标题简介、站内导航与链接抽检）与进阶分（1.5分：`/llms-full.txt` 或 `.md` 纯文本直出）。文件存在不能替代 P0 抓取基建。
- GEO-025 使用各页已记录的 HTML 获取耗时（含 TTFB 记录与重定向/响应体）。≤800ms得4分；≤1500ms得3分；≤3000ms得2分；≤5000ms得1分；超过5000ms得0分。
- GEO-026 检查 URL 静态化与语义规范：干净小写路径及常见跟踪参数得满分；大写/乱码路径略扣分；内容参数或动态脚本入口得半分；会话标识或哈希路由得0分。

## 计分、聚合与未知区间

1. 每页先按六维分别计算。某维度已测得分为 `100 × Σ(单项满分 × value) / Σ已测适用单项满分`。na剔除，unknown不当作通过。
2. 候选页按页面类型轮询采样。站点层页面类型等权，同类型页面等权。各规则先按样本权重聚合，再按维度固定权重汇总，避免首页或最佳页替代全站。
3. 每维证据覆盖率为已测适用分值/全部适用分值；总覆盖率按六维权重汇总。某维度完全未知时，暂算其余维度，仍在上下界中保留该维度。
4. `score`是已测证据下的估计；`score_range`下界将未知设0，上界设1。只要有unknown，`provisional=true`，就绪状态保持unverified或blocked。
5. 每个规则及维度最多取得其分配满分，不以超额叠分后截断代替归一化。
6. 每次复测应使用相同页面集合、类型与评分版本。候选覆盖率不是全站覆盖率，不能据少量已发现页推断未发现内容。

## 阻断与就绪结论

HTTP失败、当前访问挑战、无核心正文、noindex及目标检索主体路径限制按页面/渠道列为blockers。总分保留用于跟踪，但 `readiness_status=blocked` 优先于高分。

无阻断但存在未知为unverified；全部适用项目已测、无阻断且分数≥85才为ready，其余为needs_work。高分、配置文件存在或平台推测均不代表已经被AI引用。

## 结果字段

| 字段 | 说明 |
|---|---|
| `result.geo.scoring_version` | `onsite-geo-v3` |
| `result.geo.score` | 站内GEO估计分，可空；配合provisional和score_range读取 |
| `result.geo.dimensions` | access/discovery/extraction/answers/trust/semantics；含原始证据覆盖率和检查状态 |
| `result.geo.pages` | 所有已选采样页，包括失败页、逐页检查、源码键及抓取元数据 |
| `result.geo.blockers` | 受影响URL、规则与证据 |
| `result.geo.coverage` | 采样数量、已发现候选量、页面类型、样本权重、证据覆盖率、未知及阻断比例；全站总量未知时为null |
| `result.geo.auxiliary` | 不计分的授权/外部权威/真实索引及引用说明；llms.txt已移入GEO-024计分 |
| `summary.geo_score` | 新版GEO分，`composite_geo_score`仅为兼容别名 |
| `summary.seo_score` | 纯GEO为null；新SGEO任务不返回此字段 |
| `summary.combined_score` | 纯GEO为null；新SGEO任务为统一SGEO分的别名 |
| `result.observation` | 独立观测，不改变分数 |

## 复用与运行限制

发现快照、源码、HTTP抓取证据可复用于SGEO。先读取已有源码；证据丢失或没有捕获时才重新抓取。SGEO复用共用规则的观察结果并补充搜索所需信号，以自己的六维权重计分；独立SEO的域名变体检查不属于SGEO流程。

缓存隔离任务类型、评分版本、页面数量、目标语言、报告语言、模式及GEO渲染开关。新版任务不会复用历史GEO评分缓存；`force_refresh=true`跳过结果缓存及站点快照缓存。

GEO始终规则评分，premium不会用模型推断补齐未知项。尚未执行的持续稳定性、跨页事实审核及未启用的浏览器对照均会保留待核验；报告显示相应覆盖率与分数区间。

Content-Signal、LLM-Policy、训练授权、OG/Twitter、一般安全响应头、外链和平台推测不进入GEO分。实际收录、AI引用、品牌提及、流量与转化独立验证。
