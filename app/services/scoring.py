"""Deterministic assessment scoring utilities."""

import re

from app.schemas import AssessmentQuestion, AssessmentScoreResponse, ConceptResult


def normalize_answer(value: str) -> str:
    """Normalize learner answers for deterministic comparison."""
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def is_correct_answer(question: AssessmentQuestion, answer: str) -> bool:
    """Evaluate one answer without using an AI model."""
    normalized_answer = normalize_answer(answer)
    normalized_correct = normalize_answer(question.correct_answer)
    if question.type in {"MCQ", "True/False"}:
        return normalized_answer == normalized_correct

    normalized_concept = normalize_answer(question.concept)
    return bool(
        normalized_answer
        and (
            normalized_correct in normalized_answer
            or normalized_concept in normalized_answer
        )
    )


def score_assessment(
    questions: list[AssessmentQuestion], answers: dict[str, str]
) -> AssessmentScoreResponse:
    """Calculate total and concept-level results from a complete submission."""
    concept_totals: dict[str, list[int]] = {}
    correct_count = 0

    for question in questions:
        is_correct = is_correct_answer(question, answers[question.id])
        correct_count += int(is_correct)
        result = concept_totals.setdefault(question.concept, [0, 0])
        result[0] += int(is_correct)
        result[1] += 1

    concept_results = [
        ConceptResult(
            concept=concept,
            correct=correct,
            total=total,
            status="mastered" if correct == total else "needs reinforcement",
        )
        for concept, (correct, total) in concept_totals.items()
    ]
    total = len(questions)
    return AssessmentScoreResponse(
        correct=correct_count,
        total=total,
        percentage=round(correct_count / total * 100),
        concept_results=concept_results,
    )
