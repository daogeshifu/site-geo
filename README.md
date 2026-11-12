# GEO Audit Service

面向通用网站的SEO、站内GEO、统一SGEO和内容诊断。页面默认任务为“网站 GEO 审计”；SGEO将搜索优化与生成式检索融合为同一套诊断规则。

## 任务与评分

| task_type | 页面名称 | 结果与口径 |
|---|---|---|
| `site_geo_only_audit` | 网站 GEO 审计（页面默认首选） | `result.geo`，站内六维就绪度 `onsite-geo-v2` |
| `site_seo_audit` | 网站 SEO 审计 | `result.seo`，保留 `seo-audit-v1`；API省略类型仍默认SEO |
| `site_geo_audit` | 网站 SGEO 诊断（沿用原标识） | `result.sgeo`，六维、30项唯一检查、一个总分 `onsite-sgeo-v1` |
| `site_content_audit` | 网站内容审计 | 单篇内容审计，独立评分 |

## 站内GEO：六维100分

| 维度 | 权重 |
|---|---:|
| 可获取：访问与抓取可达性 | 20% |
| 可获取：页面发现与可索引性 | 15% |
| 可理解：正文读取与信息提取 | 20% |
| 可引用：内容价值与答案适配 | 25% |
| 可推荐：站内可信度与时效性 | 15% |
| 可理解：元数据与实体语义 | 5% |

- 26项检查唯一归属、先逐页后按类型汇总；显示关键阻断、失败页、待核验项、适用范围和证据覆盖率。llms.txt、HTML获取速度、URL静态化与参数规范已纳入计分。
- 不设统一字数/FAQ要求，不按Schema类型数量累计；事实核验不足和未测渲染保持未知。
- 外链、OG/Twitter、一般安全头、训练授权和平台推测不计入新版GEO；实际索引、AI引用和流量独立观测。
- 独立SEO保留现有维度及技术/外链支持信号。SEO、GEO、SGEO使用各自评分版本，不直接横比。
- [完整计分、证据和字段说明](docs/onsite-geo-audit.md)；在线 `/api-doc` 为接入说明。
- 历史 `/api/v1/audit/full` 和五个模块端点仍为 `geo-audit-v3`，不代表新版评分。旧版字段见历史数据字典。

## 诊断结果展示

SEO、GEO 和 SGEO 共用诊断报告样式；SGEO展示版本为 `diagnostic-report-v3-sgeo`：

- SEO、GEO各保留6个维度、26项检查。SGEO融合为6个维度、30项唯一检查；访问与性能20%、发现与索引15%、正文读取15%、内容与答案25%、可信与时效15%、元数据与实体10%，合计100%。
- SGEO从逐项页面证据直接计分，共用检查只计一次；统一显示一个总分、一张雷达图、一组六维评估和一份行动清单，不使用SEO、GEO分数相加或平均。
- 问题清单支持关键词、维度和优先级筛选，保留检测证据、影响、修复建议和验收条件；问题可定位到受影响页面。
- 完整覆盖清单以桌面每行三项展示编号、事项和状态，小屏依次切换两列/一列；区分通过、待整改、部分满足、待核验和不适用。部分页面通过、其他页面未知时，仍列入待核验队列。
- 平台区域展示采样路径的检索爬虫规则，不生成平台曝光分或引用概率；Google 搜索的共用规则与 Gemini 未采集数据分别说明。
- 逐页证据、站点快照、归一权重与计分说明可展开查看，支持窄屏和键盘操作。Markdown 导出同步包含 GEO 完整检查表、待核验队列、平台规则与逐项建议。

此次调整保持现有 `/api/v1` 路径和请求参数。原组合任务 `site_geo_audit` 改为返回 `sgeo` 与统一摘要，新增SGEO评分缓存隔离；纯SEO/GEO字段不变。历史组合结果按保存的页面证据重新归并展示和导出，未保存的新检查保持待核验，不改写历史存储分数。[SGEO计分、归并与兼容说明](docs/onsite-sgeo-audit.md)。

验证：`.venv/bin/python -m pytest -q`、`node --test tests/*report.test.mjs`。

## 抓取与渲染

抓取限制在精确host和语言路径；默认站点任务最多采样8页，Full Audit按max_pages扩展。
源码证据最多2MB并标记截断，SGEO的一套规则复用同一批抓取证据。
GEO直接检查正文、表格、代码等内容，不靠HTML体积或字数推断SSR。

可选渲染复用现有Chromium检测：

```bash
.venv/bin/playwright install chromium
ALLOW_PLAYWRIGHT=true ./start.sh
```

