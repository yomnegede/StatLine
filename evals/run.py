"""Run a small, repeatable answer-quality check against the local StatLine API.

Usage: venv/bin/python -m evals.run --api http://127.0.0.1:8000
The report is saved locally under evals/runs/ and should be reviewed by a human.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases.json"


def normalized(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))


def get_json(url: str) -> object:
    with urlopen(url, timeout=45) as response:
        return json.load(response)


def ask(api: str, question: str) -> dict:
    request = Request(
        f"{api}/ask", data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def grade(case: dict, result: dict, leader: str | None = None) -> dict[str, bool]:
    """Check objective behavior; humans review claim-level accuracy separately."""
    sources = result.get("sources", [])
    answer = result.get("answer") or ""
    source_ids = {source["id"] for source in sources}
    citations = re.findall(r"\[Source: ([^\]]+)\]", answer)
    checks = {
        "expected_source_players": all(
            normalized(name) in {normalized(source["player"]) for source in sources}
            for name in case["expected_players"]
        ),
        "citations_reference_retrieved_sources": all(citation in source_ids for citation in citations),
    }
    if result.get("status") == "answered":
        from backend.answer_quality import uncited_stat_paragraphs
        checks["every_numeric_paragraph_cited"] = not uncited_stat_paragraphs(answer)
    if case["kind"] == "unsupported":
        checks["honest_scope"] = result.get("status") == "no_data" and bool(result.get("notice"))
    else:
        checks["answered"] = result.get("status") == "answered" and bool(answer)
        checks["has_citation"] = bool(citations)
    if case["kind"] == "named_average" and sources:
        source = next((source for source in sources if source["player"] == case["expected_players"][0]), None)
        match = re.search(r"averaging (\d+(?:\.\d+)?) pts", source["content"]) if source else None
        checks["states_source_average"] = bool(match and match[1] in answer)
    if case["kind"] == "season_leader" and leader:
        checks["names_scoring_leader"] = normalized(leader) in normalized(answer)
    if case["kind"] == "recent_leader" and sources:
        checks["names_recent_leader"] = normalized(sources[0]["player"]) in normalized(answer)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate StatLine answer quality")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--ids", nargs="*", help="Only run these case IDs")
    parser.add_argument("--expected-season", help="Fail if recommendations use a different NBA season, such as 2025-26")
    args = parser.parse_args()
    api = args.api.rstrip("/")
    cases = json.loads(CASES.read_text())
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]
        if len(cases) != len(set(args.ids)):
            parser.error("An --ids value does not match a case in cases.json")
    leaders = get_json(f"{api}/recommendations")
    leader = leaders[0]["name"] if leaders else None
    actual_season = leaders[0]["season"] if leaders else None
    season_check = bool(actual_season) and (not args.expected_season or actual_season == args.expected_season)
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "api": api,
              "recommendation_season": actual_season, "expected_season": args.expected_season,
              "recommendation_season_check": season_check, "cases": []}
    for case in cases:
        try:
            result = ask(api, case["question"])
            checks = grade(case, result, leader)
            item = {"id": case["id"], "question": case["question"], "checks": checks,
                    "passed": all(checks.values()), "answer": result.get("answer"),
                    "notice": result.get("notice"), "sources": result.get("sources", []),
                    "human_review": {"factuality": None, "relevance": None,
                                     "scope_honesty": None, "citation_support": None}}
        except Exception as error:
            item = {"id": case["id"], "question": case["question"], "passed": False,
                    "error": f"{type(error).__name__}: {error}"}
        report["cases"].append(item)
        print(f"{'PASS' if item['passed'] else 'FAIL'} {case['id']}")
    output = ROOT / "runs" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{sum(item['passed'] for item in report['cases'])}/{len(cases)} automated checks passed; report: {output}")
    print(f"Recommendation season: {actual_season or 'unavailable'}" +
          (f" (expected {args.expected_season})" if args.expected_season else ""))
    return 0 if season_check and all(item["passed"] for item in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
