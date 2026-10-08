"""Gemini Backend Service.

Connects to Google Gemini using the official google-genai SDK.
Handles age-calibrated prompt engineering, structured JSON generation,
response validation, transient error retries (503/429), and fallback to gemini-3.7-flash.
"""

import asyncio
import json
import logging

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.schemas import StoryGenerationResponse, get_age_tier_info

logger = logging.getLogger(__name__)


def is_transient_error(exc: Exception) -> bool:
    """Check whether a Gemini or transport failure is safe to retry."""
    if isinstance(exc, (TimeoutError, httpx.TransportError)):
        return True
    if isinstance(exc, APIError):
        return getattr(exc, "code", None) in (408, 429, 500, 502, 503, 504)
    return False


def build_story_prompt(topic: str, age: int, tier_info: dict) -> str:
    """Constructs a pedagogically tuned prompt tailored to child's age."""
    return f"""You are StorySpark, an expert educational storyteller and curriculum specialist.
Your mission is to teach the school STEM concept "{topic}" to a {age}-year-old child through an engaging, memorable story.

Pedagogical Calibration for Age {age} ({tier_info['tier']}):
- Target Complexity: {tier_info['target_complexity']}
- Core Style: {tier_info['style']}
- Vocabulary Guidance: {tier_info['vocabulary_guidance']}
- Narrative Focus: {tier_info['narrative_focus']}

CRITICAL INSTRUCTIONS:
1. AGE-APPROPRIATE VOICE:
   - For Ages 4-6: Short sentences, rhythmic and sensory words, relatable characters (animals/everyday objects), zero technical formulas.
   - For Ages 7-9: Energetic quests, dialogue, hands-on experimentation, intuitive cause-and-effect science.
   - For Ages 10-12: Accurate STEM terminology introduced in context, narrative problem-solving, structural mechanisms.
   - For Ages 13-14: Academically precise language, systemic connections, deeper logic, and real-world implications.

2. CONCEPT INTEGRATION:
   - The concept "{topic}" must be the central puzzle or breakthrough in the narrative.
   - The protagonist discovers, applies, or observes how the concept works to overcome an obstacle.

3. STRUCTURED OUTPUT:
   Return valid JSON with exactly these four keys:
   - "story": The full story text, organized with clear paragraph breaks.
   - "learning_objectives": Array of 2 to 3 concise curriculum outcomes the story conveys.
   - "key_concepts": Array of 2 to 4 core STEM terms or conceptual ideas taught.
   - "questions": Array of 3 to 5 comprehension questions that directly test the listed key_concepts.

4. QUESTION REQUIREMENTS:
   - Every question has a unique machine-readable "id", "question", "type", "concept", "options" when applicable, "correct_answer", and a short "explanation".
   - "concept" must exactly match one item in "key_concepts".
   - Use mostly "MCQ" and "True/False" types; include at most one "Short Answer" type.
   - MCQ questions must have 2 to 4 unique options and correct_answer must be one option.
   - True/False questions must use exactly ["True", "False"] options and a matching correct_answer.
   - Short Answer questions have no options. Set correct_answer to a concise essential term or phrase from the concept.
   - Questions must use the vocabulary, complexity, and reasoning appropriate for the requested age.
"""


class GeminiService:
    """Service boundary for Google Gemini API integration with resilience and fallbacks."""

    def __init__(self):
        self.model_name = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self.max_retries_per_model = 2
        self.initial_backoff = 1.0
        self.backoff_multiplier = 2.0
        self.max_backoff = 4.0

    @property
    def api_key(self) -> str:
        """Fetch API key dynamically from settings."""
        return settings.gemini_api_key

    @property
    def is_configured(self) -> bool:
        """Check if backend has a valid Gemini API key configured."""
        return settings.is_gemini_configured

    def get_status(self) -> dict:
        """Returns readiness status of the Gemini backend integration."""
        return {
            "configured": self.is_configured,
            "target_model": self.model_name,
            "fallback_model": self.fallback_model,
            "backend_secured": True,
        }

    async def generate_educational_story(self, topic: str, age: int) -> StoryGenerationResponse:
        """Generates an age-calibrated educational story using Google Gemini.
        
        Features:
        - Bounded exponential backoff on transient 503/429 failures.
        - Graceful fallback from gemini-3.8-flash to gemini-3.7-flash.
        - Strict Pydantic response validation.
        """
        if not self.is_configured:
            logger.warning("Attempted story generation without configured GEMINI_API_KEY.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Gemini API key is not configured on the server. "
                    "Please set the GEMINI_API_KEY environment variable on the server."
                ),
            )

        tier_info = get_age_tier_info(age)
        prompt = build_story_prompt(topic, age, tier_info)

        # Initialize client with server-side API key (never exposed)
        client = genai.Client(api_key=self.api_key)

        models_to_try = [self.model_name]
        if self.fallback_model and self.fallback_model != self.model_name:
            models_to_try.append(self.fallback_model)

        last_transient_error = None

        for model_idx, model in enumerate(models_to_try):
            is_fallback = model_idx > 0
            if is_fallback:
                logger.info("Switching to fallback model: %s", model)

            for attempt in range(self.max_retries_per_model + 1):
                try:
                    logger.debug("Calling Gemini model %s (attempt %d)", model, attempt + 1)
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=StoryGenerationResponse,
                            temperature=0.7,
                        ),
                    )

                    raw_text = response.text
                    if not raw_text or not raw_text.strip():
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Gemini returned an empty response. Please try again.",
                        )

                    # Strictly validate the AI output against the Pydantic schema
                    try:
                        validated_story = StoryGenerationResponse.model_validate_json(raw_text)
                        return validated_story
                    except (ValidationError, json.JSONDecodeError) as val_err:
                        logger.error("Gemini response failed schema validation: %s", str(val_err))
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Received malformed story format from Gemini API.",
                        )

                except (APIError, httpx.TransportError, TimeoutError) as request_error:
                    if is_transient_error(request_error):
                        last_transient_error = request_error
                        if attempt < self.max_retries_per_model:
                            backoff = min(
                                self.initial_backoff * (self.backoff_multiplier ** attempt),
                                self.max_backoff,
                            )
                            logger.warning(
                                "Transient Gemini request failure on %s (attempt %d). Retrying in %.2fs.",
                                model,
                                attempt + 1,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        logger.warning("Model %s exhausted retries.", model)
                        break

                    logger.error("Non-transient Gemini API error on %s", model)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Gemini could not generate a story. Please try again.",
                    )
                except HTTPException:
                    raise
                except Exception:
                    logger.error("Unexpected error in Gemini story generation on %s", model)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Story generation is temporarily unavailable. Please try again.",
                    )

        # If all models exhausted transient errors
        if last_transient_error:
            if getattr(last_transient_error, "code", None) == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Gemini request quota is temporarily exhausted. Please try again later.",
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini is temporarily unavailable. Please try again shortly.",
            )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate story after trying available models.",
        )


# Singleton instance
gemini_service = GeminiService()