未启用或无法完成时，对应规则为待核验。当前模拟不来自真实搜索/AI爬虫IP，不模拟当地网络位置。
Google爬虫独立工具仍位于 `/google-crawler-test`。

## 技术栈

- Python 3.10+
- FastAPI
- Pydantic
- Async task pipeline
- Optional OpenRouter LLM enhancement
- Optional Semrush backlink enrichment

---

## 运行方式

### 本地运行

```bash
python -m venv .venv     //启用配置文件
.venv\\Scripts\\activate  //启用虚拟环境
pip install -r requirements.txt  //安装相关依赖
uvicorn app.main:app --reload --port 8023  //指定端口启动脚本

然后浏览器打开  http://127.0.0.1:8023 就可以访问了
```

访问：

```text
http://127.0.0.1:8023
```

### Docker

推荐使用 Compose。服务器首次部署和以后更新均执行：

```bash
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` 会依次拉取最新代码、重建镜像、重建容器并等待健康检查。
容器参数统一维护在 `compose.yaml` 中；Google Render 的 Playwright 开关由
Compose 强制启用，镜像构建时会安装 Chromium。脚本优先使用新版
`docker compose`；仅有已停止维护的旧版 `docker-compose` v1 或未安装
Compose 时，会自动使用纯 Docker 命令。

如果镜像构建在 `playwright install --with-deps chromium` 前报
`playwright/driver/node: ... libatomic.so.1: cannot open shared object file`，
需要在 **Dockerfile 内、运行 Playwright 之前**安装 `libatomic1`。当前 Dockerfile
已包含此步骤；只在宿主机安装该包不能补齐镜像内的依赖。

若旧容器报 `docker-<容器ID>.scope was already loaded or has a fragment file`，
先检查 `docker inspect --format '{{json .State}}' geo-audit-service`。
确认容器已退出且 `stop/reset-failed` 无效后，可在镜像构建成功后只重建该服务，
让新容器使用新的 ID；不要为此重启整个 Docker 服务。
重建前确认 `.env`、`/app/.data` 的实际挂载和备份，保留 Token 与调用日志。

```bash
COMPOSE_BAKE=false docker compose -p site-geo -f compose.yaml build geo-audit-service &&
docker compose -p site-geo -f compose.yaml up -d --no-deps --no-build --force-recreate geo-audit-service
```

这里显式指定 `site-geo`，与部署脚本使用同一个 Compose 项目。构建失败时不会执行
后面的容器重建；`COMPOSE_BAKE=false` 可用于服务器未安装 buildx 的情况。

常用维护命令：

```bash
docker compose ps
docker compose logs -f --tail 100 geo-audit-service
docker compose restart geo-audit-service
docker compose down
```

---

## 环境变量

### 基础

```env
APP_ENV=development
APP_DEBUG=true
HOST=0.0.0.0
PORT=8023
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=15
REQUEST_RETRIES=3
MAX_SITEMAP_URLS=50
MAX_SITEMAP_INDEXES=10
CACHE_TTL_DAYS=7
CACHE_DIR=.cache/audits
MYSQL_ENABLED=false
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=site_geo_audit
MYSQL_USER=site_geo_audit
MYSQL_PASSWORD=
MYSQL_CONNECT_TIMEOUT_SECONDS=5
MYSQL_READ_TIMEOUT_SECONDS=15
MYSQL_WRITE_TIMEOUT_SECONDS=15
MYSQL_POOL_SIZE=5
MYSQL_POOL_MAX_OVERFLOW=10
MYSQL_POOL_TIMEOUT_SECONDS=10
MYSQL_POOL_RECYCLE_SECONDS=1800
MYSQL_POOL_PRE_PING=true
MYSQL_RECOVERY_PROBE_INTERVAL_SECONDS=1
MYSQL_STORE_RAW_HTML=false
MYSQL_STORE_PARSED_CONTENT=true
DISCOVERY_FETCH_CONCURRENCY=8
DEFAULT_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
ALLOW_PLAYWRIGHT=false
GOOGLE_RENDER_TIMEOUT_SECONDS=25
GOOGLE_RENDER_NETWORK_IDLE_SECONDS=5
ALLOW_BENCHMARK_PROXY_IPS=false
```

### AI 增强

