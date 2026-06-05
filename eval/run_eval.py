#!/usr/bin/env python3
"""
Northwind evaluation harness.

Usage:
  python eval/run_eval.py --fixture eval/fixtures/example_expected.json
  python eval/run_eval.py --fixture held_out.json --api-url https://your-deploy.com

Expected JSON schema:
{
  "line_items": [
    {
      "submission_folder": "03_dinner_over_cap",
      "receipt_filename": "04_dinner_alinea.pdf",
      "expected_verdict": "flagged",
      "expected_doc_ids": ["TEP-002"]
    }
  ],
  "policy_questions": [
    {
      "question": "What is the solo travel dinner cap?",
      "should_refuse": false,
      "expected_doc_ids": ["TEP-002"]
    },
    {
      "question": "Who won the Super Bowl in 1999?",
      "should_refuse": true
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

# Allow running from repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Employee, LineItem, Receipt, Submission  # noqa: E402
from app.services.policy_chat import policy_chat  # noqa: E402
from app.services.policy_index import policy_index  # noqa: E402
from app.services.receipt_parser import receipt_parser  # noqa: E402
from app.services.reviewer import expense_reviewer  # noqa: E402


VERDICT_ALIASES = {
    "approve": "compliant",
    "compliant": "compliant",
    "flag": "flagged",
    "flagged": "flagged",
    "reject": "rejected",
    "rejected": "rejected",
    "ambiguous": "needs_review",
    "needs_review": "needs_review",
}


def normalize_verdict(v: str) -> str:
    return VERDICT_ALIASES.get(v.lower().strip(), v.lower().strip())


def eval_local_line_items(cases: list[dict]) -> dict:
    init_db()
    policy_index.ensure_indexed()
    db = SessionLocal()
    correct = 0
    citation_hits = 0
    results = []

    try:
        for case in cases:
            folder = case["submission_folder"]
            fname = case["receipt_filename"]
            seed = settings.resolve_path(settings.submissions_seed_dir)
            info = json.loads((seed / folder / "employee_info.json").read_text())
            emp = db.query(Employee).filter(Employee.employee_id == info["employee_id"]).first()
            ctx = {
                "employee_id": info["employee_id"],
                "name": info["name"],
                "grade": info["grade"],
                "department": info["department"],
                "trip_purpose": info["trip_purpose"],
                "trip_dates": info["trip_dates"],
            }
            path = seed / folder / "receipts" / fname
            extracted, text = receipt_parser.parse(path, "application/pdf")
            review = expense_reviewer.review_line(text, extracted, ctx)
            pred = review.verdict.value
            exp = normalize_verdict(case["expected_verdict"])
            ok = pred == exp
            if ok:
                correct += 1
            cited_docs = {c.document_id.upper() for c in review.policy_citations}
            expected_docs = {d.upper() for d in case.get("expected_doc_ids", [])}
            cite_ok = not expected_docs or expected_docs & cited_docs
            if cite_ok:
                citation_hits += 1
            results.append(
                {
                    "case": f"{folder}/{fname}",
                    "expected": exp,
                    "predicted": pred,
                    "verdict_match": ok,
                    "citation_match": cite_ok,
                    "confidence": review.confidence,
                }
            )
    finally:
        db.close()

    n = len(cases) or 1
    return {
        "verdict_accuracy": correct / n,
        "citation_accuracy": citation_hits / n,
        "details": results,
    }


def eval_policy_questions(questions: list[dict]) -> dict:
    policy_index.ensure_indexed()
    correct_refusal = 0
    citation_hits = 0
    details = []

    for q in questions:
        resp = policy_chat.ask(q["question"])
        should_refuse = q.get("should_refuse", False)
        refusal_ok = resp.refused == should_refuse
        if refusal_ok:
            correct_refusal += 1
        cited = {c.document_id.upper() for c in resp.citations}
        expected = {d.upper() for d in q.get("expected_doc_ids", [])}
        cite_ok = should_refuse or not expected or (expected & cited)
        if cite_ok:
            citation_hits += 1
        details.append(
            {
                "question": q["question"][:80],
                "refused": resp.refused,
                "should_refuse": should_refuse,
                "refusal_correct": refusal_ok,
                "citation_match": cite_ok,
            }
        )

    n = len(questions) or 1
    return {
        "refusal_accuracy": correct_refusal / n,
        "citation_accuracy": citation_hits / n,
        "details": details,
    }


def eval_via_api(api_url: str, fixture: dict) -> dict:
    """Optional HTTP mode for deployed instances (subset of metrics)."""
    client = httpx.Client(base_url=api_url.rstrip("/"), timeout=120.0)
    policy_results = []
    for q in fixture.get("policy_questions", []):
        r = client.post("/api/policy/ask", json={"question": q["question"]})
        r.raise_for_status()
        data = r.json()
        policy_results.append(
            {
                "question": q["question"][:80],
                "refused": data["refused"],
                "should_refuse": q.get("should_refuse", False),
                "refusal_correct": data["refused"] == q.get("should_refuse", False),
            }
        )
    n = len(policy_results) or 1
    return {
        "refusal_accuracy": sum(p["refusal_correct"] for p in policy_results) / n,
        "policy_details": policy_results,
        "note": "Line-item API eval requires creating submissions; use local mode for full harness.",
    }


def main():
    parser = argparse.ArgumentParser(description="Northwind eval harness")
    parser.add_argument("--fixture", required=True, help="Path to expected outcomes JSON")
    parser.add_argument("--api-url", help="If set, run policy Q&A against deployed API")
    parser.add_argument("--output", help="Write JSON report to file")
    args = parser.parse_args()

    fixture = json.loads(Path(args.fixture).read_text())
    report = {"fixture": str(args.fixture)}

    if args.api_url:
        report["api"] = eval_via_api(args.api_url, fixture)
    else:
        if not settings.openai_api_key:
            print("ERROR: Set OPENAI_API_KEY for local eval.", file=sys.stderr)
            sys.exit(1)
        if fixture.get("line_items"):
            report["line_items"] = eval_local_line_items(fixture["line_items"])
        if fixture.get("policy_questions"):
            report["policy_questions"] = eval_policy_questions(
                fixture["policy_questions"]
            )

    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
