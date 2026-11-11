# 通用站内 GEO 审计：onsite-geo-v1

## 任务与兼容性

| task_type | 任务 | 评分 |
|---|---|---|
| `site_geo_only_audit` | 网站 GEO 审计，页面首位并默认选中 | 新版站内六维 |
| `site_seo_audit` | 网站 SEO 审计，API省略类型时的兼容默认 | 原SEO六维，`seo-audit-v1` |
| `site_geo_audit` | 网站 SEO+GEO 审计，沿用旧标识 | 分别输出SEO与新版GEO，共享页面证据，不平均 |
| `site_content_audit` | 网站内容审计 | 保留单篇内容评分 |

纯GEO不调用外链服务；SEO/组合审计可取得外链支持数据。OG/Twitter卡片保留在SEO技术支持分中；外链保留在SEO品牌权威支持信号中，并非独立一级SEO维度。两者均不参与新版GEO。

同步新版端点为 `POST /api/v1/audit/geo`，支持已有 `discovery`。历史 `/audit/full`、`/audit/visibility`、`/audit/technical`、`/audit/content`、`/audit/schema`、`/audit/platform` 仍保留 `geo-audit-v3` 模块算法，不可和新版分数横向比较。

单页 `audit_scope=page` 仍为 `single-page-checks-v2` 的适用必检项通过率，不是站点GEO分。GEO/组合任务在网站范围默认最多采样8页，Full Audit按 `max_pages` 扩展。

## 六维和23项唯一计分规则

以下括号内分值为全局满分分配，总计100。页面适用性和未知状态会影响有效分母，不能直接把缺失证据记为失败。

| 维度 | 权重 | 规则 |
|---|---:|---|
| 访问与抓取可达性 | 20% | GEO-001 HTTP/HTTPS可用(5)；002目标路径检索爬虫规则(7)；003当前抓取无访问挑战(5)；004稳定性(3) |
| 页面发现与可索引性 | 15% | GEO-005可抓取导航/内链(5)；006入口导航链或Sitemap发现覆盖(4)；007规范网址与跳转一致(3)；008索引和摘要指令(3) |
| 正文读取与信息提取 | 20% | GEO-009核心正文可提取(10)；010关键信息载体完整(6)；011原始/渲染正文一致(4) |
| 内容价值与答案适配 | 25% | GEO-012主题与正文对应(7)；013结论/关键信息位置(5)；014段落自包含与组织(5)；015页面任务所需信息(5)；016具体表达与低冗余(3) |
| 站内可信度与时效性 | 15% | GEO-017发布主体/责任团队(4)；018主张依据可追溯(6)；019日期/版本(3)；020跨页事实一致(2) |
| 元数据与实体语义 | 5% | GEO-021标题及语言(2)；022实体名称/标识可见一致(1)；023适用Schema及正文一致(2) |

规则定义集中在 `app/services/audit/geo.py` 的 `RULES`，每个ID唯一归属一个维度。SEO继续保留自己的权重，不使用GEO分替换SEO支持分。

## 单项证据与判定

