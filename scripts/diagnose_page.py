"""Run one page diagnosis locally and save an independent JSON, without an API server."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.exceptions import AppError
from app.models.task import TaskAuditRequest
from app.services.audit.single_page import SinglePageAuditService


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--country")
    parser.add_argument("--language", choices=["en", "de", "nl", "fr", "zh", "es", "ar", "tr"])
    parser.add_argument("--feedback-lang", default="zh", choices=["zh", "en"])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = TaskAuditRequest(url=args.url, audit_scope="page", country=args.country,
                               target_locale=args.language, feedback_lang=args.feedback_lang)
    try:
        result = await SinglePageAuditService().audit(request.url, country=request.country,
                     target_locale=request.target_locale, feedback_lang=request.feedback_lang)
        payload = {"success": True, "request": request.model_dump(mode="json"), "result": result}
    except AppError as exc:
        payload = {"success": False, "request": request.model_dump(mode="json"),
                   "error": exc.message, "error_details": exc.errors}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": payload["success"], "output": str(output)}, ensure_ascii=True))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
