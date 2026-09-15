from __future__ import annotations

import json

import pytest

from dal.evaluation import load_case_set


def test_case_set_keeps_benchmarks_separate_and_marks_evaluability(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "format": "dal.benchmark-cases.v1",
        "name": "fixture",
        "source": {"artifact": "fixture"},
        "cases": [
            {
                "case_id": "ready", "category": "ontology",
                "question": "What is a customer?", "expected_object_ids": ["entity:customer"],
                "max_turns": 1, "max_tokens": 100, "source_refs": ["fixture#/customer"],
                "evaluable": True,
            },
            {
                "case_id": "blocked", "category": "freshness",
                "question": "Is it fresh?", "expected_object_ids": [],
                "max_turns": 1, "max_tokens": 100, "source_refs": ["fixture#/freshness"],
                "evaluable": False, "not_evaluable_reason": "snapshot not imported",
            },
        ],
    }), encoding="utf-8")

    case_set = load_case_set(path)

    assert [case.case_id for case in case_set.evaluable_cases] == ["ready"]
    assert [case.case_id for case in case_set.blocked_cases] == ["blocked"]


def test_unknown_case_fields_are_rejected(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "format": "dal.benchmark-cases.v1", "name": "bad", "source": {},
        "cases": [{
            "case_id": "bad", "question": "bad", "expected_object_ids": [],
            "max_turns": 1, "max_tokens": 1, "gold_query": "not benchmark vocabulary",
        }],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown fields"):
        load_case_set(path)
