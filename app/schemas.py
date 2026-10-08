"""StorySpark Request & Response Validation Schemas."""

import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


def get_age_tier_info(age: int) -> dict:
    """Returns pedagogical guidelines based on the child's age."""
    if 4 <= age <= 6:
        return {
            "tier": "Early Explorer",
            "band": "4-6 years",
            "style": "Playful metaphors, sensory descriptions, vibrant characters, and simple everyday scenarios without technical jargon.",
            "target_complexity": "Foundational / Intuitive",
            "vocabulary_guidance": "Use simple, relatable words, rhythm, sensory imagery, and everyday wonders. Avoid complex formulas and multi-syllable jargon.",
            "narrative_focus": "Curious animal or friendly child experiencing the concept through playful daily discovery.",
        }
    elif 7 <= age <= 9:
        return {
            "tier": "Curious Adventurer",
            "band": "7-9 years",
            "style": "Exciting quests, dialogue, relatable challenges, and tangible cause-and-effect science.",
            "target_complexity": "Intermediate / Exploratory",
            "vocabulary_guidance": "Introduce basic real scientific terms with vivid context. Keep sentences engaging and dynamic.",
            "narrative_focus": "An adventure or hands-on mystery where characters experiment, observe results, and overcome an obstacle using the concept.",
        }
    elif 10 <= age <= 12:
        return {
            "tier": "Bold Discoverer",
            "band": "10-12 years",
            "style": "Deeper scientific mechanisms, narrative stakes, mathematical reasoning, and problem-solving puzzles.",
            "target_complexity": "Advanced / Analytical",
            "vocabulary_guidance": "Incorporate accurate scientific/math terminology, logical connections, and quantitative relationships.",
            "narrative_focus": "A high-stakes challenge or scientific dilemma where understanding mechanisms and applying logic solves the problem.",
        }
    elif 13 <= age <= 14:
        return {
            "tier": "Young Innovator",
            "band": "13-14 years",
            "style": "Nuanced inquiry, systemic connections, real-world applications, and higher-order critical thinking.",
            "target_complexity": "Proficient / Systematic",
            "vocabulary_guidance": "Academically precise and mature prose, discussing systems, trade-offs, and multi-step scientific principles.",
            "narrative_focus": "A realistic scenario, technological innovation, or ecosystem challenge highlighting broader impacts and deeper inquiry.",
        }
    else:
        return {
            "tier": "General Learner",
            "band": f"{age} years",
            "style": "Age-adapted storytelling.",
            "target_complexity": "Standard",
            "vocabulary_guidance": "Age-appropriate language and clear concepts.",
            "narrative_focus": "Engaging educational story.",
        }


