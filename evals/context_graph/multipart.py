"""Compare joint retrieval with explicit fact plans; not an LLM planner evaluation."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.evaluation import CatalogSearchAdapter, evaluate, load_case_set
from .synthetic_catalog import synthetic_document


def run(root):
    cases = load_case_set(Path(__file__).with_name("multipart_cases.json"))
    bundle = BundleBuilder(root / "bundle").build(synthetic_document())
    adapter = CatalogSearchAdapter(CatalogService(BundleCatalog(bundle.bundle)))
    joint = evaluate("joint-question", [replace(case, retrieval_queries=()) for case in cases.evaluable_cases], adapter)
    planned = evaluate("fact-by-fact", cases.evaluable_cases, adapter)
    return {"scope": "Synthetic retrieval coverage with human-authored decomposition. Does not measure agent planning or SQL correctness.",
            "joint_question": asdict(joint), "fact_by_fact": asdict(planned)}


def main():
    with TemporaryDirectory(prefix="dal-multipart-") as temporary:
        report = run(Path(temporary))
    print(json.dumps(report, indent=2))
    return 0 if report["fact_by_fact"]["summary"]["success_at_budget_rate"] == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
