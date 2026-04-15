"""Resume API router module for resume management operations.

This module implements the API endpoints for resume-related functionality including
resume creation, retrieval, optimization, PDF generation and deletion. It handles
the interface between HTTP requests and the resume repository, and coordinates
AI-powered resume optimization services.
"""

import asyncio
import json
import logging
import os
import secrets
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
    BackgroundTasks,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.database.models.resume import Resume, ResumeData
from app.database.repositories.resume_repository import ResumeRepository
from app.services.ai.ats_scoring import ATSScorerLLM
from app.services.ai.model_ai import AtsResumeOptimizer
from app.services.ai.cover_letter_generator import CoverLetterGenerator
from app.services.ai.resume_enrichment import ResumeEnrichmentWizard
from app.services.ai.phrase_blacklist import detect_ai_phrases, replace_ai_phrases, get_blacklist_stats
from app.services.resume.latex_generator import LaTeXGenerator
from app.services.resume.pdf_generator import generate_resume_pdf
from app.core.security import get_current_user, get_current_user_optional
from app.database.repositories.user_repository import UserRepository
from app.utils.file_handling import create_temporary_pdf, extract_text_from_pdf
from app.utils.scalability import get_ai_semaphore, get_job_status, set_job_status

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("app.utils.token_tracker").setLevel(logging.WARNING)


# Request and response models
class CreateResumeRequest(BaseModel):
    """Schema for creating a new resume."""

    user_id: str = Field(..., description="Unique identifier for the user")
    title: str = Field(..., description="Title of the resume")
    original_content: str = Field(..., description="Original content of the resume")
    job_description: str = Field(
        ..., description="Job description to tailor the resume for"
    )


class OptimizeResumeRequest(BaseModel):
    """Schema for optimizing an existing resume."""

    job_description: str = Field(
        ..., description="Job description to tailor the resume for"
    )
    template_id: Optional[str] = Field(
        "ats_standard", description="ID of the template style to use"
    )


class ResumeSummary(BaseModel):
    """Schema for resume summary information."""

    id: str = Field(..., description="Unique identifier for the resume")
    title: str = Field(..., description="Title of the resume")
    ats_score: Optional[int] = Field(
        None, description="ATS score of the resume if optimized"
    )
    created_at: datetime = Field(..., description="When the resume was created")
    updated_at: datetime = Field(..., description="When the resume was last updated")


class OptimizationResponse(BaseModel):
    """Schema for resume optimization response."""

    resume_id: str = Field(
        ..., description="Unique identifier for the optimized resume"
    )
    original_ats_score: int = Field(..., description="ATS score before optimization")
    optimized_ats_score: int = Field(..., description="ATS score after optimization")
    score_improvement: int = Field(
        ..., description="Score improvement after optimization"
    )
    matching_skills: List[str] = Field(
        [], description="Skills that match the job description"
    )
    missing_skills: List[str] = Field([], description="Skills missing from the resume")
    recommendation: str = Field("", description="AI recommendation for improvement")
    optimized_data: Dict[str, Any] = Field(..., description="Optimized resume data")


class ManualSaveRequest(BaseModel):
    title: str
    data: ResumeData
    resume_id: Optional[str] = None
    selected_template: Optional[str] = "ats_standard"

class ContactFormRequest(BaseModel):
    """Schema for contact form submission."""

    name: str = Field(..., description="Full name of the person reaching out")
    email: EmailStr = Field(..., description="Email address for return communication")
    subject: str = Field(..., description="Subject of the contact message")
    message: str = Field(..., description="Detailed message content")


class ContactFormResponse(BaseModel):
    """Schema for contact form response."""

    success: bool = Field(..., description="Whether the message was sent successfully")
    message: str = Field(..., description="Status message")


class ScoreResumeRequest(BaseModel):
    """Schema for scoring an existing resume."""

    job_description: str = Field(
        ..., description="Job description to score the resume against"
    )


