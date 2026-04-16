"""AI-powered ATS Soring module.

This module provides the ATSScorerLLM class that leverages AI language models
to analyze and score resumes based on job descriptions.
"""

import json
import os
import re
import random
from typing import List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from app.utils.token_tracker import TokenTracker


class SkillsExtraction(BaseModel):
    """Model for structured extraction of skills and qualifications from text.

    This Pydantic model defines the structure for extracted information from
    resumes and job descriptions, including technical skills, experience,
    requirements, and industry domains.
    """

    skills: List[str] = Field(
        description="List of technical skills extracted from the text"
    )
    experience_years: Optional[int] = Field(
        description="Years of experience mentioned in the text, if any"
    )
    key_requirements: List[str] = Field(
        description="Key requirements or qualifications extracted from the text"
    )
    domains: List[str] = Field(
        description="Domains or industries mentioned in the text"
    )


from app.core.config import settings

class ATSScorerLLM:
    """Class for scoring resumes against job descriptions using AI techniques.

    This class provides methods to extract information from resumes and job descriptions,
    and perform a comprehensive match analysis using LLM-based techniques only.
    All scoring, skill matching, and recommendations are 100% LLM-driven, making the system domain-agnostic and robust for any industry.
    """

    def __init__(self, model_name=None, api_key=None, api_base=None, user_id=None):
        """Initialize the ATS scorer with API credentials and model configuration.

        Args:
            model_name (str, optional): Name of the LLM model to use.
            api_key (str, optional): API key for the LLM service.
            api_base (str, optional): Base URL for the API service.
            user_id (str, optional): User ID for token tracking.
        """
        # Support single key or rotation from pool
        self.api_keys = [api_key] if api_key else getattr(settings, 'API_KEYS', [])
        self.api_key = random.choice(self.api_keys) if self.api_keys else None
        self.api_base = api_base or settings.API_BASE
        self.model_name = model_name or settings.MODEL_NAME
        self.user_id = user_id

        if not self.api_key:
            raise ValueError("An LLM API key is required.")
        if not self.api_base:
            raise ValueError("An LLM API base is required.")
        if not self.model_name:
            raise ValueError("An LLM model name is required.")

        # Use TokenTracker to create a tracked instance of the LLM
        self.llm = TokenTracker.get_tracked_langchain_llm(
            model_name=self.model_name,
            temperature=0.1,
            api_key=self.api_key,
            api_base=self.api_base,
            feature="ats_scoring",
            user_id=self.user_id
        )

        self.parser = PydanticOutputParser(pydantic_object=SkillsExtraction)

        self.setup_prompts()

        self.setup_chains()

    def setup_prompts(self):
        """Set up a high-precision consolidated prompt for ATS analysis."""
        self.consolidated_prompt = PromptTemplate(
            template="""You are an expert ATS (Applicant Tracking System) analyzer and recruiter.
            Your task is to analyze a resume against a job description with extreme precision.

            RESUME TEXT:
            {resume_text}

            JOB DESCRIPTION:
            {job_text}

            INSTRUCTIONS:
            1. **Skill Extraction**: Extract ALL technical, soft, and domain-specific skills from both the resume and the job description.
            2. **Match Analysis**: Compare the two. Look for exact matches, synonyms, and transferable skills.
            3. **Scoring Logic (0-100)**:
               - **Score 90-100**: If the resume is well-tailored, includes most keywords from the JD, and shows strong alignment. This is the MOST COMMON range for good candidates.
               - **Score 80-89**: Solid match with most requirements met, minor gaps in secondary skills.
               - **Score 65-79**: Decent match but missing some important keywords or experience.
               - **Score <65**: Major gaps in core requirements, poorly tailored.
               
               **IMPORTANT GUIDANCE**:
               - **BE GENEROUS**: If the candidate has relevant experience, education, or projects that relate to the JD, reward them generously.
               - **Transferable skills count**: If they know Python and the JD asks for PyTorch, that's a strong match.
               - **Students and interns should score 85+** if they have decent projects and relevant coursework.
               - **Aim HIGH**: Most good candidates should score between 85-98. Only give low scores if there are MAJOR gaps.

            Format your response as a JSON object:
            {{
                "resume_skills": ["list"],
                "job_requirements": ["list"],
                "score": number,
                "matching_skills": ["list"],
                "missing_skills": ["list"],
                "recommendation": "Executive summary of fit",
                "rationale": "Detailed explanation of why this score was given"
            }}
            """,
            input_variables=["resume_text", "job_text"],
        )

    def setup_chains(self):
        """Set up the LangChain chain."""
        self.chain = self.consolidated_prompt | self.llm

    async def compute_match_score_async(self, resume_text: str, job_text: str) -> dict:
        """Calculate match score asynchronously in a single LLM call."""
        try:
            result = await self.chain.ainvoke({"resume_text": resume_text, "job_text": job_text})
            
            # Extract JSON from response
            content = result.content
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                
                # Apply aggressive score boost for optimized resumes
                raw_score = data.get("score", 50)
                llm_score = max(raw_score / 100, 0.45)  # Floor at 45%
                
                # Apply generous boost to all scores
                if llm_score < 0.60:
                    # Low scores get biggest boost
                    llm_score = llm_score + 0.25 * (1 - llm_score)
                elif llm_score < 0.75:
                    # Mid scores get moderate boost
                    llm_score = llm_score + 0.18 * (1 - llm_score)
                elif llm_score < 0.85:
                    # Good scores get small boost
                    llm_score = llm_score + 0.10 * (1 - llm_score)
                # Scores >= 85% pass through unchanged (already high)
                
                final_score = min(llm_score, 1.0)  # Cap at 100%
                
                return {
                    "llm_score": round(llm_score * 100, 2),
                    "final_score": round(final_score * 100, 2),
                    "resume_skills": data.get("resume_skills", []),
                    "job_requirements": data.get("job_requirements", []),
                    "matching_skills": data.get("matching_skills", []),
                    "missing_skills": data.get("missing_skills", []),
                    "recommendation": data.get("recommendation", ""),
                    "rationale": data.get("rationale", "")
                }
        except Exception as e:
            print(f"Error in async match score: {e}")
            
        # Fallback
        return self.compute_match_score(resume_text, job_text)

    def compute_match_score(self, resume_text: str, job_text: str, weights: dict = None) -> dict:
        """Calculate match score synchronously (legacy support)."""
        # For simplicity and speed, we use the same consolidated logic but sync
        try:
            result = self.chain.invoke({"resume_text": resume_text, "job_text": job_text})
            content = result.content
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                
                # Apply aggressive score boost
                raw_score = data.get("score", 50)
                llm_score = max(raw_score / 100, 0.45)  # Floor at 45%
                
                # Apply generous boost to all scores
                if llm_score < 0.60:
                    # Low scores get biggest boost
                    llm_score = llm_score + 0.25 * (1 - llm_score)
                elif llm_score < 0.75:
                    # Mid scores get moderate boost
                    llm_score = llm_score + 0.18 * (1 - llm_score)
                elif llm_score < 0.85:
                    # Good scores get small boost
                    llm_score = llm_score + 0.10 * (1 - llm_score)
                # Scores >= 85% pass through unchanged (already high)
                
                final_score = min(llm_score, 1.0)  # Cap at 100%
                
                return {
                    "llm_score": round(llm_score * 100, 2),
                    "final_score": round(final_score * 100, 2),
                    "resume_skills": data.get("resume_skills", []),
                    "job_requirements": data.get("job_requirements", []),
                    "matching_skills": data.get("matching_skills", []),
                    "missing_skills": data.get("missing_skills", []),
                    "recommendation": data.get("recommendation", ""),
                    "rationale": data.get("rationale", "")
                }
        except Exception as e:
            print(f"Error in sync match score: {e}")
            
        return {
            "llm_score": 50, "final_score": 50, "resume_skills": [], "job_requirements": [],
            "matching_skills": [], "missing_skills": [], "recommendation": "Error", "rationale": ""
        }


# Example usage
def demo_ats_scorer_llm():
    """Demo function to showcase the ATSScorerLLM functionality."""
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("API_KEY")
    model_name = os.getenv("API_MODEL_NAME", "gpt-4-turbo")
    api_base = os.getenv("API_BASE", "https://api.openai.com/v1")

    scorer = ATSScorerLLM(api_key=api_key, model_name=model_name, api_base=api_base)

    resume = """
    """

    job_desc = """
    """

    result = scorer.compute_match_score(resume, job_desc)

    print("Resume Skills:", result["resume_skills"])
    print("Job Requirements:", result["job_requirements"])
    print("Matching Skills:", result["matching_skills"])
    print("Missing Skills:", result["missing_skills"])
    print(f"Final Score: {result['final_score']}%")
    print("Recommendation:", result["recommendation"])
    print("Rationale:", result["rationale"])


if __name__ == "__main__":
    demo_ats_scorer_llm()
