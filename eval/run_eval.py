#!/usr/bin/env python3
"""
Northwind Expense Reviewer — Evaluation Harness
================================================
Usage:
    python eval/run_eval.py --cases eval/sample_cases.json [--url http://localhost:8000]

Drop in any JSON file that follows the schema described in README.md.
The harness creates real API objects (employees, submissions, receipts) for verdict
tests, runs the AI review, checks outcomes, then cleans up.

Exit codes:
    0  all tests passed
    1  one or more tests failed
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Northwind eval harness")
    p.add_argument("--cases", required=True, help="Path to test-cases JSON file")
    p.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    p.add_argument("--output", default=None, help="Where to write the JSON report (default: eval/results_<ts>.json)")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    return p.parse_args()


# ── API helpers ───────────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, base_url: str, timeout: int):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def post(self, path, **kwargs):
        return self.session.post(f"{self.base}{path}", timeout=self.timeout, **kwargs)

    def get(self, path, **kwargs):
        return self.session.get(f"{self.base}{path}", timeout=self.timeout, **kwargs)

    def delete(self, path, **kwargs):
        return self.session.delete(f"{self.base}{path}", timeout=self.timeout, **kwargs)


# ── Result helpers ────────────────────────────────────────────────────────────

def make_result(case_id, description, case_type, passed, score, details, error=None):
    return {
        "id": case_id,
        "description": description,
        "type": case_type,
        "passed": passed,
        "score": score,          # 0.0–1.0
        "details": details,
        "error": error,
    }


# ── Policy Q&A test ───────────────────────────────────────────────────────────

def run_qa_case(client: APIClient, case: dict) -> dict:
    cid   = case["id"]
    desc  = case.get("description", cid)
    exp   = case["expected"]

    try:
        resp = client.post("/policy-qa", json={"question": case["question"]})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return make_result(cid, desc, "policy_qa", False, 0.0, {}, error=str(e))

    actual_in_scope = data.get("is_in_scope", None)
    actual_answer   = data.get("answer", "")
    actual_citations = data.get("citations", [])

    checks = {}
    scores = []

    # 1. Scope classification
    if "is_in_scope" in exp:
        ok = actual_in_scope == exp["is_in_scope"]
        checks["scope_correct"] = ok
        scores.append(1.0 if ok else 0.0)

    # 2. Citation presence
    if exp.get("has_citations"):
        ok = len(actual_citations) > 0
        checks["has_citations"] = ok
        scores.append(1.0 if ok else 0.0)

    # 3. Answer contains expected keywords (any match counts)
    if "answer_mentions_any" in exp and actual_in_scope:
        keywords = exp["answer_mentions_any"]
        answer_lower = actual_answer.lower()
        ok = any(str(kw).lower() in answer_lower for kw in keywords)
        checks["answer_mentions_any"] = ok
        checks["answer_mentions_any_keywords"] = keywords
        scores.append(1.0 if ok else 0.0)

    # 4. Citation correctness: expected doc refs appear in citations
    if "citations_contain" in exp:
        joined = " ".join(actual_citations).lower()
        ok = all(str(ref).lower() in joined for ref in exp["citations_contain"])
        checks["citations_contain"] = ok
        scores.append(1.0 if ok else 0.0)

    score  = sum(scores) / len(scores) if scores else 1.0
    passed = all(v for k, v in checks.items() if isinstance(v, bool))

    return make_result(cid, desc, "policy_qa", passed, score, {
        "actual_is_in_scope": actual_in_scope,
        "actual_answer_snippet": actual_answer[:200],
        "actual_citations": actual_citations,
        "checks": checks,
    })


# ── Verdict test ──────────────────────────────────────────────────────────────

def run_verdict_case(client: APIClient, case: dict) -> dict:
    cid  = case["id"]
    desc = case.get("description", cid)
    exp  = case["expected"]

    cleanup_ids = {"employee_id": None, "submission_id": None}

    try:
        # 1. Get or create employee
        emp_payload = case["employee"]
        emp_resp = client.post("/employees/", json=emp_payload)
        if emp_resp.status_code == 409:
            # Already exists from a previous run — fetch it
            emp_resp = client.get(f"/employees/{emp_payload['employee_id']}")
        emp_resp.raise_for_status()
        emp = emp_resp.json()
        cleanup_ids["employee_id"] = emp["id"]

        # 2. Create submission
        trip = case["trip"]
        sub_resp = client.post("/submissions/", json={
            "employee_id": emp["id"],
            "trip_purpose": trip["trip_purpose"],
            "trip_dates":   trip["trip_dates"],
        })
        sub_resp.raise_for_status()
        sub = sub_resp.json()
        cleanup_ids["submission_id"] = sub["id"]

        # 3. Upload receipt as a text file
        content  = case["receipt_content"].encode()
        filename = case.get("receipt_filename", f"eval_receipt_{cid}.txt")
        upload = client.post(
            f"/submissions/{sub['id']}/receipts",
            files={"file": (filename, content, "text/plain")},
        )
        upload.raise_for_status()

        # 4. Run AI review
        review = client.post(f"/submissions/{sub['id']}/review")
        review.raise_for_status()

        # 5. Fetch updated submission with verdicts
        detail = client.get(f"/submissions/{sub['id']}")
        detail.raise_for_status()
        sub_detail = detail.json()

    except Exception as e:
        return make_result(cid, desc, "verdict", False, 0.0, {
            "cleanup_ids": cleanup_ids,
        }, error=str(e))

    # Collect all verdicts across all receipts
    all_verdicts = [
        v
        for r in sub_detail.get("receipts", [])
        for v in r.get("verdicts", [])
    ]

    if not all_verdicts:
        return make_result(cid, desc, "verdict", False, 0.0,
                           {"error": "No verdicts returned"})

    # Use the first verdict for single-receipt eval cases
    v = all_verdicts[0]
    actual_verdict     = v.get("verdict")
    actual_citations   = v.get("policy_citations", [])
    actual_confidence  = v.get("confidence", 0.0) or 0.0

    checks = {}
    scores = []

    # 1. Verdict value
    if "verdict" in exp:
        ok = actual_verdict == exp["verdict"]
        checks["verdict_correct"] = ok
        checks["expected_verdict"] = exp["verdict"]
        checks["actual_verdict"]   = actual_verdict
        scores.append(1.0 if ok else 0.0)

    # 2. Citation presence
    if exp.get("has_citations"):
        ok = len(actual_citations) > 0
        checks["has_citations"] = ok
        scores.append(1.0 if ok else 0.0)

    # 3. Citation correctness
    if "citations_contain" in exp:
        joined = " ".join(actual_citations).lower()
        ok = all(str(ref).lower() in joined for ref in exp["citations_contain"])
        checks["citations_contain"] = ok
        scores.append(1.0 if ok else 0.0)

    # 4. Confidence threshold
    if "confidence_min" in exp:
        ok = actual_confidence >= exp["confidence_min"]
        checks["confidence_ok"] = ok
        checks["actual_confidence"] = round(actual_confidence, 3)
        checks["required_confidence_min"] = exp["confidence_min"]
        scores.append(1.0 if ok else 0.0)

    score  = sum(scores) / len(scores) if scores else 1.0
    passed = all(v for k, v in checks.items() if isinstance(v, bool))

    return make_result(cid, desc, "verdict", passed, score, {
        "actual_verdict":    actual_verdict,
        "actual_citations":  actual_citations,
        "actual_confidence": round(actual_confidence, 3),
        "actual_reason_snippet": v.get("reason", "")[:200],
        "checks": checks,
    })


# ── Aggregated metrics ────────────────────────────────────────────────────────

def aggregate(results: list[dict]) -> dict:
    total       = len(results)
    passed      = sum(1 for r in results if r["passed"])
    avg_score   = sum(r["score"] for r in results) / total if total else 0

    qa_results      = [r for r in results if r["type"] == "policy_qa"]
    verdict_results = [r for r in results if r["type"] == "verdict"]

    def type_metrics(subset):
        if not subset:
            return {"count": 0, "pass_rate": None, "avg_score": None}
        n = len(subset)
        return {
            "count":      n,
            "pass_rate":  round(sum(1 for r in subset if r["passed"]) / n, 3),
            "avg_score":  round(sum(r["score"] for r in subset) / n, 3),
        }

    # Scope accuracy from Q&A tests only
    scope_checks = [
        r["details"]["checks"].get("scope_correct")
        for r in qa_results
        if isinstance(r["details"].get("checks", {}).get("scope_correct"), bool)
    ]
    scope_accuracy = round(sum(scope_checks) / len(scope_checks), 3) if scope_checks else None

    # Citation coverage across all test types
    citation_checks = []
    for r in results:
        c = r["details"].get("checks", {}).get("has_citations")
        if isinstance(c, bool):
            citation_checks.append(c)
    citation_coverage = round(sum(citation_checks) / len(citation_checks), 3) if citation_checks else None

    # Verdict accuracy
    verdict_accuracy_checks = [
        r["details"]["checks"].get("verdict_correct")
        for r in verdict_results
        if isinstance(r["details"].get("checks", {}).get("verdict_correct"), bool)
    ]
    verdict_accuracy = round(sum(verdict_accuracy_checks) / len(verdict_accuracy_checks), 3) if verdict_accuracy_checks else None

    # OOS refusal rate
    oos_results = [
        r for r in qa_results
        if r["details"].get("actual_is_in_scope") is False
        or (r["details"].get("checks", {}).get("scope_correct") is not None
            and not r["details"].get("actual_is_in_scope", True))
    ]
    oos_rate = round(
        sum(1 for r in oos_results if r["details"]["checks"].get("scope_correct")) / len(oos_results), 3
    ) if oos_results else None

    return {
        "total_cases":        total,
        "passed":             passed,
        "failed":             total - passed,
        "overall_pass_rate":  round(passed / total, 3) if total else 0,
        "avg_score":          round(avg_score, 3),
        "verdict_accuracy":   verdict_accuracy,
        "citation_coverage":  citation_coverage,
        "qa_scope_accuracy":  scope_accuracy,
        "oos_refusal_rate":   oos_rate,
        "by_type": {
            "policy_qa": type_metrics(qa_results),
            "verdict":   type_metrics(verdict_results),
        },
    }


# ── Printer ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def cprint(text, color=""):
    print(f"{color}{text}{RESET}")

def print_results(results: list[dict], metrics: dict):
    cprint("\n" + "═" * 68, BOLD)
    cprint("  NORTHWIND EXPENSE REVIEWER — EVAL RESULTS", BOLD)
    cprint("═" * 68, BOLD)

    for r in results:
        icon   = f"{GREEN}✓{RESET}" if r["passed"] else f"{RED}✗{RESET}"
        score  = f"{r['score']:.0%}"
        label  = f"[{r['type'][:7]}]"
        status = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        print(f"  {icon} {label:<10} {r['id']:<15} {r['description'][:35]:<36} {score:>5}  {status}")
        if r.get("error"):
            cprint(f"       ERROR: {r['error']}", RED)

    cprint("\n" + "─" * 68, BOLD)
    cprint("  METRICS SUMMARY", BOLD)
    cprint("─" * 68, BOLD)

    def fmt(val):
        if val is None: return f"{YELLOW}n/a{RESET}"
        return f"{GREEN}{val:.0%}{RESET}" if val >= 0.8 else f"{RED}{val:.0%}{RESET}"

    rows = [
        ("Overall pass rate",      metrics["overall_pass_rate"]),
        ("Verdict accuracy",       metrics["verdict_accuracy"]),
        ("Citation coverage",      metrics["citation_coverage"]),
        ("QA scope accuracy",      metrics["qa_scope_accuracy"]),
        ("OOS refusal rate",       metrics["oos_refusal_rate"]),
    ]
    for label, val in rows:
        print(f"  {label:<30} {fmt(val)}")

    pf = metrics["passed"]
    tf = metrics["total_cases"]
    color = GREEN if pf == tf else (YELLOW if pf >= tf * 0.8 else RED)
    cprint(f"\n  {pf}/{tf} tests passed  (avg score: {metrics['avg_score']:.0%})", color + BOLD)
    cprint("═" * 68 + "\n", BOLD)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"ERROR: cases file not found: {cases_path}", file=sys.stderr)
        sys.exit(1)

    with cases_path.open() as f:
        suite = json.load(f)

    test_cases = suite.get("test_cases", [])
    if not test_cases:
        print("ERROR: no test_cases found in JSON", file=sys.stderr)
        sys.exit(1)

    print(f"\nLoaded {len(test_cases)} test case(s) from {cases_path}")
    print(f"Target API: {args.url}\n")

    client  = APIClient(args.url, args.timeout)
    results = []

    for i, case in enumerate(test_cases, 1):
        case_type = case.get("type")
        print(f"  [{i}/{len(test_cases)}] {case['id']} ({case_type}) … ", end="", flush=True)
        t0 = time.time()

        if case_type == "policy_qa":
            result = run_qa_case(client, case)
        elif case_type == "verdict":
            result = run_verdict_case(client, case)
        else:
            result = make_result(
                case["id"], case.get("description",""), case_type or "unknown",
                False, 0.0, {}, error=f"Unknown case type: {case_type!r}"
            )

        elapsed = time.time() - t0
        status  = "PASS" if result["passed"] else "FAIL"
        print(f"{status}  ({elapsed:.1f}s)")
        results.append(result)

    metrics = aggregate(results)
    print_results(results, metrics)

    # Write JSON report
    output_path = args.output or f"eval/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_at":    datetime.now().isoformat(),
        "api_url":   args.url,
        "cases_file": str(cases_path),
        "metrics":   metrics,
        "results":   results,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to: {output_path}\n")

    sys.exit(0 if metrics["passed"] == metrics["total_cases"] else 1)


if __name__ == "__main__":
    main()
