"""Focused validation and deterministic scoring tests for assessments."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import StoryGenerationResponse
from app.services.gemini_service import build_story_prompt
from app.schemas import get_age_tier_info


client = TestClient(app)


def questions():
    return [
        {
            "id": "plant-food",
            "question": "What do plants use to make food?",
            "type": "MCQ",
            "concept": "Photosynthesis",
            "options": ["Sunlight", "Sand", "Rocks"],
            "correct_answer": "Sunlight",
            "explanation": "Plants use sunlight during photosynthesis.",
        },
        {
            "id": "leaf-part",
            "question": "Chloroplasts help leaves capture light.",
            "type": "True/False",
            "concept": "Chloroplasts",
            "options": ["True", "False"],
            "correct_answer": "True",
            "explanation": "Chloroplasts capture light energy.",
        },
        {
            "id": "plant-process",
            "question": "Name the process plants use to make food.",
            "type": "Short Answer",
            "concept": "Photosynthesis",
            "correct_answer": "photosynthesis",
            "explanation": "Photosynthesis is how plants make food.",
        },
    ]


def test_valid_question_structure():
    response = StoryGenerationResponse.model_validate(
        {
            "story": "A long enough story about a leaf learning how sunlight helps it make food every bright day.",
            "learning_objectives": ["Explain how plants make food"],
            "key_concepts": ["Photosynthesis", "Chloroplasts"],
            "questions": questions(),
        }
    )
    assert len(response.questions) == 3


def test_malformed_question_response_rejected():
    bad_questions = questions()
    bad_questions[0]["correct_answer"] = "Rain"
    with pytest.raises(ValidationError):
        StoryGenerationResponse.model_validate(
            {
                "story": "A long enough story about a leaf learning how sunlight helps it make food every bright day.",
                "learning_objectives": ["Explain how plants make food"],
                "key_concepts": ["Photosynthesis", "Chloroplasts"],
                "questions": bad_questions,
            }
        )


def test_all_answers_correct():
    response = client.post(
        "/api/assessment/score",
        json={
            "questions": questions(),
            "answers": {"plant-food": " sunlight ", "leaf-part": "TRUE", "plant-process": "Photosynthesis happens in leaves"},
        },
    )
    assert response.status_code == 200
    assert response.json()["correct"] == 3
    assert response.json()["percentage"] == 100


def test_all_answers_wrong():
    response = client.post(
        "/api/assessment/score",
        json={
            "questions": questions(),
            "answers": {"plant-food": "Rocks", "leaf-part": "False", "plant-process": "weather"},
        },
    )
    assert response.status_code == 200
    assert response.json()["correct"] == 0
    assert response.json()["percentage"] == 0


def test_incomplete_submission_rejected():
    response = client.post(
        "/api/assessment/score",
        json={"questions": questions(), "answers": {"plant-food": "Sunlight"}},
    )
    assert response.status_code == 422


def test_concept_level_scoring():
    response = client.post(
        "/api/assessment/score",
        json={
            "questions": questions(),
            "answers": {"plant-food": "Sunlight", "leaf-part": "False", "plant-process": "photosynthesis"},
        },
    )
    assert response.status_code == 200
    results = {item["concept"]: item for item in response.json()["concept_results"]}
    assert results["Photosynthesis"] == {"concept": "Photosynthesis", "correct": 2, "total": 2, "status": "mastered"}
    assert results["Chloroplasts"]["status"] == "needs reinforcement"


def test_assessment_prompt_is_age_specific():
    young_prompt = build_story_prompt("Photosynthesis", 5, get_age_tier_info(5))
    older_prompt = build_story_prompt("Photosynthesis", 14, get_age_tier_info(14))
    assert "QUESTION REQUIREMENTS" in young_prompt
    assert "zero technical formulas" in young_prompt
    assert "Academically precise" in older_prompt
