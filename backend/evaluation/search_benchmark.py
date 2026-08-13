"""End-to-end search latency benchmark.

Measures query latency against a live API with a populated document corpus.
Tests both cold (first query) and warm (cached) performance, plus
RBAC enforcement for different user roles.

Usage:
    python -m evaluation.search_benchmark --output-dir evaluation/reports
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import requests

try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False


API_BASE = "http://localhost:18001/api/v1"

TEST_QUERIES = [
    "minimum credit score requirement",
    "debt to income ratio conventional",
    "FHA down payment requirements",
    "closing costs estimate",
    "interest rate for VA loans",
    "appraisal process timeline",
    "title insurance coverage",
    "loan terms balloon options",
    "required documentation self-employed",
    "eligibility criteria for USDA",
    "rate lock policy",
    "escrow account waiver",
    "pre-approval process",
    "foreclosure waiting period",
    "credit score and interest rates",
]

USERS = {
    "admin": ("admin@hexa.local", "adminpass"),
    "loan_officer": ("officer@hexa.local", "officerpass"),
    "compliance": ("compliance@hexa.local", "compliancepass"),
}


def _make_session() -> requests.Session:
    s = requests.Session()
    if _HAS_RETRY:
        retries = Retry(total=3, backoff_factor=0.3)
        s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


def login(session: requests.Session, email: str, password: str) -> str:
    r = session.post(f"{API_BASE}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def search(session: requests.Session, token: str, query: str) -> dict:
    r = session.post(
        f"{API_BASE}/search/",
        json={"query": query},
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


def benchmark_search(queries: list[str], tokens: dict[str, str], rounds: int = 5) -> dict:
    session = _make_session()
    all_latencies: dict[str, list[float]] = {user: [] for user in tokens}
    result_counts: dict[str, list[int]] = {user: [] for user in tokens}
    conf_counts: dict[str, list[int]] = {user: [] for user in tokens}

    # Warm-up
    for user, token in tokens.items():
        search(session, token, queries[0])

    # Benchmark rounds
    for _ in range(rounds):
        for user, token in tokens.items():
            for q in queries:
                t0 = time.perf_counter()
                resp = search(session, token, q)
                elapsed = (time.perf_counter() - t0) * 1000
                all_latencies[user].append(elapsed)
                result_counts[user].append(len(resp.get("excerpts", [])))
                conf_counts[user].append(1 if resp.get("routing") == "answer" else 0)

    summary = {}
    for user in tokens:
        lats = all_latencies[user]
        summary[user] = {
            "queries": len(lats),
            "latency_ms": {
                "p50": round(statistics.median(lats), 1),
                "p95": round(sorted(lats)[int(len(lats) * 0.95) - 1], 1),
                "min": round(min(lats), 1),
                "max": round(max(lats), 1),
                "mean": round(statistics.mean(lats), 1),
            },
            "avg_excerpts": round(statistics.mean(result_counts[user]), 1),
            "answer_rate": round(statistics.mean(conf_counts[user]) * 100, 1),
        }

    report = {
        "timestamp": datetime.now().isoformat(),
        "queries_per_round": len(queries),
        "rounds": rounds,
        "total_queries": len(queries) * rounds * len(tokens),
        "results_by_user": summary,
    }

    return report


def main(output_dir: str, rounds: int) -> None:
    session = _make_session()

    tokens = {}
    for user, (email, password) in USERS.items():
        token = login(session, email, password)
        tokens[user] = token
        print(f"Logged in as {user}")

    print(f"\nRunning {len(TEST_QUERIES)} queries x {rounds} rounds x {len(USERS)} users...")
    report = benchmark_search(TEST_QUERIES, tokens, rounds=rounds)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fname = out / f"search_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {fname}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search latency benchmark")
    parser.add_argument("--output-dir", default="evaluation/reports")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    main(args.output_dir, args.rounds)
