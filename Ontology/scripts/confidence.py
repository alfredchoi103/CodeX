from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Mapping


WEIGHTS = {
    "crossSourceAgreement": 0.25,
    "evidenceCoverage": 0.20,
    "runtimeSupport": 0.20,
    "semanticSpecificity": 0.15,
    "constraintConsistency": 0.10,
    "counterEvidenceAssessment": 0.10,
}
COUNTER_EVIDENCE_SCORES = frozenset({0, 25, 50, 75, 100})
_INTERNAL_STABLE_ID = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9._-]*|domain:[A-Za-z][A-Za-z0-9._-]*)$"
)
COUNTER_EVIDENCE_LEVEL_SCORES = {
    "none": 100,
    "minor": 75,
    "material": 50,
    "strong": 25,
    "coreContradiction": 0,
}


def _bounded_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer between 0 and 100")
    if not 0 <= value <= 100:
        raise ValueError(f"{label} must be between 0 and 100")
    return value


def confidence_score(dimensions: Mapping[str, int]) -> int:
    if type(dimensions) is not dict or set(dimensions) != set(WEIGHTS):
        raise ValueError(
            "confidence dimensions must contain exactly: "
            + ", ".join(WEIGHTS)
        )
    weighted = sum(
        Decimal(_bounded_integer(dimensions[key], key)) * Decimal(str(weight))
        for key, weight in WEIGHTS.items()
    )
    return int(weighted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def confidence_grade(score: int) -> str:
    score = _bounded_integer(score, "confidence score")
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def verify_claim_confidence(claim: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if type(claim) is not dict:
        return ["claim must be an object"]
    if not isinstance(claim.get("statement"), str) or not claim.get("statement", "").strip():
        errors.append("statement must be a non-empty string")
    if type(claim.get("confidence")) is not int:
        errors.append("confidence must be an integer between 0 and 100")
    if not isinstance(claim.get("grade"), str) or claim.get("grade") not in {"A", "B", "C", "D"}:
        errors.append("grade must be A, B, C, or D")
    dimensions = claim.get("confidenceDimensions", {})
    try:
        expected_score = confidence_score(dimensions)
    except (TypeError, ValueError) as exc:
        return [str(exc)]
    expected_grade = confidence_grade(expected_score)
    rationale = claim.get("confidenceRationale")
    if type(rationale) is not dict or set(rationale) != set(WEIGHTS):
        errors.append(
            "confidenceRationale must contain exactly: " + ", ".join(WEIGHTS)
        )
    else:
        for dimension in WEIGHTS:
            detail = rationale[dimension]
            if type(detail) is not dict:
                errors.append(f"confidenceRationale/{dimension} must be an object")
                continue
            expected_item_keys = {"score", "rationale", "evidenceRefs", "deductions"}
            if set(detail) != expected_item_keys:
                errors.append(
                    f"confidenceRationale/{dimension} must contain exactly: "
                    + ", ".join(sorted(expected_item_keys))
                )
            if (
                type(detail.get("rationale")) is not str
                or not detail.get("rationale", "").strip()
            ):
                errors.append(
                    f"confidenceRationale/{dimension}/rationale must be a non-empty string"
                )
            score = detail.get("score")
            if type(score) is not int or not 0 <= score <= 100:
                errors.append(
                    f"confidenceRationale/{dimension}/score must be an integer between 0 and 100"
                )
            if score != dimensions[dimension]:
                errors.append(
                    f"confidenceRationale/{dimension}/score must equal "
                    f"confidenceDimensions/{dimension} ({dimensions[dimension]})"
                )
            evidence_refs = detail.get("evidenceRefs")
            if type(evidence_refs) is not list or any(
                type(reference) is not str
                or not _INTERNAL_STABLE_ID.fullmatch(reference)
                for reference in evidence_refs
            ):
                errors.append(
                    f"confidenceRationale/{dimension}/evidenceRefs must be stable ID strings"
                )
            deductions = detail.get("deductions")
            if type(deductions) is not list or any(
                type(item) is not str or not item.strip() for item in deductions
            ):
                errors.append(
                    f"confidenceRationale/{dimension}/deductions must be an array of non-empty strings"
                )
            elif type(score) is int and score < 100 and not deductions:
                errors.append(
                    f"confidenceRationale/{dimension}/deductions must be non-empty "
                    "when score is below 100"
                )
    for field in ("evidenceRefs", "counterEvidenceRefs"):
        references = claim.get(field)
        if type(references) is not list or any(
            type(reference) is not str
            or not _INTERNAL_STABLE_ID.fullmatch(reference)
            for reference in references
        ):
            errors.append(f"{field} must be an array of internal stable IDs")
    counter_score = dimensions["counterEvidenceAssessment"]
    if counter_score not in COUNTER_EVIDENCE_SCORES:
        errors.append(
            "counterEvidenceAssessment must use one of 0, 25, 50, 75, 100"
        )
    level = claim.get("counterEvidenceLevel")
    expected_counter_score = COUNTER_EVIDENCE_LEVEL_SCORES.get(level)
    if expected_counter_score is None:
        errors.append(
            "counterEvidenceLevel must be none, minor, material, strong, or coreContradiction"
        )
    elif counter_score != expected_counter_score:
        errors.append(
            f"counterEvidenceLevel {level!r} requires counterEvidenceAssessment "
            f"score {expected_counter_score}, got {counter_score!r}"
        )
    if claim.get("confidence") != expected_score:
        errors.append(
            f"confidence mismatch: expected {expected_score}, got {claim.get('confidence')!r}"
        )
    if claim.get("grade") != expected_grade:
        errors.append(
            f"grade mismatch: expected {expected_grade!r}, got {claim.get('grade')!r}"
        )
    return errors