```env
LLM_REQUEST_TIMEOUT_SECONDS=30
DEFAULT_OPENROUTER_MODEL=openai/gpt-5.6-sol
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

### Semrush

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

### MySQL 站点资产库

启用后，系统会将站点主记录、URL 清单、页面快照、站点知识图谱投影和任务记录写入 MySQL：

- `geo_sites`
- `geo_urls`
- `geo_page_snapshots`
- `geo_graph_entities`
- `geo_graph_edges`
- `geo_graph_evidence`
- `geo_site_graph_snapshots`
- `geo_audit_tasks`

初始化表结构：

```bash
PYTHONPATH=. .venv/bin/python scripts/init_mysql_schema.py
```

建表 SQL 位于：

- `sql/mysql/001_geo_asset_schema.sql`

启用后，`discovery` 会优先复用 MySQL 中的站点资产；传入 `force_refresh=true` 时会清空该站点的页面快照并重新抓取。

当前 MySQL 基础设施包含：

- 连接池复用：`MYSQL_POOL_SIZE` + `MYSQL_POOL_MAX_OVERFLOW`
- 借出前探活：`MYSQL_POOL_PRE_PING=true`
- 长连接回收：`MYSQL_POOL_RECYCLE_SECONDS`
- 短暂故障后的自动恢复尝试：`MYSQL_RECOVERY_PROBE_INTERVAL_SECONDS`
- 操作级重试：`MYSQL_RETRY_ATTEMPTS` + `MYSQL_RETRY_BACKOFF_MS`

异步任务创建时还支持：

- `build_knowledge_graph`: 是否在 discovery 完成后，基于 MySQL 已保存的页面快照构建站点知识图谱投影；默认 `true`

知识图谱构建是附加流程：

- 默认不会改变现有审计打分逻辑
- 构建失败不会让原有 audit 任务失败
- 当前图谱以 MySQL 投影表形式落地，适合做站点级实体、页面、关系和证据溯源
- 任务完成后可通过 `GET /api/v1/tasks/{task_id}/knowledge-graph` 拉取整张图谱结构数据

---

## API

推荐异步提交，显式指定任务类型：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -H "X-API-Token: YOUR_API_TOKEN" \
  -d '{"url":"https://example.com","task_type":"site_geo_only_audit","feedback_lang":"zh"}'
```

查询 `GET /api/v1/tasks/{task_id}`。纯GEO结果包含 `geo`、`discovery`、`observation`、`summary` 和逐页证据。
SGEO任务包含 `sgeo`、`discovery`、`observation`、`summary` 与逐页证据；`result.sgeo.score`、`summary.sgeo_score` 为统一分数。`summary.overall_score`、`summary.combined_score` 为该分数的兼容别名，新SGEO任务不再返回独立 `seo`、`geo` 或 `seo_summary`。
`summary.composite_geo_score`仅为新版GEO分的兼容别名。

完成后的任务另存到 `TASK_REPORT_DIR`（默认 `.data/reports`），以原 `task_id` 恢复结果，不受7天请求缓存过期影响。Docker 已挂载 `.data`，因此服务重启和容器重建后仍可通过 `/?task_id=...` 查看。旧版本写入 MySQL 的已完成任务在首次访问时恢复并补存文件；没有保存过的内存任务无法追溯恢复。

持有任务链接的人可直接阅读已完成报告、查看站点链接和导出 Markdown，无需 Token，也不会因地址中的 `force_refresh=1` 重新诊断。只读接口为 `GET /api/v1/public/reports/{task_id}`，其下的 `/pages`、`/pages/{page_id}/source` 和 `/report` 同样只读取已完成任务。新建任务、读取未完成任务和原业务接口仍需 Token。公开视图与保存的报告均排除 LLM API key 和自定义服务地址。

浏览器按报告结构校验本地HTML缓存；SGEO数据始终使用统一六维报告，即便从旧版报告入口调用也不读取已删除的旧评分字段。页面与报告脚本需重新验证缓存，避免旧模板把缺失字段显示为0分。

新版GEO分数是已测项的暂定估计；同时返回 `provisional`、`readiness_status`、`score_range` 与证据覆盖率。
出现阻断时标记 `blocked`；未知项不视为通过，分数不代表实际引用概率。

- `POST /api/v1/audit/geo`：同步新版GEO，支持传入已有discovery。
- `POST /api/v1/audit/seo`：同步SEO。
- `GET /api/v1/tasks/{task_id}/report`：导出GEO/SEO/SGEO Markdown报告。
- `GET /api/v1/demo/tasks/{task_id}/export.xlsx`：仅SEO任务的Excel导出。
- `POST /api/v1/audit/full`：兼容历史 `geo-audit-v3`，不用于新版GEO或组合审计。

完整参数和评分规则见 `/api-doc`，交互式接口定义见 `/docs`。
单页范围仍使用独立的检查通过率，见[单页面诊断说明](docs/single-page-diagnosis.md)，不冒充站点GEO分。
