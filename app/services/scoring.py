"""Deterministic assessment scoring and report utilities."""

import re

from app.schemas import (
    AssessmentQuestion,
    AssessmentScoreResponse,
    ConceptResult,
    LearningReport,
    ReportConceptResult,
)


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
    return bool(normalized_answer and (normalized_correct in normalized_answer or normalized_concept in normalized_answer))


def score_assessment(questions: list[AssessmentQuestion], answers: dict[str, str]) -> AssessmentScoreResponse:
    """Calculate total and concept-level results from a complete submission."""
    concept_totals: dict[str, list[int]] = {}
    correct_count = 0
    for question in questions:
        correct = is_correct_answer(question, answers[question.id])
        correct_count += int(correct)
        result = concept_totals.setdefault(question.concept, [0, 0])
        result[0] += int(correct)
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


def report_status(correct: int, total: int) -> str:
    if correct == total:
        return "mastered"
    if correct / total >= 0.5:
        return "developing"
    return "needs reinforcement"


def build_learning_report(
    topic: str,
    age: int,
    learning_objectives: list[str],
    questions: list[AssessmentQuestion],
    answers: dict[str, str],
) -> LearningReport:
    """Build learner and parent-facing conclusions entirely from scored answers."""
    score = score_assessment(questions, answers)
    report_concepts = [
        ReportConceptResult(
            concept=item.concept,
            correct=item.correct,
            total=item.total,
            status=report_status(item.correct, item.total),
        )
        for item in score.concept_results
    ]
    objective_coverage = [
        report_status(
            sum(
                int(is_correct_answer(question, answers[question.id]))
                for question in questions
                if question.concept.casefold() in objective.casefold()
            ),
            max(1, sum(1 for question in questions if question.concept.casefold() in objective.casefold())),
        )
        for objective in learning_objectives
    ]
    mastered = [item.concept for item in report_concepts if item.status == "mastered"]
    gaps = [item.concept for item in report_concepts if item.status != "mastered"]
    if not gaps:
        summary = "Great work! You demonstrated strong understanding of the key concepts."
        takeaway = "The learner answered every assessed concept correctly and is ready to apply the idea in a new context."
        next_step = "Try a related topic or explain the concept to someone else."
    elif mastered:
        summary = f"You showed strong understanding of {', '.join(mastered)} and are still building {', '.join(gaps)}."
        takeaway = f"Strengths are clear in {', '.join(mastered)}. A short revisit of {', '.join(gaps)} will strengthen confidence."
        next_step = f"Reinforce {', '.join(gaps)} with the targeted mini-lesson."
    else:
        summary = f"You are building understanding of {', '.join(gaps)}."
        takeaway = "The learner benefits from a focused explanation before trying the concept again."
        next_step = f"Use the targeted mini-lesson for {', '.join(gaps)} and answer the follow-up questions."

    return LearningReport(
        topic=topic,
        age=age,
        correct=score.correct,
        total=score.total,
        percentage=score.percentage,
        objective_coverage=objective_coverage,
        concept_results=report_concepts,
        summary=summary,
        parent_teacher_takeaway=takeaway,
        recommended_next_step=next_step,
    )


def gap_concepts(questions: list[AssessmentQuestion], answers: dict[str, str]) -> list[str]:
    """Return only concepts with an incorrect answer from deterministic scoring."""
    score = score_assessment(questions, answers)
    return [item.concept for item in score.concept_results if item.status == "needs reinforcement"]