class ResumeScoreResponse(BaseModel):
    """Schema for resume score response."""

    resume_id: str = Field(..., description="Unique identifier for the resume")
    ats_score: int = Field(..., description="ATS compatibility score (0-100)")
    matching_skills: List[str] = Field(
        [], description="Skills that match the job description"
    )
    missing_skills: List[str] = Field([], description="Skills missing from the resume")
    recommendation: str = Field("", description="AI recommendation for improvement")
    resume_skills: List[str] = Field([], description="Skills extracted from the resume")
    job_requirements: List[str] = Field(
        [], description="Requirements extracted from the job description"
    )


resume_router = APIRouter(prefix="/api/resume", tags=["Resume"])


async def get_resume_repository(request: Request) -> ResumeRepository:
    """Dependency for getting the resume repository instance.

    Args:
        request: The incoming request

    Returns:
    -------
        ResumeRepository: An instance of the resume repository
    """
    return ResumeRepository()


async def process_resume_upload(resume_id: str, temp_file_path: str, repo: ResumeRepository):
    """Background task to extract text and update resume."""
    import re
    try:
        resume_text = extract_text_from_pdf(temp_file_path)
        
        # Extract contact info from raw text
        contact_info = {}
        
        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text)
        if email_match:
            contact_info['email'] = email_match.group(0)
        
        # Extract phone number
        phone_match = re.search(r'(\+?[\d\s\-\(\)]{10,15})', resume_text.replace(' ', '').replace('-', ''))
        if not phone_match:
            phone_match = re.search(r'(\+?\d[\d\s\-\(\)]{9,14}\d)', resume_text)
        if phone_match:
            contact_info['phone'] = phone_match.group(0).strip()
        
        # Extract LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/([\w\.-]+)', resume_text, re.IGNORECASE)
        if linkedin_match:
            contact_info['linkedin'] = linkedin_match.group(1)
        
        # Extract GitHub
        github_match = re.search(r'github\.com/([\w\.-]+)', resume_text, re.IGNORECASE)
        if github_match:
            contact_info['github'] = github_match.group(1)
        
        # Extract Portfolio
        portfolio_match = re.search(r'(?:portfolio|website|personal site)[:\s]*(https?://[\w\.-]+)', resume_text, re.IGNORECASE)
        if portfolio_match:
            contact_info['portfolio'] = portfolio_match.group(1)
        
        # Extract LeetCode
        leetcode_match = re.search(r'leetcode\.com/([\w\.-]+)', resume_text, re.IGNORECASE)
        if leetcode_match:
            contact_info['leetcode'] = leetcode_match.group(1)
        
        # Extract GeeksforGeeks
        gfg_match = re.search(r'geeksforgeeks\.org/user/([\w\.-]+)', resume_text, re.IGNORECASE)
        if gfg_match:
            contact_info['geeksforgeeks'] = gfg_match.group(1)
        
        # Update resume with extracted contact info
        update_data = {"original_content": resume_text, "status": "pending"}
        update_data.update(contact_info)
        await repo.update_resume(resume_id, update_data)
        
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@resume_router.post("/", summary="Create a resume (Instant response)")
async def create_resume(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    job_description: str = Form(default=""),
    user_id: str = Form(default=""),
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Creates a resume record and processes text in background. Uses logged-in user's ID if available."""
    try:
        # Try to get logged-in user ID from session
        auth_user_id = await get_current_user_optional(request)
        effective_user_id = auth_user_id or user_id or "anonymous"
        
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Create record with status 'processing'
        new_resume = Resume(
            user_id=effective_user_id,
            title=title,
            original_content="Extracting text...",
            job_description=job_description,
            status="processing"
        )
        resume_id = await repo.create_resume(new_resume)
        if not resume_id:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(
                status_code=500,
                detail="Failed to create resume record.",
            )

        # Increment user's resume count if authenticated
        if auth_user_id:
            user_repo = UserRepository()
            await user_repo.increment_resume_count(auth_user_id)

        # Process text extraction in background
        background_tasks.add_task(process_resume_upload, resume_id, tmp_path, repo)

        return {"id": resume_id, "status": "uploading"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_optimization_task(
    resume_id: str,
    job_description: str,
    repo: ResumeRepository,
    api_key: str = None,
    api_base_url: str = None,
    model_name: str = None,
):
    """
    Background task: runs the full AI optimization pipeline.

    Uses:
    - asyncio.Semaphore (from scalability module) to cap concurrent LLM calls
      so we never exceed the LLM provider rate limits, even with 1500+ students.
    - run_in_executor to offload synchronous LangChain calls to a thread pool,
      keeping the FastAPI event loop fully responsive for other requests.
    - Auto-retry logic (2 attempts) with exponential backoff.
    """
    max_retries = 2
    semaphore = get_ai_semaphore()
    loop = asyncio.get_event_loop()

    # Resolve API config
    _api_key = api_key or settings.API_KEY
    _api_base = api_base_url or settings.API_BASE
    _model = model_name or settings.MODEL_NAME

    set_job_status(resume_id, "processing")
    await repo.update_one(
        {"id": resume_id},
        {"status": "processing", "updated_at": datetime.now().isoformat()},
    )

    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        logger.error(f"[{resume_id}] Resume not found, aborting task.")
        return

    resume_content = resume.get("original_content", "")

    for attempt in range(1, max_retries + 1):
        try:
            async with semaphore:
                logger.info(
                    f"[{resume_id}] Optimization attempt {attempt}/{max_retries} "
                    f"| semaphore: {semaphore._value} slots free"
                )

                # ── Step 1: Score original (sync → thread pool) ──
                def _score_original():
                    scorer = ATSScorerLLM(
                        model_name=_model, api_key=_api_key, api_base=_api_base
                    )
                    return scorer.compute_match_score(resume_content, job_description)

                # ── Step 2: Generate optimized resume (sync → thread pool) ──
                # Fast path: skip the optimizer's internal pre-score because we already
                # compute missing skills here. This removes one full LLM round trip.
                def _optimize(missing_skills: List[str]):
                    optimizer = AtsResumeOptimizer(
                        model_name=_model,
                        resume=resume_content,
                        api_key=_api_key,
                        api_base=_api_base,
                    )
                    return optimizer.generate_ats_optimized_resume_json(
                        job_description, missing_skills=missing_skills
                    )

                original_score_result = await loop.run_in_executor(None, _score_original)
                original_ats_score = int(original_score_result.get("final_score", 0))
                logger.info(f"[{resume_id}] Original ATS score: {original_ats_score}")

                missing_skills = original_score_result.get("missing_skills", []) or []
                result = await loop.run_in_executor(None, _optimize, missing_skills)

                if "error" in result:
                    raise RuntimeError(f"AI error: {result['error']}")

                # ── Step 3: Validate result ──
                optimized_data_model = ResumeData.parse_obj(result)

                # ── Step 4: Score optimized (sync → thread pool) ──
                def _score_optimized():
                    scorer = ATSScorerLLM(
                        model_name=_model, api_key=_api_key, api_base=_api_base
                    )
                    return scorer.compute_match_score(json.dumps(result), job_description)

                optimized_score_result = await loop.run_in_executor(None, _score_optimized)
                optimized_ats_score = int(optimized_score_result.get("final_score", 0))
                score_improvement = optimized_ats_score - original_ats_score
                logger.info(
                    f"[{resume_id}] Optimized ATS: {optimized_ats_score} "
                    f"(+{score_improvement})"
                )

            # ── Step 5: Persist to DB (outside semaphore — DB calls are fast) ──
            await repo.update_optimized_data(
                resume_id,
                optimized_data_model,
                optimized_ats_score,
                original_ats_score=original_ats_score,
                matching_skills=optimized_score_result.get("matching_skills", []),
                missing_skills=optimized_score_result.get("missing_skills", []),
                score_improvement=score_improvement,
                recommendation=optimized_score_result.get("recommendation", ""),
            )
            await repo.update_one(
                {"id": resume_id},
                {"status": "completed", "updated_at": datetime.now().isoformat()},
            )
            set_job_status(resume_id, "completed")
            logger.info(f"[{resume_id}] Optimization completed successfully.")
            return  # ✅ success

        except Exception as e:
            logger.error(
                f"[{resume_id}] Attempt {attempt} failed: {e}\n"
                + traceback.format_exc()
            )
            if attempt == max_retries:
                err_msg = str(e)[:1000]
                set_job_status(resume_id, "failed", error=err_msg)
                await repo.update_one(
                    {"id": resume_id},
                    {
                        "status": "failed",
                        "error_message": err_msg,
                        "updated_at": datetime.now().isoformat(),
                    },
                )
            else:
                # Exponential backoff before retry
                await asyncio.sleep(2 ** attempt)


@resume_router.get(
    "/{resume_id}",
    response_model=Dict[str, Any],
    summary="Get a resume",
    response_description="Resume retrieved successfully",
)
async def get_resume(
    resume_id: str,
    request: Request,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Get a specific resume by ID.

    Args:
        resume_id: ID of the resume to retrieve
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        Dict containing the resume data

    Raises:
    ------
        HTTPException: If the resume is not found
    """
    resume_data = await repo.get_resume_by_id(resume_id)
    if not resume_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found",
        )
    # Handle both MongoDB (_id) and Supabase (id) field names
    if "_id" in resume_data:
        resume_data["id"] = str(resume_data.pop("_id"))
    elif "id" not in resume_data:
        resume_data["id"] = resume_id

    live_job_status = get_job_status(resume_id)
    if live_job_status:
        resume_data["status"] = live_job_status.get("status", resume_data.get("status"))
        if live_job_status.get("error"):
            resume_data["error_message"] = live_job_status["error"]
    return resume_data


@resume_router.get(
    "/mine",
    response_model=List[ResumeSummary],
    summary="Get all resumes for the current logged-in user",
    response_description="Resumes retrieved successfully",
)
async def get_my_resumes(
    request: Request,
    user_id: str = Depends(get_current_user),
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Get all resumes for the currently authenticated user.

    Args:
        request: The incoming request
        user_id: ID of the current authenticated user
        repo: Resume repository instance

    Returns:
    -------
        List of resume summaries for the current user
    """
    resumes = await repo.get_resumes_by_user_id(user_id)
    formatted_resumes = []
    for resume in resumes:
        # Handle both MongoDB (_id) and Supabase (id) field names
        resume_id = resume.get("_id") or resume.get("id", "")
        if resume_id and hasattr(resume_id, '__str__'):
            resume_id = str(resume_id)
        formatted_resumes.append(
            {
                "id": resume_id,
                "title": resume.get("title"),
                "ats_score": resume.get("ats_score"),
                "created_at": resume.get("created_at"),
                "updated_at": resume.get("updated_at"),
            }
        )
    return formatted_resumes


@resume_router.get(
    "/user/{user_id}",
    response_model=List[ResumeSummary],
    summary="Get all resumes for a user",
    response_description="Resumes retrieved successfully",
)
async def get_user_resumes(
    user_id: str,
    request: Request,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Get all resumes for a specific user.

    Args:
        user_id: ID of the user whose resumes to retrieve
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        List of resume summaries for the specified user
    """
    resumes = await repo.get_resumes_by_user_id(user_id)
    formatted_resumes = []
    for resume in resumes:
        # Handle both MongoDB (_id) and Supabase (id) field names
        resume_id = resume.get("_id") or resume.get("id", "")
        if resume_id and hasattr(resume_id, '__str__'):
            resume_id = str(resume_id)
        formatted_resumes.append(
            {
                "id": resume_id,
                "title": resume.get("title"),
                "ats_score": resume.get("ats_score"),
                "created_at": resume.get("created_at"),
                "updated_at": resume.get("updated_at"),
            }
        )
    return formatted_resumes
    
@resume_router.post("/{resume_id}/track-download")
async def track_download(
    resume_id: str,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Increment download count when a resume is downloaded."""
    resume = await repo.get_resume_by_id(resume_id)
    if resume and resume.get("user_id"):
        user_repo = UserRepository()
        await user_repo.increment_download_count(resume.get("user_id"))
    return {"success": True}

@resume_router.post("/save-manual")
async def save_manual_resume(
    request: ManualSaveRequest,
    user_id: str = Depends(get_current_user),
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Save a manually built resume to the database."""
    try:
        # If resume_id is provided, update existing, otherwise create new
        if request.resume_id:
            update_data = {
                "title": request.title,
                "optimized_data": request.data.model_dump(),
                "selected_template": request.selected_template,
                "status": "completed"
            }
            success = await repo.update_resume(request.resume_id, update_data)
            return {"status": "success", "id": request.resume_id} if success else {"status": "error"}
        else:
            new_resume = Resume(
                user_id=user_id,
                title=request.title,
                original_content="Manually built resume",
                job_description="N/A",
                optimized_data=request.data,
                status="completed",
                selected_template=request.selected_template or "ats_standard"
            )
            created_id = await repo.create_resume(new_resume)
            return {"status": "success", "id": created_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@resume_router.put(
    "/{resume_id}",
    response_model=Dict[str, bool],
    summary="Update a resume",
    response_description="Resume updated successfully",
)
async def update_resume(
    resume_id: str,
    update_data: Dict[str, Any] = Body(...),
    request: Request = None,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Update a specific resume by ID.

    Args:
        resume_id: ID of the resume to update
        update_data: Data to update in the resume
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        Dict indicating success status

    Raises:
    ------
        HTTPException: If the resume is not found or update fails
    """
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found",
        )
    success = await repo.update_resume(resume_id, update_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resume",
        )
    return {"success": True}


@resume_router.delete(
    "/{resume_id}",
    response_model=Dict[str, bool],
    summary="Delete a resume",
    response_description="Resume deleted successfully",
)
async def delete_resume(
    resume_id: str,
    request: Request = None,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Delete a specific resume by ID.

    Args:
        resume_id: ID of the resume to delete
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        Dict indicating success status

    Raises:
    ------
        HTTPException: If the resume is not found or deletion fails
    """
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found",
        )
    success = await repo.delete_resume(resume_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resume",
        )
    return {"success": True}


@resume_router.post(
    "/{resume_id}/optimize",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Optimize a resume with AI (Non-blocking background task)",
    response_description="Optimization queued — poll /status for progress",
)
async def optimize_resume(
    resume_id: str,
    optimization_request: OptimizeResumeRequest,
    background_tasks: BackgroundTasks,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """
    Queues resume optimization as a background task.

    Returns HTTP 202 IMMEDIATELY — the student's browser is not left hanging.
    The AI work happens concurrently (up to MAX_CONCURRENT_AI_CALLS at a time,
    default 20). Poll GET /{resume_id}/status to check progress.
    """
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    job_description = optimization_request.job_description or resume.get(
        "job_description", ""
    )
    if not job_description:
        raise HTTPException(
            status_code=400,
            detail="Job description is required for optimization",
        )

    # Resolve API config at request time (not inside background task)
    api_key = settings.API_KEY
    api_base_url = settings.API_BASE
    model_name = settings.MODEL_NAME

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="AI API key is not configured. Set API_KEY in .env file.",
        )

    # Fire and forget — returns 202 instantly
    background_tasks.add_task(
        run_optimization_task,
        resume_id,
        job_description,
        repo,
        api_key,
        api_base_url,
        model_name,
    )

    return {
        "message": "Optimization queued. Poll /status for progress.",
        "resume_id": resume_id,
        "status": "processing",
    }


@resume_router.get("/{resume_id}/status")
async def get_optimization_status(
    resume_id: str, repo: ResumeRepository = Depends(get_resume_repository)
):
    """Get the current status of the resume optimization.

    Args:
        resume_id: ID of the resume to check
        repo: Resume repository instance
    """
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    try:
        live_job_status = get_job_status(resume_id) or {}
        effective_status = live_job_status.get("status") or resume.get("status", "pending")
        return {
            "status": effective_status,
            "ats_score": resume.get("ats_score"),
            "original_ats_score": resume.get("original_ats_score"),
            "score_improvement": resume.get("score_improvement"),
            "matching_skills": resume.get("matching_skills", []),
            "missing_skills": resume.get("missing_skills", []),
            "recommendation": resume.get("recommendation", ""),
            "error_message": live_job_status.get("error") or resume.get("error_message", ""),
        }
    except HTTPException:
        # Re-raise HTTP exceptions as they're already properly formatted
        raise
    except Exception as e:
        # Log the full stack trace for any other exception
        logger.error(f"Unexpected error during resume optimization: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")

        # Check for specific error types to provide better error messages
        if "API key" in str(e).lower() or "authentication" in str(e).lower():
            logger.error("AI service authentication error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error authenticating with AI service. Please check API configuration.",
            )
        elif "timeout" in str(e).lower() or "time" in str(e).lower():
            logger.error("AI service timeout error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service request timed out. Please try again later.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error during resume optimization: {str(e)}",
            )


@resume_router.post(
    "/{resume_id}/score",
    response_model=ResumeScoreResponse,
    summary="Score a resume against a job description",
    response_description="Resume scored successfully",
)
async def score_resume(
    resume_id: str,
    scoring_request: ScoreResumeRequest,
    request: Request,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Score a resume against a job description using ATS algorithms.

    This endpoint analyzes the resume against the provided job description and
    returns an ATS compatibility score along with matching skills and recommendations.

    Args:
        resume_id: ID of the resume to score
        scoring_request: Contains the job description to score against
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        ResumeScoreResponse: Contains the ATS score and skill analysis

    Raises:
    ------
        HTTPException: If the resume is not found or scoring fails
    """
    logger.info(f"Starting resume scoring for resume_id: {resume_id}")

    # Retrieve resume
    logger.info(f"Retrieving resume with ID: {resume_id}")
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        logger.warning(f"Resume not found with ID: {resume_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found",
        )

    # Get API configuration
    api_key = settings.API_KEY
    api_base_url = settings.API_BASE
    model_name = settings.MODEL_NAME

    if not api_key:
        logger.error("AI API key not configured in settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI API key not configured",
        )

    # Initialize ATS scorer
    try:
        ats_scorer = ATSScorerLLM(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base_url,
        )

        # Get job description
        job_description = scoring_request.job_description
        if not job_description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description is required for scoring",
            )

        # Get resume content - first check if optimized data exists, use that for comparison
        resume_content = resume["original_content"]
        
        # Optionally also score the optimized version if it exists
        optimized_data = resume.get("optimized_data")
        optimized_score = None
        
        # Score the original resume
        logger.info("Scoring original resume against job description")
        score_result = ats_scorer.compute_match_score(
            resume_content, job_description
        )
        ats_score = int(score_result["final_score"])
        
        # If optimized data exists, score it too for comparison
        if optimized_data:
            logger.info("Scoring optimized resume for comparison")
            if isinstance(optimized_data, str):
                optimized_content = optimized_data
            else:
                optimized_content = json.dumps(optimized_data)
            
            optimized_score_result = ats_scorer.compute_match_score(
                optimized_content, job_description
            )
            optimized_score = int(optimized_score_result["final_score"])
            logger.info(f"Original score: {ats_score}, Optimized score: {optimized_score}")
        
        # Prepare enhanced recommendation if we have both scores
        recommendation = score_result.get("recommendation", "")
        if optimized_score:
            improvement = optimized_score - ats_score
            if improvement > 0:
                recommendation += f"\n\nYour optimized resume scores {improvement} points higher ({optimized_score}%). Consider using the optimized version for better results."

        return {
            "resume_id": resume_id,
            "ats_score": ats_score,
            "matching_skills": score_result.get("matching_skills", []),
            "missing_skills": score_result.get("missing_skills", []),
            "recommendation": recommendation,
            "resume_skills": score_result.get("resume_skills", []),
            "job_requirements": score_result.get("job_requirements", []),
        }

    except Exception as e:
        logger.error(f"Error during resume scoring: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")

        # Check for specific error types
        if "API key" in str(e).lower() or "authentication" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error authenticating with AI service. Please check API configuration.",
            )
        elif "timeout" in str(e).lower() or "time" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service request timed out. Please try again later.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error during resume scoring: {str(e)}",
            )


@resume_router.get(
    "/{resume_id}/download",
    summary="Download a resume as PDF or HTML",
    response_description="Resume downloaded successfully",
)
async def download_resume(
    resume_id: str,
    use_optimized: bool = True,
    template: str = "resume_template.tex",
    format: str = "html",  # Default to HTML since LaTeX isn't available on Windows
    request: Request = None,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Download a resume as an HTML file (or PDF if LaTeX is available).

    This endpoint generates an HTML version of the resume.
    By default, it uses the optimized version of the resume.

    Args:
        resume_id: ID of the resume to download
        use_optimized: Whether to use the optimized version of the resume
        template: LaTeX template to use (ignored for HTML)
        format: Output format (html or pdf)
        request: The incoming request
        repo: Resume repository instance

    Returns:
    -------
        HTMLResponse or FileResponse: Resume file download

    Raises:
    ------
        HTTPException: If the resume is not found
    """
    resume = await repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found",
        )
    
    try:
        if use_optimized and resume.get("optimized_data"):
            json_data = resume["optimized_data"]
        elif not use_optimized and resume.get("original_content"):
            # If original content is available, we'd normally parse it, 
            # but for now we provide a minimal structure
            json_data = {
                "user_information": {
                    "name": resume.get("title", "Resume"),
                    "main_job_title": "",
                    "profile_description": resume.get("original_content", ""),
                    "email": "user@example.com",
                    "experiences": [],
                    "education": [],
                    "skills": {"hard_skills": [], "soft_skills": []}
                }
            }
        elif resume.get("optimized_data"):
            json_data = resume["optimized_data"]
        else:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume data is empty. Please add content or optimize first.",
            )
        
        if isinstance(json_data, str):
            import json as json_mod
            json_data = json_mod.loads(json_data)
        
        # Generate PDF resume using fpdf2 with selected template
        template_id = resume.get("selected_template", "ats_standard")
        pdf_path = generate_resume_pdf(json_data, template_id=template_id)
        
        filename = f"{resume.get('title', 'resume')}.pdf"
        
        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating resume: {str(e)}",
        )




@resume_router.get(
    "/{resume_id}/preview",
    summary="Preview a resume",
    response_description="Resume previewed successfully",
)
async def preview_resume(
    resume_id: str,
    request: Request,
    repo: ResumeRepository = Depends(get_resume_repository),
):
    """Preview a resume (not implemented).

    This endpoint is intended for previewing a resume, but it's not yet implemented.

    Args:
        resume_id: ID of the resume to preview
        request: The incoming request
        repo: Resume repository instance

    Raises:
    ------
        HTTPException: Always raises a 501 Not Implemented error
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Resume preview not implemented. Use the download endpoint to generate a PDF.",
    )


@resume_router.post(
    "/contact",
    response_model=ContactFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    response_description="Contact form submission status",
)
async def submit_contact_form(
    request: ContactFormRequest = Body(...),
) -> ContactFormResponse:
    """Submit a contact form.

    This endpoint processes contact form submissions from users wanting to reach out
    to the project maintainers, report issues, or ask questions.

    Args:
        request: The contact form data including name, email, subject, and message

    Returns:
    -------
        ContactFormResponse: Success status and confirmation message

    Raises:
    ------
        HTTPException: If there's an issue processing the form
    """
    try:
        # In a production environment, this would typically:
        # 1. Store the message in a database
        # 2. Send an email notification to administrators
        # 3. Potentially send an auto-response to the user

        # For now, we'll just return a success response
        # TODO: Implement actual email sending functionality

        return ContactFormResponse(
            success=True,
            message="Thank you for your message! We'll get back to you soon.",
        )
    except Exception as e:
        # Log the error in a production environment
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process your message: {str(e)}",
        )
 

# ===== COVER LETTER GENERATION =====
class CoverLetterRequest(BaseModel):
    resume_id: str
    job_description: str
    job_title: str = ""

class CoverLetterResponse(BaseModel):
    cover_letter: str
    word_count: int
    status: str

@resume_router.post("/cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter(req: CoverLetterRequest):
    """Generate a tailored cover letter from resume + job description."""
    repo = ResumeRepository()
    resume = await repo.get_resume_by_id(req.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume_text = resume.get("original_content", "")
    if not resume_text or resume_text == "Extracting text...":
        raise HTTPException(status_code=400, detail="Resume text not available")

    generator = CoverLetterGenerator()
    result = generator.generate(resume_text, req.job_description, req.job_title)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    return CoverLetterResponse(
        cover_letter=result["cover_letter"],
        word_count=result["word_count"],
        status="success"
    )


# ===== RESUME ENRICHMENT WIZARD =====
class EnrichmentAnalyzeRequest(BaseModel):
    resume_id: str
    job_description: str = ""

class EnrichmentEnhanceRequest(BaseModel):
    resume_id: str
    qa_pairs: list

@resume_router.post("/enrichment/analyze")
async def analyze_resume(req: EnrichmentAnalyzeRequest):
    """Find weak descriptions and generate clarifying questions."""
    repo = ResumeRepository()
    resume = await repo.get_resume_by_id(req.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume_text = resume.get("original_content", "")
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text not available")

    wizard = ResumeEnrichmentWizard()
    result = wizard.find_weak_descriptions(resume_text, req.job_description)
    return result

@resume_router.post("/enrichment/enhance")
async def enhance_resume(req: EnrichmentEnhanceRequest):
    """Generate enhanced descriptions from candidate's answers."""
    repo = ResumeRepository()
    resume = await repo.get_resume_by_id(req.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    job_desc = resume.get("job_description", "")
    wizard = ResumeEnrichmentWizard()
    result = wizard.enhance_descriptions(req.qa_pairs, job_desc)
    return result


# ===== AI PHRASE BLACKLIST =====
class PhraseCheckRequest(BaseModel):
    text: str

class PhraseCheckResponse(BaseModel):
    ai_phrases: list
    clean_text: str
    replacements: int
    stats: dict

@resume_router.post("/phrases/check", response_model=PhraseCheckResponse)
async def check_ai_phrases(req: PhraseCheckRequest):
    """Check text for AI-sounding phrases and suggest replacements."""
    detected = detect_ai_phrases(req.text)
    clean_text, replacements = replace_ai_phrases(req.text)
    stats = get_blacklist_stats()

    return PhraseCheckResponse(
        ai_phrases=[{"phrase": p, "alternative": a} for p, a in detected],
        clean_text=clean_text,
        replacements=replacements,
        stats=stats
    )

@resume_router.get("/phrases/stats")
async def phrase_stats():
    """Get blacklist statistics."""
    return get_blacklist_stats()
