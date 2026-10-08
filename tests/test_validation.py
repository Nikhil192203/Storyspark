"""Unit and API Integration Tests for StorySpark Input Validation, Security, and Gemini Integration."""

import json
from unittest.mock import patch, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai.errors import APIError, ClientError, ServerError

from app.main import app
from app.config import settings
from app.schemas import StoryGenerationResponse, get_age_tier_info
from app.services.gemini_service import build_story_prompt, gemini_service, is_transient_error

client = TestClient(app)


def test_health_check_endpoint():
    """Verify health check returns valid status and preserves backend security."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "StorySpark"
    assert isinstance(data["gemini_configured"], bool)
    # Ensure API key is NEVER exposed in the payload
    assert "api_key" not in data
    assert "GEMINI_API_KEY" not in data


@pytest.mark.parametrize(
    "topic,age,expected_tier",
    [
        ("Photosynthesis", 8, "Curious Adventurer"),
        ("Gravity & Orbits", 5, "Early Explorer"),
        ("Adding Fractions", 11, "Bold Discoverer"),
        ("DNA & Genetics", 14, "Young Innovator"),
        ("The Water Cycle", 4, "Early Explorer"),  # min boundary
        ("Thermodynamics", 14, "Young Innovator"),  # max boundary
    ],
)
def test_valid_story_input(topic, age, expected_tier):
    """Test valid topics and age inputs across all pedagogical bands."""
    response = client.post(
        "/api/validate-story-input",
        json={"topic": topic, "age": age},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["topic"] == topic
    assert data["age"] == age
    assert expected_tier in data["tier_info"]["tier"]
    assert "style" in data["tier_info"]
    assert "target_complexity" in data["tier_info"]


@pytest.mark.parametrize(
    "invalid_topic,age,reason",
    [
        ("", 8, "Empty topic"),
        ("   ", 8, "Whitespace only"),
        ("A", 8, "Too short (< 2 chars)"),
        ("x" * 101, 8, "Too long (> 100 chars)"),
        ("!@#$%^&*()", 8, "No alphanumeric content"),
    ],
)
def test_invalid_topic_validation(invalid_topic, age, reason):
    """Test validation catches improper or malformed school topics."""
    response = client.post(
        "/api/validate-story-input",
        json={"topic": invalid_topic, "age": age},
    )
    assert response.status_code == 422, f"Failed on reason: {reason}"


@pytest.mark.parametrize(
    "topic,invalid_age,reason",
    [
        ("Photosynthesis", 3, "Below min age (4)"),
        ("Photosynthesis", 15, "Above max age (14)"),
        ("Photosynthesis", -1, "Negative age"),
        ("Photosynthesis", 0, "Zero age"),
        ("Photosynthesis", "eight", "String age"),
    ],
)
def test_invalid_age_validation(topic, invalid_age, reason):
    """Test validation catches out-of-range or malformed age values."""
    response = client.post(
        "/api/validate-story-input",
        json={"topic": topic, "age": invalid_age},
    )
    assert response.status_code == 422, f"Failed on reason: {reason}"


def test_missing_payload_fields():
    """Test validation rejects requests missing required fields."""
    response = client.post("/api/validate-story-input", json={"topic": "Gravity"})
    assert response.status_code == 422

    response = client.post("/api/validate-story-input", json={"age": 8})
    assert response.status_code == 422

    response = client.post("/api/validate-story-input", json={})
    assert response.status_code == 422


def test_landing_page_serves_html():
    """Verify root endpoint serves the StorySpark HTML shell."""
    response = client.get("/")
    assert response.status_code == 200
    assert "StorySpark" in response.text
    assert "School Concept or Topic" in response.text
    assert "Create My Story" in response.text


# =========================================================================
# Gemini Integration Tests
# =========================================================================

def test_generate_story_rejects_invalid_inputs_before_ai():
    """Verify generation endpoint enforces input validation before calling Gemini."""
    response = client.post("/api/story/generate", json={"topic": "", "age": 8})
    assert response.status_code == 422

    response = client.post("/api/story/generate", json={"topic": "Fractions", "age": 16})
    assert response.status_code == 422


def test_generate_story_missing_api_key(monkeypatch):
    """Verify 503 response when GEMINI_API_KEY is not configured on server."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    response = client.post(
        "/api/story/generate",
        json={"topic": "Photosynthesis", "age": 8},
    )
    assert response.status_code == 503
    assert "Gemini API key is not configured" in response.json()["detail"]


def test_prompt_construction_differs_by_age():
    """Verify prompt adapts tone, vocabulary, and complexity across age tiers."""
    tier_young = get_age_tier_info(5)
    prompt_young = build_story_prompt("Photosynthesis", 5, tier_young)
    assert "Early Explorer" in prompt_young
    assert "Ages 4-6" in prompt_young
    assert "zero technical formulas" in prompt_young

    tier_older = get_age_tier_info(14)
    prompt_older = build_story_prompt("Photosynthesis", 14, tier_older)
    assert "Young Innovator" in prompt_older
    assert "Ages 13-14" in prompt_older
    assert "Academically precise" in prompt_older


