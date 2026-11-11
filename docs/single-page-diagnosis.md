# 单页面诊断

异步接口仍为 `POST /api/v1/tasks/audit`，传入 `audit_scope: "page"`：

```json
{
  "url": "https://consumer.huawei.com/de/wearables/watch-gt6-pro/buy/",
  "audit_scope": "page",
  "country": "DE",
  "target_locale": "de",
  "feedback_lang": "zh",
  "mode": "standard"
}
```

通过 `GET /api/v1/tasks/{task_id}` 读取结果。`audit_scope` 默认 `site`，原有站点诊断继续使用原流程。页面模式强制 `full_audit=false`、`max_pages=1`、关闭图谱，不接受 premium 模式。

单页面模式只 GET 输入 URL，不访问主页、其他链接、robots.txt、sitemap、外链服务、脚本或图片，不执行 JavaScript。页面内链接只读取属性，不访问其目标。HTTP 重定向不会自动跟随：任务失败并在 `error_details.redirect_url` 记录目标，避免把主页或其他页面的结果归到当前链接。HTTP 错误、非 HTML 响应也不生成页面分数。

诊断除基础标签外，还检查标签数量、标题与描述长度、canonical 地址及归一目标、标题跳级与空标题、正文深度、图片替代文本与尺寸、链接可访问名称、HTTP 混合资源、head 阻塞脚本、HTML 体积、JSON-LD 语法、Product/Offer 字段以及 hreflang。每项包含 `evidence`。长度阈值、正文分词、图片尺寸、潜在阻塞、canonical 不同地址等仅是优化提示，不能直接认定为排名或性能故障；未在浏览器测量 Core Web Vitals。商品页不套用文章作者或发布日期要求。页面类型由当前页面结构化数据及购买路径推断。

`page.findings` 收集全部未通过项，`severity=issue` 为明确检查问题，`severity=advisory` 为需结合页面用途确认的优化建议；`page.issues` 与 `page.advisories` 分开输出。版本 `single-page-checks-v2` 的分数仅为适用必检项通过率，建议项不计入分母，不等同于原来的站点 GEO/SEO 综合分数。没有请求 robots.txt，因此文档可索引检查不代表完整的爬虫可访问性。

国家使用两字母代码，作为请求语言偏好和结果元数据；不会改变本机出口 IP，不模拟当地网络位置。页面语言支持 `de/es/en/ar/tr` 等；报告语言支持 `zh/en`。语言不匹配会作为检查失败记录，绝不自动切换到其他语言链接。

页面结果缓存按完整规范化 URL（包括路径和查询参数，不含 fragment）、国家、语言及任务参数隔离，不读写站点 MySQL discovery 快照。缓存保存在现有文件缓存目录；`force_refresh=true` 可绕过结果缓存。任务状态保留在当前 API 进程内存中。

结果包含 `requested_url`、`final_url`、`audited_urls`、`audited_page_count`、`country`、`target_locale`、`detected_language`、`page`、`page_diagnostics` 和 `summary`，便于关联表格原记录。

无需启动 API，可在项目目录直接运行：

```powershell
.\.venv\Scripts\python.exe scripts/diagnose_page.py "https://consumer.huawei.com/de/wearables/watch-gt6-pro/buy/" --country DE --language de --output outputs/de-watch-gt6-pro.json
```

此命令每次只诊断指定链接，并把成功结果或失败原因保存到独立 JSON；不连接站点资产数据库。
