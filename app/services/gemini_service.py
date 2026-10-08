"""Gemini generation with validated outputs, retries, and fallback models."""

import asyncio
import json
import logging
from typing import TypeVar

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.schemas import ReinforcementResponse, StoryGenerationResponse, get_age_tier_info

logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def is_transient_error(exc: Exception) -> bool:
    """Check whether a Gemini or transport failure is safe to retry."""
    if isinstance(exc, (TimeoutError, httpx.TransportError)):
        return True
    return isinstance(exc, APIError) and getattr(exc, "code", None) in (408, 429, 500, 502, 503, 504)


def build_story_prompt(topic: str, age: int, tier_info: dict) -> str:
    """Construct a pedagogically tuned story prompt."""
    return f'''You are StorySpark, an expert educational storyteller and curriculum specialist.
Teach the school STEM concept "{topic}" to a {age}-year-old child through an engaging story.

Pedagogical Calibration for Age {age} ({tier_info['tier']}):
- Target Complexity: {tier_info['target_complexity']}
- Core Style: {tier_info['style']}
- Vocabulary Guidance: {tier_info['vocabulary_guidance']}
- Narrative Focus: {tier_info['narrative_focus']}

AGE-APPROPRIATE VOICE:
- Ages 4-6: short, sensory sentences; zero technical formulas.
- Ages 7-9: energetic quests, dialogue, and cause-and-effect science.
- Ages 10-12: accurate STEM terms and problem-solving.
- Ages 13-14: precise language, systems, logic, and real-world implications.

Return JSON with exactly: story, learning_objectives, key_concepts, questions.
- story: full story with paragraph breaks.
- learning_objectives: 2 to 3 concise outcomes.
- key_concepts: 2 to 4 core ideas.
- questions: 3 to 5 questions directly testing the key_concepts.
QUESTION REQUIREMENTS:
Every question needs id, question, type, concept, options when applicable, correct_answer, and explanation.
concept must exactly match key_concepts. Use mostly MCQ and True/False, at most one Short Answer.
MCQ: 2 to 4 unique options and correct_answer is an option. True/False: exactly ["True", "False"].
Short Answer: no options and a concise essential-term correct_answer. Questions must match the requested age.'''


def build_reinforcement_prompt(
    topic: str, age: int, learning_objectives: list[str], gaps: list[str]
) -> str:
    """Construct a narrow, age-calibrated prompt for proven knowledge gaps."""
    tier_info = get_age_tier_info(age)
    return f'''You are StorySpark, an expert educational storyteller.
Create a short targeted teaching explanation for a {age}-year-old learner about the missed concepts from "{topic}".

Age guidance: {tier_info['style']}
Vocabulary: {tier_info['vocabulary_guidance']}
Relevant learning objectives: {learning_objectives}
Only reinforce these missed concepts: {gaps}

Return JSON with exactly: teaching_text, gap_concepts, questions.
- teaching_text: a short, engaging explanation or mini-story focused only on gap_concepts.
- gap_concepts: exactly the supplied missed concepts.
- questions: 1 to 2 age-appropriate questions that only test gap_concepts.
Every question needs id, question, type, concept, options when applicable, correct_answer, and explanation.
Use MCQ or True/False. MCQ has 2 to 4 unique options and correct_answer is an option. True/False uses exactly ["True", "False"].'''


class GeminiService:
    """Server-side Gemini service with bounded retries and model fallback."""

    def __init__(self):
        self.model_name = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self.max_retries_per_model = 2
        self.initial_backoff = 1.0
        self.backoff_multiplier = 2.0
        self.max_backoff = 4.0

    @property
    def api_key(self) -> str:
        return settings.gemini_api_key

    @property
    def is_configured(self) -> bool:
        return settings.is_gemini_configured

    async def _generate_structured(self, prompt: str, response_schema: type[ResponseModel]) -> ResponseModel:
        if not self.is_configured:
            logger.warning("Attempted Gemini generation without a configured API key.")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini API key is not configured on the server.")

        client = genai.Client(api_key=self.api_key)
        models = [self.model_name]
        if self.fallback_model and self.fallback_model != self.model_name:
            models.append(self.fallback_model)
        last_transient_error: Exception | None = None

        for index, model in enumerate(models):
            if index:
                logger.info("Switching to fallback model: %s", model)
            for attempt in range(self.max_retries_per_model + 1):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema,
                            temperature=0.7,
                        ),
                    )
                    raw_text = response.text
                    if not raw_text or not raw_text.strip():
                        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini returned an empty response. Please try again.")
                    return response_schema.model_validate_json(raw_text)
                except (ValidationError, json.JSONDecodeError):
                    logger.error("Gemini response failed schema validation.")
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Received malformed story format from Gemini API.")
                except (APIError, httpx.TransportError, TimeoutError) as request_error:
                    if not is_transient_error(request_error):
                        logger.error("Non-transient Gemini API error on %s", model)
                        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini could not generate a story. Please try again.")
                    last_transient_error = request_error
                    if attempt < self.max_retries_per_model:
                        backoff = min(self.initial_backoff * self.backoff_multiplier**attempt, self.max_backoff)
                        logger.warning("Transient Gemini request failure on %s (attempt %d). Retrying in %.2fs.", model, attempt + 1, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    logger.warning("Model %s exhausted retries.", model)
                    break

        if getattr(last_transient_error, "code", None) == 429:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Gemini request quota is temporarily exhausted. Please try again later.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini is temporarily unavailable. Please try again shortly.")

    async def generate_educational_story(self, topic: str, age: int) -> StoryGenerationResponse:
        return await self._generate_structured(build_story_prompt(topic, age, get_age_tier_info(age)), StoryGenerationResponse)

    async def generate_reinforcement(
        self, topic: str, age: int, learning_objectives: list[str], gaps: list[str]
    ) -> ReinforcementResponse:
        reinforcement = await self._generate_structured(
            build_reinforcement_prompt(topic, age, learning_objectives, gaps),
            ReinforcementResponse,
        )
        if {concept.casefold() for concept in reinforcement.gap_concepts} != {concept.casefold() for concept in gaps}:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Received malformed response from Gemini API.")
        return reinforcement


gemini_service = GeminiService()
