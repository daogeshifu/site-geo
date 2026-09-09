"""Excel export for the SEO issue backlog and task URL inventory."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import xlsxwriter

from app.core.exceptions import AppError
from app.services.reporting.site_pages import task_site_pages


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_LABELS = {"critical": "紧急", "high": "高", "medium": "常规", "low": "低"}
SOURCE_LABELS = {
    "discovery": "关键页发现",
    "seo_sample": "SEO 采样",
    "full_audit": "扩展采样",
    "sitemap": "Sitemap",
    "internal_link": "站内链接",
}
CHECK_LABELS = {
    "CHK-001": "Robots", "CHK-002": "站点地图", "CHK-003": "数据追踪",
    "CHK-004": "HTTPS", "CHK-005": "主域统一", "CHK-006": "URL 规范",
    "CHK-007": "结构化数据", "CHK-008": "HTTP 状态", "CHK-009": "移动适配",
    "CHK-010": "页面性能", "CHK-011": "多语言", "CHK-012": "索引指令",
    "CHK-013": "JS 渲染", "CHK-014": "页面标题", "CHK-015": "页面描述",
    "CHK-016": "标题层级", "CHK-017": "规范链接", "CHK-018": "语言声明",
    "CHK-019": "图片文本", "CHK-020": "内部链接", "CHK-021": "页面体量",
    "CHK-022": "图片加载", "CHK-023": "内容深度", "CHK-024": "内容可信度",
    "CHK-025": "内容引用", "CHK-026": "AI 可见性",
}


def _text(value, fallback="") -> str:
    return fallback if value is None or value == "" else str(value)


def _local_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return None


def _safe_filename(task) -> str:
    domain = task.domain or urlparse(task.url).hostname or "site"
    safe_domain = re.sub(r"[^A-Za-z0-9._-]+", "-", domain).strip("-.") or "site"
    return f"{safe_domain}-seo-audit.xlsx"


def _workbook_formats(workbook):
    return {
        "title": workbook.add_format({"font_name": "Arial", "font_size": 15, "bold": True, "font_color": "#183F43"}),
        "meta": workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": "#7A8E92"}),
        "header": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#FFFFFF", "bg_color": "#183F43", "align": "center", "valign": "vcenter", "border": 0}),
        "text": workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#405B61", "valign": "top", "text_wrap": True, "bottom": 1, "bottom_color": "#E7EDED"}),
        "center": workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#405B61", "align": "center", "valign": "top", "bottom": 1, "bottom_color": "#E7EDED"}),
        "date": workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#405B61", "num_format": "yyyy-mm-dd hh:mm:ss", "align": "center", "valign": "top", "bottom": 1, "bottom_color": "#E7EDED"}),
        "url": workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": "#287D72", "underline": True, "valign": "top", "text_wrap": True, "bottom": 1, "bottom_color": "#E7EDED"}),
        "p0": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#B84C38", "bg_color": "#FDEBE7", "align": "center", "valign": "top", "bottom": 1, "bottom_color": "#E7EDED"}),
        "p1": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#A96A28", "bg_color": "#FFF2E3", "align": "center", "valign": "top", "bottom": 1, "bottom_color": "#E7EDED"}),
        "p2": workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "#687E7D", "bg_color": "#EEF4F3", "align": "center", "valign": "top", "bottom": 1, "bottom_color": "#E7EDED"}),
    }


def _write_sheet_header(sheet, title: str, context: str, headers: list[str], formats):
    sheet.hide_gridlines(2)
    sheet.write(1, 0, title, formats["title"])
    sheet.write(2, 0, context, formats["meta"])
    sheet.set_row(1, 24)
    sheet.set_row(4, 28)
    for col, header in enumerate(headers):
        sheet.write(4, col, header, formats["header"])
    sheet.freeze_panes(5, 0)


def build_seo_excel_export(task) -> tuple[bytes, str]:
    if task.status != "completed" or not task.result:
        raise AppError(409, "task is not completed yet")
    if task.task_type != "site_seo_audit":
        raise AppError(409, "Excel export is only available for site SEO audits")

    seo = task.result.get("seo") or {}
    discovery = task.result.get("discovery") or {}
    issues = sorted(
        seo.get("issues_table") or [],
        key=lambda item: (
            PRIORITY_ORDER.get(item.get("priority"), 99),
            SEVERITY_ORDER.get(item.get("severity"), 99),
            item.get("issue_id", ""),
        ),
    )
    checks = seo.get("coverage_checks") or []
    pages = task_site_pages(task)
    domain = discovery.get("domain") or task.domain or urlparse(task.url).hostname or task.url
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    context = f"站点：{domain}    审计地址：{task.url}    导出时间：{generated_at}"

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {
        "in_memory": True,
        "strings_to_formulas": False,
        "strings_to_urls": False,
    })
    workbook.set_properties({"title": f"{domain} SEO 审计", "subject": "问题清单与链接清单"})
    formats = _workbook_formats(workbook)

    issue_headers = ["序号", "问题类型", "检查事项", "优先级", "重要程度", "问题描述", "影响", "问题示例 / 证据", "建议", "负责人", "工作量", "实施难度", "状态"]
    issue_sheet = workbook.add_worksheet("问题清单")
    issue_sheet.set_tab_color("#183F43")
    _write_sheet_header(issue_sheet, "SEO 审计问题清单", context, issue_headers, formats)
    issue_sheet.set_column("A:A", 7)
    issue_sheet.set_column("B:B", 15)
    issue_sheet.set_column("C:C", 15)
    issue_sheet.set_column("D:E", 10)
    issue_sheet.set_column("F:I", 32)
    issue_sheet.set_column("J:J", 18)
    issue_sheet.set_column("K:M", 13)
    for row_index, issue in enumerate(issues, start=5):
        coverage = next((item for item in checks if item.get("summary") == issue.get("description")), {})
        check_item = issue.get("check_item") or CHECK_LABELS.get(coverage.get("id"), "站点检查")
        priority = _text(issue.get("priority"), "-")
        priority_format = formats.get(priority.lower(), formats["center"])
        values = [
            row_index - 4,
            _text(issue.get("category"), "-"),
            check_item,
            priority,
            SEVERITY_LABELS.get(issue.get("severity"), _text(issue.get("severity"), "-")),
            _text(issue.get("description"), "-"),
            _text(issue.get("seo_impact"), "-"),
            _text(issue.get("evidence"), "未记录"),
            _text(issue.get("recommendation"), "-"),
            _text(issue.get("owner_team"), "未分配"),
            _text(issue.get("estimated_effort"), "未评估"),
            _text(issue.get("implementation_difficulty"), "未评估"),
            _text(issue.get("status"), "todo"),
        ]
        issue_sheet.set_row(row_index, 56)
        for col, value in enumerate(values):
            cell_format = priority_format if col == 3 else formats["center"] if col in {0, 4, 10, 11, 12} else formats["text"]
            issue_sheet.write(row_index, col, value, cell_format)
    issue_last_row = max(5, 4 + len(issues))
    issue_sheet.autofilter(4, 0, issue_last_row, len(issue_headers) - 1)

    link_headers = ["序号", "页面类型", "页面标题", "URL", "内容字数", "状态码", "抓取时间", "响应耗时（ms）", "最终 URL", "发现来源"]
    link_sheet = workbook.add_worksheet("链接清单")
    link_sheet.set_tab_color("#6FA99D")
    _write_sheet_header(link_sheet, "站点链接清单", context, link_headers, formats)
    link_sheet.set_column("A:A", 7)
    link_sheet.set_column("B:B", 15)
    link_sheet.set_column("C:C", 30)
    link_sheet.set_column("D:D", 48)
    link_sheet.set_column("E:F", 11)
    link_sheet.set_column("G:G", 20)
    link_sheet.set_column("H:H", 15)
    link_sheet.set_column("I:I", 48)
    link_sheet.set_column("J:J", 15)
    for row_index, page in enumerate(pages, start=5):
        fetched_at = _local_datetime(page.get("fetched_at"))
        status_code = page.get("status_code") if page.get("status_code") else "未采样"
        word_count = page.get("word_count") if page.get("word_count") is not None else "未记录"
        values = [
            row_index - 4,
            _text(page.get("page_type"), "页面"),
            _text(page.get("title"), "未记录"),
            _text(page.get("url"), "-"),
            word_count,
            status_code,
            fetched_at or "未记录",
            page.get("response_time_ms") if page.get("response_time_ms") is not None else "未记录",
            _text(page.get("final_url"), "未记录"),
            SOURCE_LABELS.get(page.get("discovery_source"), _text(page.get("discovery_source"), "未记录")),
        ]
        link_sheet.set_row(row_index, 36)
        for col, value in enumerate(values):
            cell_format = formats["date"] if col == 6 and fetched_at else formats["center"] if col in {0, 1, 4, 5, 7, 9} else formats["text"]
            if col in {3, 8} and isinstance(value, str) and value.startswith(("http://", "https://")):
                link_sheet.write_url(row_index, col, value, formats["url"], value)
            else:
                link_sheet.write(row_index, col, value, cell_format)
    link_last_row = max(5, 4 + len(pages))
    link_sheet.autofilter(4, 0, link_last_row, len(link_headers) - 1)

    workbook.close()
    return output.getvalue(), _safe_filename(task)