def test_generate_story_successful_structure_mock(monkeypatch):
    """Verify endpoint returns a validated story and comprehension assessment."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")

    mock_payload = {
        "story": (
            "Once upon a time in a sunny backyard, Pip the squirrel noticed that the great oak tree "
            "never had to eat acorns. 'How do you grow so tall without breakfast?' Pip asked. "
            "The old oak rustled its leaves in the warm morning breeze. 'I have millions of tiny green "
            "kitchens inside my leaves, little Pip! When the sun shines, I catch the golden light, drink "
            "water from deep underground, and breathe in the air. That is how I make sweet sugar to grow!' "
            "Pip danced on the branches, marveling at the miracle of photosynthesis."
        ),
        "learning_objectives": [
            "Understand that plants create their own food using sunlight",
            "Identify water, sunlight, and air as essential inputs for photosynthesis",
        ],
        "key_concepts": [
            "Photosynthesis",
            "Chloroplasts",
            "Sunlight Energy",
        ],
        "questions": [
            {"id": "q1", "question": "What helps plants make food?", "type": "MCQ", "concept": "Photosynthesis", "options": ["Sunlight", "Moonlight"], "correct_answer": "Sunlight", "explanation": "Plants use sunlight to make food."},
            {"id": "q2", "question": "Chloroplasts are in plant leaves.", "type": "True/False", "concept": "Chloroplasts", "options": ["True", "False"], "correct_answer": "True", "explanation": "Chloroplasts help leaves capture light."},
            {"id": "q3", "question": "What kind of energy does sunlight provide?", "type": "MCQ", "concept": "Sunlight Energy", "options": ["Light energy", "Sound energy"], "correct_answer": "Light energy", "explanation": "Sunlight provides light energy."},
        ],
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_payload)

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        response = client.post(
            "/api/story/generate",
            json={"topic": "Photosynthesis", "age": 6},
        )

        assert response.status_code == 200
        data = response.json()

        # Strict check: response must contain ONLY these 3 keys
        assert set(data.keys()) == {"story", "learning_objectives", "key_concepts", "questions"}
        assert len(data["story"]) >= 50
        assert len(data["learning_objectives"]) == 2
        assert len(data["key_concepts"]) == 3
        assert "Photosynthesis" in data["key_concepts"]


def test_generate_story_malformed_response(monkeypatch):
    """Verify 502 error when Gemini returns malformed or incomplete JSON."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")

    mock_response = MagicMock()
    mock_response.text = '{"story": "Short story", "missing_other_keys": true}'

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        response = client.post(
            "/api/story/generate",
            json={"topic": "Gravity", "age": 9},
        )

        assert response.status_code == 502
        assert "malformed story format" in response.json()["detail"]


def test_generate_story_api_error_handling(monkeypatch):
    """Verify 502 error when google-genai raises a non-transient APIError."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")

    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = APIError(
            403,
            {"error": {"message": "The caller does not have permission"}},
        )
        mock_client_cls.return_value = mock_instance

        response = client.post(
            "/api/story/generate",
            json={"topic": "Electric Circuits", "age": 10},
        )

        assert response.status_code == 502
        assert response.json()["detail"] == "Gemini could not generate a story. Please try again."


def test_current_sdk_and_transport_errors_are_classified_correctly():
    request = httpx.Request("POST", "https://example.invalid")
    assert is_transient_error(ServerError(503, {"error": {"message": "Unavailable"}}))
    assert is_transient_error(ClientError(429, {"error": {"message": "Quota"}}))
    assert is_transient_error(httpx.ReadTimeout("Timed out", request=request))
    assert is_transient_error(httpx.ConnectError("Disconnected", request=request))
    assert not is_transient_error(ClientError(404, {"error": {"message": "Not found"}}))


def test_retry_transient_503_and_succeed(monkeypatch):
    """Verify that transient 503 on 3.8 Flash retries with backoff and succeeds."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")

    mock_payload = {
        "story": "A wonderful story about gravity and planets orbiting the glowing sun.",
        "learning_objectives": ["Understand gravity keeps planets in orbit"],
        "key_concepts": ["Gravity", "Orbit"],
        "questions": [
            {"id": "q1", "question": "What pulls objects down?", "type": "MCQ", "concept": "Gravity", "options": ["Gravity", "Wind"], "correct_answer": "Gravity", "explanation": "Gravity pulls objects together."},
            {"id": "q2", "question": "An orbit is a path around an object.", "type": "True/False", "concept": "Orbit", "options": ["True", "False"], "correct_answer": "True", "explanation": "Planets travel in orbits."},
            {"id": "q3", "question": "Gravity can keep a planet in orbit.", "type": "True/False", "concept": "Gravity", "options": ["True", "False"], "correct_answer": "True", "explanation": "Gravity keeps planets near the sun."},
        ],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_payload)

    transient_503 = APIError(503, {"error": {"message": "Model high demand"}})

    with patch.object(gemini_service, "initial_backoff", 0.001), \
         patch("google.genai.Client") as mock_client_cls:

        mock_instance = MagicMock()
        # 1st call fails with 503, 2nd call succeeds
        mock_instance.models.generate_content.side_effect = [transient_503, mock_response]
        mock_client_cls.return_value = mock_instance

        response = client.post(
            "/api/story/generate",
            json={"topic": "Gravity", "age": 8},
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"story", "learning_objectives", "key_concepts", "questions"}
        assert mock_instance.models.generate_content.call_count == 2
        # First attempt called gemini-3.8-flash
        first_call = mock_instance.models.generate_content.call_args_list[0]
        assert first_call.kwargs["model"] == "gemini-3.8-flash"


