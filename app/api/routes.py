"""StorySpark API Routes."""

from fastapi import APIRouter
from app.config import settings
from app.schemas import (
    StoryInputRequest,
    ValidationResponse,
    HealthResponse,
    StoryGenerationResponse,
    AssessmentSubmissionRequest,
    AssessmentScoreResponse,
    get_age_tier_info,
)
from app.services.gemini_service import gemini_service
from app.services.scoring import score_assessment

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def get_health():
    """Health check endpoint providing backend readiness and safe Gemini status."""
    return HealthResponse(
        status="healthy",
        app=settings.PROJECT_NAME,
        version=settings.VERSION,
        gemini_configured=gemini_service.is_configured,
        environment=settings.ENVIRONMENT,
    )


@router.post("/validate-story-input", response_model=ValidationResponse, tags=["Validation"])
async def validate_story_input(payload: StoryInputRequest):
    """Validate story topic and age parameters before generation.
    
    Provides feedback on age appropriateness and pedagogy tiers.
    """
    tier_info = get_age_tier_info(payload.age)
    return ValidationResponse(
        valid=True,
        topic=payload.topic,
        age=payload.age,
        tier_info=tier_info,
        message=f"Topic '{payload.topic}' is valid for a {payload.age}-year-old learner ({tier_info['tier']}).",
    )


@router.post(
    "/story/generate",
    response_model=StoryGenerationResponse,
    response_model_exclude_unset=True,
    tags=["Story Generation"],
)
async def generate_story(payload: StoryInputRequest):
    """Generate an age-appropriate educational story and its assessment in one Gemini call."""
    return await gemini_service.generate_educational_story(payload.topic, payload.age)


@router.post("/assessment/score", response_model=AssessmentScoreResponse, tags=["Assessment"])
async def score_assessment_submission(payload: AssessmentSubmissionRequest):
    """Score a complete assessment deterministically without calling Gemini."""
    return score_assessment(payload.questions, payload.answers)
