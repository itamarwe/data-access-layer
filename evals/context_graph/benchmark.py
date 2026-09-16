"""Run reproducible synthetic retrieval checks through the production catalog service."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from dal.application import BundleCatalog, CatalogService, SearchOptions
from dal.compiler import BundleBuilder, FastEmbedder
from dal.evaluation import CatalogSearchAdapter, assess_gate, evaluate, load_case_set

from .synthetic_catalog import synthetic_document

CASES = Path(__file__).with_name("synthetic_cases.json")


def run_variant(root, mode, tokens, model, local_files_only):
    cases = load_case_set(CASES)
    document = synthetic_document()
    started = time.perf_counter()
    embedder = FastEmbedder(model, local_files_only=local_files_only) if mode == "hybrid" else None
    model_seconds = time.perf_counter() - started
    started = time.perf_counter()
    bundle = BundleBuilder(root, embedder).build(document).bundle
    build_seconds = time.perf_counter() - started
    adapter = CatalogSearchAdapter(
        CatalogService(BundleCatalog(bundle), embedder),
        options=SearchOptions(max_details=8, max_compact=20),
    )
    run = evaluate(mode, [replace(case, max_tokens=tokens) for case in cases.evaluable_cases], adapter)
    if mode == "hybrid" and any(not result.embedding_available for result in run.results):
        raise RuntimeError("Hybrid benchmark requires working embeddings; no BM25 fallback is scored.")
    gate = replace(cases.gate, maximum_mean_tokens=tokens)
    assessment = assess_gate(run, gate)
    return {
        **asdict(run),
        "token_budget": tokens,
        "embedding_model": model if embedder else None,
        "model_load_seconds": model_seconds,
        "build_seconds": build_seconds,
        "gate": asdict(gate),
        "gate_passed": assessment.meets_gate,
        "gate_failures": list(assessment.failures),
    }


def run_benchmark(mode="bm25", tokens=1600, model="BAAI/bge-small-en-v1.5", local_files_only=False):
    if mode not in {"bm25", "hybrid", "both"} or tokens < 512:
        raise ValueError("Choose bm25, hybrid, or both and a total token budget of at least 512.")
    document = synthetic_document()
    fingerprint = hashlib.sha256(CASES.read_bytes() + json.dumps(document, sort_keys=True).encode()).hexdigest()
    modes = ("bm25", "hybrid") if mode == "both" else (mode,)
    with TemporaryDirectory(prefix="dal-benchmark-") as temporary:
        variants = [run_variant(Path(temporary) / variant, variant, tokens, model, local_files_only)
                    for variant in modes]
    return {
        "format": "dal.synthetic-retrieval-benchmark.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split": "development",
        "fixture": "synthetic-library",
        "fixture_sha256": fingerprint,
        "object_count": len(document["objects"]),
        "token_measurement": "estimated_utf8_bytes_divided_by_four",
        "latency_scope": "search calls in fixture order, including first-query cost; model load and build reported separately",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "variants": variants,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", choices=("bm25", "hybrid", "both"), default="bm25")
    parser.add_argument("--tokens", type=int, default=1600, help="Estimated question + response tokens; minimum 512.")
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--local-files-only", action="store_true", help="Require cached model weights; do not download them.")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path as well as stdout.")
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(args.search, args.tokens, args.embedding_model, args.local_files_only)
        payload = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
    except (ImportError, OSError, RuntimeError, ValueError, StopIteration) as error:
        parser.exit(2, f"Benchmark could not run: {error}. Hybrid search needs the embeddings extra and a supported local model.\n")
    print(payload, end="")
    return 0 if all(variant["gate_passed"] for variant in report["variants"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
