"""AI-powered resume optimization module.

This module provides the AtsResumeOptimizer class that leverages AI language models
to analyze and optimize resumes based on job descriptions, improving compatibility
with Applicant Tracking Systems (ATS).
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.services.ai.ats_scoring import ATSScorerLLM
from app.utils.token_tracker import TokenTracker


from app.core.config import settings

class AtsResumeOptimizer:
    """ATS Resume Optimizer.

    A class that uses AI language models to optimize resumes for Applicant Tracking
    Systems (ATS) based on specific job descriptions.
    """

    def __init__(
        self,
        model_name: str = None,
        resume: str = None,
        api_key: str = None,
        api_base: str = None,
        user_id: str = None,
    ) -> None:
        """Initialize the AI model for resume processing.

        Args:
            model_name: The name of the OpenAI model to use.
            resume: The resume text to be optimized.
            api_key: OpenAI API key for authentication.
            api_base: Base URL for the OpenAI API.
            user_id: Optional user ID for token tracking.
        """
        self.model_name = model_name or settings.MODEL_NAME
        self.resume = resume
        self.api_key = api_key or settings.API_KEY
        self.api_base = api_base or settings.API_BASE
        self.user_id = user_id

        # Initialize LLM component and output parser
        self.llm = self._get_openai_model()
        self.output_parser = JsonOutputParser()
        self.chain = None
        
        # Initialize ATS scorer for skill extraction and analysis
        self.ats_scorer = None
        if self.api_key and self.api_base and self.model_name:
            self.ats_scorer = ATSScorerLLM(
                model_name=self.model_name,
                api_key=self.api_key,
                api_base=self.api_base,
                user_id=self.user_id,
            )

        self._setup_chain()

    def _get_openai_model(self) -> ChatOpenAI:
        """Initialize the OpenAI model with appropriate settings.
        
        Returns:
            ChatOpenAI: Configured language model instance with token tracking
        """
        if self.model_name:
            # Create LLM instance with token tracking for usage monitoring
            return TokenTracker.get_tracked_langchain_llm(
                model_name=self.model_name,
                temperature=0,
                api_key=self.api_key,
                api_base=self.api_base,
                feature="resume_optimization",
                user_id=self.user_id,
                metadata={"resume_length": len(self.resume) if self.resume else 0}
            )
        else:
            # Fallback to standard model if no specific model is configured
            return ChatOpenAI(temperature=0)

    def _get_prompt_template(self, missing_skills: Optional[List[str]] = None) -> PromptTemplate:
        """Create the PromptTemplate for ATS resume optimization.
        
        Args:
            missing_skills: A list of skills identified as missing from the resume
                        that should be incorporated if the candidate has them.

        Returns:
            PromptTemplate: A prompt template with instructions for resume optimization.
        """
        recommended_skills_section = ""
        if missing_skills and len(missing_skills) > 0:
            skills_list = ", ".join([f"'{skill}'" for skill in missing_skills])
            recommended_skills_section = f"""
        ## RECOMMENDED SKILLS TO ADD
        
        The following skills were identified as potentially valuable for this position but may be missing or not prominently featured in the resume:
        
        {skills_list}
        
        If the candidate has any experience with these skills, even minor exposure:
        - Highlight them prominently in the skills section
        - Look for ways to showcase these skills in past experience descriptions
        - Ensure you're using the exact terminology as listed
        - Look for related skills or experience that could be reframed to match these requirements
        - Reframe transferable or implied experience to match the job requirements where ethically possible
        - Be assertive in surfacing any relevant experience, even if it is not an exact match, as long as it is truthful
        - Do NOT fabricate experience with these skills, only highlight them if they exist
        """
        
        template = f"""
        # ROLE: Expert ATS Resume Optimization Specialist
        You are an expert ATS (Applicant Tracking System) Resume Optimizer with specialized knowledge in resume writing, keyword optimization, and applicant tracking systems. Your task is to transform the candidate's existing resume into a highly optimized version tailored specifically to the provided job description, maximizing the candidate's chances of passing through ATS filters while maintaining honesty and accuracy.
        
        ## INPUT DATA:
        
        ### JOB DESCRIPTION:
        {{job_description}}

        ### CANDIDATE'S CURRENT RESUME:
        {{resume}}
        
        {recommended_skills_section}

        ## OPTIMIZATION PROCESS:

        1. **ANALYZE THE JOB DESCRIPTION**
            - Extract key requirements, skills, qualifications, and responsibilities
            - Identify primary keywords, secondary keywords, and industry-specific terminology
            - Note the exact phrasing and terminology used by the employer
            - Identify technical requirements (software, tools, frameworks, etc.)
            - Detect company values and culture indicators
            - Determine desired experience level and specific metrics/achievements valued
            - Pay special attention to both hard skills (technical) and soft skills (interpersonal)

        2. **EVALUATE THE CURRENT RESUME**
            - Compare existing content against job requirements
            - Identify skills and experiences that align with the job
            - Detect terminology mismatches and missing keywords
            - Assess the presentation of achievements and results
            - Calculate an initial "match score" to identify improvement areas
            - Note transferable skills that could be reframed for the target position
            - Look for implied skills that might not be explicitly stated

        3. **CREATE AN ATS-OPTIMIZED RESUME**
            - Use a clean, ATS-friendly format with standard section headings
            - Include the candidate's name, contact information, and professional profiles
            - Create a targeted professional summary highlighting relevant qualifications
            - Incorporate exact keywords and phrases from the job description throughout the resume
            - Prioritize and emphasize experiences most relevant to the target position
            - Reorder content to place most relevant experiences and skills first
            - Use industry-standard terminology that ATS systems recognize
            - Quantify achievements with metrics where possible (numbers, percentages, dollar amounts)
            - Remove irrelevant information that doesn't support this application
            - Ensure job titles, company names, dates, and locations are clearly formatted
            - Include a skills section with relevant hard and soft skills using job description terminology
            - Highlight both technical capabilities and relevant soft skills like communication, teamwork, leadership
            - Emphasize transferable skills and reframe related experience to match job requirements, even if not an exact match
            - Be assertive in surfacing all relevant experience, including implied or adjacent skills, as long as it is truthful

        4. **ATS OPTIMIZATION TECHNIQUES**
            - Use standard section headings (e.g., "Work Experience" not "Career Adventures")
            - Avoid tables, columns, headers, footers, images, and special characters
            - Use standard bullet points (• or - only)
            - Use common file formats and fonts (Arial, Calibri, Times New Roman)
            - Include keywords in context rather than keyword stuffing
            - Use both spelled-out terms and acronyms where applicable (e.g., "Search Engine Optimization (SEO)")
            - Keep formatting consistent throughout the document
            - For technical positions, include relevant projects with clear descriptions
            - Limit project listings to 3-4 most relevant examples
            - Use synonyms and related terms for key skills to maximize keyword matching
            - Make connections between past experience and job requirements clear and explicit

        5. **ATS SCORING LOGIC (For `ats_metrics`)**:
            - **Strictness**: Be objective. Don't just give 100%.
            - **90-100**: Well-tailored, strong keyword alignment, all core requirements met.
            - **80-89**: Solid match, maybe missing 1-2 minor secondary skills.
            - **70-79**: Good attempt but clear gaps in experience or specific tools.
            - **Below 70**: Mismatch in seniority or core technical stack.
            - **Generosity**: For students/interns, reward relevant projects and courses at 85+ if they show potential.

        ## QUALITY & ALIGNMENT CONSTRAINTS:
        - **Impact Verbs**: Use strong action verbs (e.g., 'Engineered', 'Orchestrated', 'Optimized', 'Spearheaded') at the start of every bullet point.
        - **JD Alignment**: For every single bullet point, ask yourself: 'How does this directly address a requirement in the Job Description?'
        - **Neat & Professional**: Write descriptions that are concise but descriptive. Avoid vague phrases like 'responsible for'. Focus on what you DID and the RESULT you achieved.
        - **Fill the Space**: Expand on the most relevant experiences to ensure the resume looks full, professional, and dense.
        - **No Hallucination**: Do not invent new jobs, but feel free to rephrase existing tasks to be 100% aligned with the JD keywords.

        ## OUTPUT FORMAT:

        You MUST return ONLY a valid JSON object with NO additional text, explanation, or commentary.
        The JSON must follow this EXACT structure:

        {{{{
            "user_information": {{{{
                "name": "",
                "main_job_title": "",
                "profile_description": "",
                "email": "",
                "linkedin": "",
                "github": "",
                "experiences": [
                    {{{{
                        "job_title": "",
                        "company": "",
                        "start_date": "",
                        "end_date": "",
                        "location": "",
                        "four_tasks": []
                    }}}}
                ],
                "education": [
                    {{{{
                        "institution": "",
                        "degree": "",
                        "location": "",
                        "description": "",
                        "start_date": "",
                        "end_date": ""
                    }}}}
                ],
                "skills": {{{{
                    "hard_skills": [],
                    "soft_skills": []
                }}}},
                "hobbies": []
            }}}},
            "projects": [
                {{{{
                    "project_name": "",
                    "project_link": "",
                    "two_goals_of_the_project": [],
                    "project_end_result": "",
                    "tech_stack": []
                }}}}
            ],
            "certificate": [
                {{{{
                    "name": "",
                    "link" : "",
                    "institution": "",
                    "description": "",
                    "date": ""
                }}}}
            ],
            "extra_curricular_activities": [
                {{{{
                    "name": "",
                    "description": "",
                    "start_date": "",
                    "end_date": ""
                }}}}
            ],
            "ats_metrics": {{{{
                "optimized_score": 0,
                "matching_skills": [],
                "missing_skills": [],
                "recommendation": ""
            }}}}
        }}}}

        IMPORTANT REQUIREMENTS:
        1. The "four_tasks" array must contain EXACTLY 4 items for each experience
        2. The "two_goals_of_the_project" array must contain EXACTLY 2 items for each project
        3. Make sure all dates follow a consistent format (YYYY-MM or MM/YYYY)
        4. Ensure all fields are filled with appropriate data extracted from the resume
        5. Return ONLY the JSON object with no other text
        """
        return PromptTemplate.from_template(template=template)

    def _setup_chain(self, missing_skills: Optional[List[str]] = None) -> None:
        """Set up the processing pipeline for job descriptions and resumes.

        This method configures the functional composition approach with the pipe operator
        to create a processing chain from prompt template to language model.
        
        Args:
            missing_skills: List of skills identified as missing that should be incorporated
                        into the optimization prompt.
        """
        prompt_template = self._get_prompt_template(missing_skills)
        self.chain = prompt_template | self.llm

    async def generate_ats_optimized_resume_json_async(
        self, job_description: str, missing_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate an ATS-optimized resume asynchronously for better speed."""
        if not self.resume:
            return {"error": "Resume not provided"}

        try:
            score_results = {}

            provided_missing_skills = missing_skills if missing_skills is not None else None

            # Step 1: Analyze resume against job description asynchronously only
            # when we were not already given missing skills by the caller.
            if provided_missing_skills is None and self.ats_scorer:
                try:
                    score_results = await self.ats_scorer.compute_match_score_async(
                        self.resume, job_description
                    )
                    provided_missing_skills = score_results.get("missing_skills", [])
                except Exception as e:
                    print(f"Warning: Async ATS scoring failed: {e}")

            self._setup_chain(provided_missing_skills)

            # Step 2: Generate optimized resume
            result = await self.chain.ainvoke(
                {"job_description": job_description, "resume": self.resume}
            )

            # Step 3: Parse JSON
            content = result.content if hasattr(result, "content") else result
            try:
                # Direct JSON parsing or extraction
                json_match = re.search(r"(\{[\s\S]*\})", content)
                if json_match:
                    json_result = json.loads(json_match.group(1))
                    
                    # Merge initial score if we computed it
                    if score_results:
                        if "ats_metrics" not in json_result:
                            json_result["ats_metrics"] = {}
                        json_result["ats_metrics"]["initial_score"] = score_results.get("final_score", 0)
                        # Only fill if LLM didn't fill its own metrics
                        if not json_result["ats_metrics"].get("matching_skills"):
                             json_result["ats_metrics"]["matching_skills"] = score_results.get("matching_skills", [])
                        if not json_result["ats_metrics"].get("missing_skills"):
                             json_result["ats_metrics"]["missing_skills"] = score_results.get("missing_skills", [])
                    
                    return json_result
            except Exception as e:
                return {"error": f"JSON parse error: {e}", "raw": content[:500]}

            return {"error": "Failed to generate valid JSON"}

        except Exception as e:
            return {"error": f"Async processing error: {e}"}

    def generate_ats_optimized_resume_json(
        self, job_description: str, missing_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate an ATS-optimized resume in JSON format (synchronous)."""
        if not self.resume:
            return {"error": "Resume not provided"}

        try:
            score_results = {}
            provided_missing_skills = missing_skills if missing_skills is not None else None

            if provided_missing_skills is None and self.ats_scorer:
                score_results = self.ats_scorer.compute_match_score(self.resume, job_description)
                provided_missing_skills = score_results.get("missing_skills", [])

            self._setup_chain(provided_missing_skills)

            result = self.chain.invoke({"job_description": job_description, "resume": self.resume})
            content = result.content if hasattr(result, "content") else result
            
            json_match = re.search(r"(\{[\s\S]*\})", content)
            if json_match:
                json_result = json.loads(json_match.group(1))
                
                # Merge initial score
                if score_results:
                    if "ats_metrics" not in json_result:
                        json_result["ats_metrics"] = {}
                    json_result["ats_metrics"]["initial_score"] = score_results.get("final_score", 0)
                
                return json_result
            return {"error": "JSON not found"}
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    pass
