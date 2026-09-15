"""Report exact-question development retrieval without exposing customer content."""

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from dal.application import BundleCatalog, CatalogService, SearchOptions
from dal.documents import load_document


def measure(document, service, token_budget):
    measurements = []
    for item in document["objects"]:
        if item["kind"] != "gold_query":
            continue
        started = time.perf_counter()
        response = service.search(item["question"], options=SearchOptions(token_budget=token_budget))
        elapsed = (time.perf_counter() - started) * 1000
        identifiers = {result.object.id for result in response.results}
        identifiers.update(result.id for result in response.also_matched)
        if response.relevant_gold_query:
            identifiers.add(response.relevant_gold_query.id)
        measurements.append((item["id"] in identifiers, elapsed,
                             response.estimated_tokens, response.capabilities.embedding == "available"))
    if not measurements:
        raise ValueError("catalog contains no gold questions to measure")
    latencies = sorted(row[1] for row in measurements)
    return {
        "evaluation_type": "development_exact_gold_question_retrieval",
        "cases": len(measurements), "hits": sum(row[0] for row in measurements),
        "response_budget": token_budget,
        "max_estimated_tokens": max(row[2] for row in measurements),
        "mean_estimated_tokens": round(statistics.mean(row[2] for row in measurements), 2),
        "mean_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": round(latencies[math.ceil(len(latencies) * .95) - 1], 2),
        "max_latency_ms": round(max(latencies), 2),
        "embedding_available_cases": sum(row[3] for row in measurements),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--tokens", type=int, default=1600)
    args = parser.parse_args()
    document = load_document(args.context.read_text(), "json" if args.context.suffix == ".json" else "yaml")
    print(json.dumps(measure(document, CatalogService(BundleCatalog(args.bundle)), args.tokens), indent=2))


if __name__ == "__main__":
    main()