- 每条检查返回 `id / dimension / max_points / status / value / evidence / evidence_type / blocker / recommendation`。
- `pass / partial / fail` 分别表示完全、部分和未满足，`value`在0–1之间；覆盖型使用比例。确定性检查为0或1。
- `unknown` 表示尚未测量或证据不足，`value=null`；`na`表示不适用，必须由规则条件确定。未知不能冒充不适用。
- robots按目标路径及查询参数检查默认四个检索主体：Googlebot、bingbot、OAI-SearchBot、PerplexityBot；支持最长匹配、通配符与结尾锚点。训练许可不影响此分。
- 当前访问挑战检查HTTP响应中的验证码、登录挑战等证据；不代表真实AI爬虫来源已验证。HTTPS/状态检查与robots许可分别计分。
- 仅单次抓取无法证明稳定性：GEO-004保持unknown。配置声明、当前HTTP观察、浏览器模拟不可混称真实爬虫测量。
- 正文从main/article/role=main或body取得，排除导航、页脚、脚本、样式和隐藏节点。无统一字数门槛，不根据HTML体积推断SSR。
- GEO-010检查实际DOM中的表格、列表、代码等是否有文本及图片替代文本；源码截断时未知。未渲染的异步内容完整性由GEO-011另行核验。
- GEO-011在允许抓取、启用Playwright且浏览器测量有效时，比较渲染正文词元在初始正文中的覆盖率。停用、失败或截断时unknown；不强制采用某种渲染架构。
- GEO-012至016明确标注 `structural_proxy`：题文主题词覆盖、首块主题/关键信息位置、段落指代与标题跳级、页面类型结构要求、重复段落与空泛词。这些不等于用户意图已完全满足或事实正确。
- 商品页检查名称、说明及规格/报价；文档检查主题、解释及步骤/代码/参考；工具检查用途、输入标签及操作控件；首页/服务/关于/联系检查用途、说明及下一步；其他内容看主题、说明和支撑分节。页面当前Schema可以细化类型。
- GEO-017识别发布主体、作者或团队，主体信息链接可部分满足。没有强制个人作者、电话或实体地址要求。
- GEO-018仅检查识别出的数字/研究/测试主张附近有无来源链接，无此类主张为na；不确认来源真实性或主张准确性。
- GEO-019对文章、文档、案例及存在日期的页面检查非未来且可解析日期或版本范围；其他页面可na。Last-Modified/ETag不是内容新鲜度证明。
- GEO-020没有已审核的跨页事实清单时unknown，不能用品牌名相同替代事实核查。
- GEO-022检查当前页面实体名称和可见正文一致性，以及已声明标识是否合法、同一标识有无冲突名称；无可比较实体时na，不使用站外品牌提及。
- GEO-023按当前页面类型检查Schema语法、适用类型及描述/正文一致性。商品、文章、技术文档有对应适用类型；其他页没有Schema时可na。不要求堆齐类型或强制FAQ。

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
| `result.geo.scoring_version` | `onsite-geo-v1` |
| `result.geo.score` | 站内GEO估计分，可空；配合provisional和score_range读取 |
| `result.geo.dimensions` | access/discovery/extraction/answers/trust/semantics；含原始证据覆盖率和检查状态 |
| `result.geo.pages` | 所有已选采样页，包括失败页、逐页检查、源码键及抓取元数据 |
| `result.geo.blockers` | 受影响URL、规则与证据 |
| `result.geo.coverage` | 采样数量、已发现候选量、页面类型、样本权重、证据覆盖率、未知及阻断比例；全站总量未知时为null |
| `result.geo.auxiliary` | 不计分的llms.txt、授权/外部权威/真实索引及引用说明 |
| `summary.geo_score` | 新版GEO分，`composite_geo_score`仅为兼容别名 |
| `summary.seo_score` | 组合任务中的独立SEO分，纯GEO为null |
| `summary.combined_score` | 始终null，不合成总分 |
| `result.seo_summary` | 组合任务中的独立SEO摘要 |
| `result.observation` | 独立观测，不改变分数 |

## 复用与运行限制

发现快照、源码、HTTP抓取证据在SEO+GEO中共享。先读取已有源码；证据丢失或没有捕获时才抓取一次并交给两种引擎。SEO额外的域名变体检查和可选浏览器测量为不同目的的请求。

缓存隔离任务类型、评分版本、页面数量、目标语言、报告语言、模式及GEO渲染开关。新版任务不会复用历史GEO评分缓存；`force_refresh=true`跳过结果缓存及站点快照缓存。

GEO始终规则评分，premium不会用模型推断补齐未知项。尚未执行的持续稳定性、跨页事实审核及未启用的浏览器对照均会保留待核验；报告显示相应覆盖率与分数区间。

llms.txt、Content-Signal、LLM-Policy、训练授权、OG/Twitter、一般安全响应头、外链和平台推测不进入GEO分。实际收录、AI引用、品牌提及、流量与转化独立验证。
