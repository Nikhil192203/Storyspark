"""Learning report and reinforcement API tests."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def questions():
    return [
        {"id": "sun", "question": "What gives plants energy?", "type": "MCQ", "concept": "Sunlight", "options": ["Sunlight", "Sand"], "correct_answer": "Sunlight", "explanation": "Plants capture light."},
        {"id": "water", "question": "Plants use water.", "type": "True/False", "concept": "Water", "options": ["True", "False"], "correct_answer": "True", "explanation": "Water is an input."},
        {"id": "food", "question": "What process makes plant food?", "type": "MCQ", "concept": "Photosynthesis", "options": ["Photosynthesis", "Evaporation"], "correct_answer": "Photosynthesis", "explanation": "Photosynthesis makes food."},
    ]


def report_payload(answers):
    return {
        "topic": "Photosynthesis",
        "age": 10,
        "learning_objectives": ["Identify plant inputs", "Explain photosynthesis"],
        "questions": questions(),
        "answers": answers,
    }


def test_learning_report_generates_deterministic_data():
    response = client.post("/api/assessment/report", json=report_payload({"sun": "Sunlight", "water": "False", "food": "Photosynthesis"}))
    assert response.status_code == 200
    data = response.json()
    assert data["percentage"] == 67
    assert data["topic"] == "Photosynthesis"
    results = {item["concept"]: item["status"] for item in data["concept_results"]}
    assert results == {"Sunlight": "mastered", "Water": "needs reinforcement", "Photosynthesis": "mastered"}
    assert "Water" in data["summary"]


def test_learning_report_no_gap_case():
    response = client.post("/api/assessment/report", json=report_payload({"sun": "Sunlight", "water": "True", "food": "Photosynthesis"}))
    assert response.status_code == 200
    assert "Great work!" in response.json()["summary"]
    assert all(item["status"] == "mastered" for item in response.json()["concept_results"])


def test_reinforcement_rejects_no_gap_case():
    response = client.post("/api/reinforcement/generate", json=report_payload({"sun": "Sunlight", "water": "True", "food": "Photosynthesis"}))
    assert response.status_code == 400


def test_reinforcement_generates_valid_targeted_questions(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")
    generated = {
        "teaching_text": "Mira watched a tiny raindrop travel into a leaf, where water helped the leaf make food.",
        "gap_concepts": ["Water"],
        "questions": [{"id": "water-followup", "question": "Plants need water to make food.", "type": "True/False", "concept": "Water", "options": ["True", "False"], "correct_answer": "True", "explanation": "Water helps plants make food."}],
    }
    with patch("google.genai.Client") as client_cls:
        instance = MagicMock()
        instance.models.generate_content.return_value = MagicMock(text=json.dumps(generated))
        client_cls.return_value = instance
        response = client.post("/api/reinforcement/generate", json=report_payload({"sun": "Sunlight", "water": "False", "food": "Photosynthesis"}))

    assert response.status_code == 200
    assert response.json()["gap_concepts"] == ["Water"]
    assert response.json()["questions"][0]["concept"] == "Water"


def test_follow_up_questions_keep_deterministic_scoring():
    follow_up = [{"id": "water-followup", "question": "Plants need water to make food.", "type": "True/False", "concept": "Water", "options": ["True", "False"], "correct_answer": "True", "explanation": "Water helps plants make food."}]
    response = client.post("/api/assessment/score", json={"questions": follow_up, "answers": {"water-followup": "True"}})
    assert response.status_code == 200
    assert response.json()["percentage"] == 100
