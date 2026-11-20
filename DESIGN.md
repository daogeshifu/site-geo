---
version: alpha
name: GEO Audit
description: 中文网站诊断工具中的爬虫测试目录与抓取结果
colors:
  primary: "#075DCC"
  ink: "#132238"
  muted: "#52647A"
  line: "#DCE4ED"
  surface: "#F5F8FB"
  fetch: "#087456"
  render: "#594396"
  warning: "#835918"
  danger: "#A43335"
typography:
  sans:
    fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", "PingFang SC", sans-serif'
  mono:
    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace'
rounded:
  panel: "12px"
  field: "6px"
spacing:
  page-max: "1168px"
  stage-gap: "22px"
components:
  run-button: {backgroundColor: "{colors.primary}", rounded: "{rounded.field}"}
  crawler-stage: {textColor: "{colors.ink}", rounded: "{rounded.panel}"}
  header-label: {textColor: "{colors.muted}"}
  table-divider: {backgroundColor: "{colors.line}"}
  content-preview: {backgroundColor: "{colors.surface}", textColor: "{colors.ink}"}
  fetch-label: {textColor: "{colors.fetch}"}
  render-label: {textColor: "{colors.render}"}
  status-warning: {textColor: "{colors.warning}"}
  status-error: {textColor: "{colors.danger}"}
---

# GEO Audit 爬虫测试界面

网站运营人员用这组页面核对某个标识向网站发送了什么，以及网站实际返回了什么。桌面在同一抓取阶段内并排展示请求头和内容，窄屏依次阅读。HTTP 状态、耗时、大小和内容类型共享一条指标栏。源码、响应头和抓取路径可分别展开。

## 视觉与实现

`app/web/static/css/google-crawler.css` 的根变量负责目录和各平台测试页的样式。primary、surface、fetch、render 和 warning 分别对应 `--blue`、`--soft`、`--green`、`--violet` 和 `--amber`。正文与技术值使用 `--sans`、`--mono`。页面宽度、阶段间距及两档圆角由 `--page-width`、`--stage-gap`、`--panel-radius` 和 `--field-radius` 控制。

平台名称是页面主标题，原始抓取、JavaScript 渲染是阶段标题。每个状态都附文字，绿色与紫色分别标记抓取与渲染。蓝色用于导航、主要操作与键盘焦点。错误原因紧邻对应的数据或输入项。

`crawler-stage.html` 和 `crawler-evidence.js` 共同呈现各平台的阶段。信息表用等宽字体显示字段、原始值和技术单位，正文预览使用正文字体。长 URL、User-Agent 和日志在容器内换行。源码可在有界区域内滚动和复制。等待动画遵循减少动态效果的系统设置。
