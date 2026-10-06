"""Agent worker Lambda - invoked asynchronously by the API so the 3-agent run is not
limited by API Gateway's 30-second timeout. Progress is written to DynamoDB and polled by the UI."""
import json

from agents import orchestrator
from common import db


def handler(event, context):
    sub, job_id, barcode = event["sub"], event["job_id"], event["barcode"]
    try:
        report = orchestrator.run(sub, job_id, barcode, store=event.get("store"), auto_add=event.get("auto_add"))
        db.save_report(sub, barcode, report)
        db.finish_job(sub, job_id, "done", report=report)
        print(json.dumps({"metric": "job", "job_id": job_id, "status": "done",
                          "cost_usd": report["total_cost_usd"]}))
    except Exception as exc:
        print(json.dumps({"metric": "job", "job_id": job_id, "status": "error", "error": repr(exc)}))
        db.append_step(sub, job_id, {"agent": "System", "kind": "error", "text": str(exc)[:300]})
        db.finish_job(sub, job_id, "error", error=str(exc)[:300])
    return {"job_id": job_id}