def test_fallback_to_gemini_3_7_flash(monkeypatch):
    """Verify that when 3.8 Flash exhausts retries with 503, it falls back to gemini-3.5-flash."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")

    mock_payload = {
        "story": "A fallback story synthesized reliably by Gemini 3.7 Flash.",
        "learning_objectives": ["Understand cellular respiration"],
        "key_concepts": ["Respiration", "Energy"],
        "questions": [
            {"id": "q1", "question": "What process releases energy from food?", "type": "MCQ", "concept": "Respiration", "options": ["Respiration", "Evaporation"], "correct_answer": "Respiration", "explanation": "Respiration releases energy from food."},
            {"id": "q2", "question": "Cells need energy to work.", "type": "True/False", "concept": "Energy", "options": ["True", "False"], "correct_answer": "True", "explanation": "Cells use energy for their jobs."},
            {"id": "q3", "question": "Respiration happens in cells.", "type": "True/False", "concept": "Respiration", "options": ["True", "False"], "correct_answer": "True", "explanation": "Cells perform respiration."},
        ],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_payload)

    transient_503 = APIError(503, {"error": {"message": "503 UNAVAILABLE: High demand"}})

    with patch.object(gemini_service, "initial_backoff", 0.001), \
         patch("google.genai.Client") as mock_client_cls:

        mock_instance = MagicMock()
        # 3 calls on 3.8-flash fail with 503, then 1st call on 3.7-flash succeeds
        mock_instance.models.generate_content.side_effect = [
            transient_503,
            transient_503,
            transient_503,
            mock_response,
        ]
        mock_client_cls.return_value = mock_instance

        response = client.post(
            "/api/story/generate",
            json={"topic": "Cellular Respiration", "age": 12},
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"story", "learning_objectives", "key_concepts", "questions"}
        
        # Verify call to fallback model
        calls = mock_instance.models.generate_content.call_args_list
        assert len(calls) == 4
        assert calls[0].kwargs["model"] == "gemini-3.8-flash"
        assert calls[1].kwargs["model"] == "gemini-3.8-flash"
        assert calls[2].kwargs["model"] == "gemini-3.8-flash"
        assert calls[3].kwargs["model"] == "gemini-3.5-flash"


def test_transport_failure_reaches_fallback_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")
    mock_payload = {
        "story": "A reliable fallback story about gravity guiding a small moon safely around its planet.",
        "learning_objectives": ["Understand gravity and orbital motion"],
        "key_concepts": ["Gravity", "Orbit"],
        "questions": [
            {"id": "q1", "question": "What pulls the moon toward the planet?", "type": "MCQ", "concept": "Gravity", "options": ["Gravity", "Wind"], "correct_answer": "Gravity", "explanation": "Gravity pulls objects together."},
            {"id": "q2", "question": "An orbit is a path around another object.", "type": "True/False", "concept": "Orbit", "options": ["True", "False"], "correct_answer": "True", "explanation": "A moon follows an orbit."},
            {"id": "q3", "question": "Gravity helps keep a moon in orbit.", "type": "True/False", "concept": "Gravity", "options": ["True", "False"], "correct_answer": "True", "explanation": "Gravity bends the moon's path."},
        ],
    }
    mock_response = MagicMock(text=json.dumps(mock_payload))
    request = httpx.Request("POST", "https://example.invalid")
    failures = [httpx.ConnectError("Disconnected", request=request) for _ in range(3)]

    with patch.object(gemini_service, "initial_backoff", 0.001), patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = [*failures, mock_response]
        mock_client_cls.return_value = mock_instance

        response = client.post("/api/story/generate", json={"topic": "Gravity", "age": 8})

    assert response.status_code == 200
    calls = mock_instance.models.generate_content.call_args_list
    assert len(calls) == 4
    assert calls[3].kwargs["model"] == "gemini-3.5-flash"


def test_quota_exhaustion_is_not_reported_as_model_overload(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-valid-api-key")
    quota_error = ClientError(429, {"error": {"message": "Resource exhausted"}})

    with patch.object(gemini_service, "initial_backoff", 0.001), patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = [quota_error] * 6
        mock_client_cls.return_value = mock_instance

        response = client.post("/api/story/generate", json={"topic": "Gravity", "age": 8})

    assert response.status_code == 429
    assert response.json()["detail"] == "Gemini request quota is temporarily exhausted. Please try again later."