class StoryInputRequest(BaseModel):
    """Input payload for validating educational story parameters."""

    topic: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="The school science or math topic to teach.",
        examples=["Photosynthesis", "Adding Fractions", "Gravity and Planetary Orbits"],
    )
    age: int = Field(
        ...,
        ge=4,
        le=14,
        description="The child's age in years (between 4 and 14).",
        examples=[8],
    )

    @field_validator("topic")
    @classmethod
    def validate_topic_content(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Topic must contain at least 2 characters.")
        if len(trimmed) > 100:
            raise ValueError("Topic cannot exceed 100 characters.")
        # Ensure it contains at least one alphanumeric character
        if not re.search(r"[a-zA-Z0-9]", trimmed):
            raise ValueError("Topic must contain meaningful letters or numbers.")
        return trimmed

    @field_validator("age")
    @classmethod
    def validate_age_range(cls, v: int) -> int:
        if v < 4 or v > 14:
            raise ValueError("Child's age must be between 4 and 14 years.")
        return v


class AssessmentQuestion(BaseModel):
    """A validated, age-appropriate question generated with a story."""

    id: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(..., min_length=5, max_length=500)
    type: Literal["MCQ", "True/False", "Short Answer"]
    concept: str = Field(..., min_length=1, max_length=100)
    options: list[str] | None = Field(default=None, max_length=4)
    correct_answer: str = Field(..., min_length=1, max_length=200)
    explanation: str = Field(..., min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_question_shape(self):
        normalized_options = [option.strip().casefold() for option in self.options or []]
        if self.type == "MCQ":
            if not self.options or len(self.options) < 2 or len(set(normalized_options)) != len(self.options):
                raise ValueError("MCQ questions require 2 to 4 unique options.")
            if self.correct_answer.strip().casefold() not in normalized_options:
                raise ValueError("MCQ correct_answer must match an option.")
        elif self.type == "True/False":
            if set(normalized_options) != {"true", "false"} or len(normalized_options) != 2:
                raise ValueError("True/False questions require True and False options.")
            if self.correct_answer.strip().casefold() not in {"true", "false"}:
                raise ValueError("True/False correct_answer must be True or False.")
        elif self.options:
            raise ValueError("Short Answer questions must not include options.")
        return self


class StoryGenerationResponse(BaseModel):
    """Structured story, concepts, and a validated comprehension assessment."""

    story: str = Field(..., min_length=40)
    learning_objectives: list[str] = Field(..., min_length=1, max_length=3)
    key_concepts: list[str] = Field(..., min_length=1, max_length=4)
    questions: list[AssessmentQuestion] = Field(..., min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_assessment_alignment(self):
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("Question IDs must be unique.")
        concepts = {concept.strip().casefold() for concept in self.key_concepts}
        if any(question.concept.strip().casefold() not in concepts for question in self.questions):
            raise ValueError("Each question concept must appear in key_concepts.")
        return self


class AssessmentSubmissionRequest(BaseModel):
    """Complete learner responses for deterministic local scoring."""

    questions: list[AssessmentQuestion] = Field(..., min_length=1, max_length=5)
    answers: dict[str, str]

    @model_validator(mode="after")
    def validate_complete_answers(self):
        question_ids = {question.id for question in self.questions}
        if len(question_ids) != len(self.questions):
            raise ValueError("Question IDs must be unique.")
        if set(self.answers) != question_ids or any(not answer.strip() for answer in self.answers.values()):
            raise ValueError("An answer is required for every question.")
        return self


class ConceptResult(BaseModel):
    concept: str
    correct: int
    total: int
    status: Literal["mastered", "needs reinforcement"]


class AssessmentScoreResponse(BaseModel):
    correct: int
    total: int
    percentage: int
    concept_results: list[ConceptResult]


class LearningReportRequest(AssessmentSubmissionRequest):
    topic: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=4, le=14)
    learning_objectives: list[str] = Field(..., min_length=1, max_length=3)


class ReportConceptResult(ConceptResult):
    status: Literal["mastered", "developing", "needs reinforcement"]


class LearningReport(BaseModel):
    topic: str
    age: int
    correct: int
    total: int
    percentage: int
    objective_coverage: list[Literal["mastered", "developing", "needs reinforcement"]]
    concept_results: list[ReportConceptResult]
    summary: str
    parent_teacher_takeaway: str
    recommended_next_step: str


class ReinforcementRequest(LearningReportRequest):
    """Validated original assessment context used to target real knowledge gaps."""


class ReinforcementResponse(BaseModel):
    teaching_text: str = Field(..., min_length=40, max_length=2500)
    gap_concepts: list[str] = Field(..., min_length=1, max_length=4)
    questions: list[AssessmentQuestion] = Field(..., min_length=1, max_length=2)

    @model_validator(mode="after")
    def validate_gap_alignment(self):
        gaps = {concept.strip().casefold() for concept in self.gap_concepts}
        if any(question.concept.strip().casefold() not in gaps for question in self.questions):
            raise ValueError("Reinforcement questions must test a gap concept.")
        return self


class ValidationResponse(BaseModel):
    """Structured response for validated story input."""

    valid: bool
    topic: str
    age: int
    tier_info: dict
    message: str


class HealthResponse(BaseModel):
    """System health check and backend readiness status."""

    status: str
    app: str
    version: str
    gemini_configured: bool
    environment: str
