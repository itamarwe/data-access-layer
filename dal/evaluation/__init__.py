"""Offline context retrieval evaluation and paired ablation."""

from .ablation import AblationComparison, compare_variants
from .case_set import BenchmarkCaseSet, load_case_set
from .catalog_adapter import CatalogSearchAdapter, TokenCounter, Utf8TokenEstimate
from .gate import GateAssessment, QualityGate, assess_gate
from .model import (
    CaseResult, EvaluationCase, EvaluationRun, EvaluationSummary,
    SearchObservation,
)
from .runner import evaluate

__all__ = (
    "AblationComparison", "BenchmarkCaseSet", "CaseResult", "CatalogSearchAdapter",
    "EvaluationCase", "EvaluationRun", "EvaluationSummary", "GateAssessment",
    "QualityGate", "SearchObservation", "TokenCounter", "Utf8TokenEstimate",
    "assess_gate", "compare_variants", "evaluate",
    "load_case_set",
)
