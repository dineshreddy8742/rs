"""Cover Letter Generation Service using LLM."""

import os
from langchain_core.prompts import PromptTemplate
from app.core.config import settings
from app.utils.token_tracker import TokenTracker


class CoverLetterGenerator:
    """Generates tailored cover letters from resume + job description."""

    def __init__(self, model_name=None, api_key=None, api_base=None, user_id=None):
        self.api_key = api_key or (settings.API_KEYS[0] if hasattr(settings, 'API_KEYS') and settings.API_KEYS else None)
        self.api_base = api_base or settings.API_BASE
        self.model_name = model_name or settings.MODEL_NAME
        self.user_id = user_id

        if not self.api_key:
            raise ValueError("An LLM API key is required.")
        if not self.api_base:
            raise ValueError("An LLM API base is required.")
        if not self.model_name:
            raise ValueError("An LLM model name is required.")

        self.llm = TokenTracker.get_tracked_langchain_llm(
            model_name=self.model_name,
            temperature=0.7,
            api_key=self.api_key,
            api_base=self.api_base,
            feature="cover_letter_generation",
            user_id=self.user_id
        )

        self.prompt = PromptTemplate(
            template="""You are an expert career coach and professional writer.
Write a compelling, personalized cover letter for the following candidate applying to this job.

CANDIDATE RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

JOB TITLE: {job_title}

INSTRUCTIONS:
1. Write a professional cover letter (3-4 paragraphs, ~300-400 words)
2. **Opening**: State the specific role, express enthusiasm, and give a compelling hook
3. **Body Paragraph 1**: Connect the candidate's most relevant experience to the job's core requirements
4. **Body Paragraph 2**: Highlight 2-3 specific achievements/skills that match the job description
5. **Closing**: Reiterate interest, express readiness for an interview, and end professionally
6. Use a warm, confident, and professional tone
7. Be specific - reference actual details from the resume, not generic statements
8. Do NOT use AI-sounding phrases like "I am writing to express", "cutting-edge", "leverage", "seamless"
9. Make it sound like a real human wrote it - natural, not robotic
10. Use the candidate's actual name and the company name if available

FORMAT:
- Start with "Dear Hiring Manager," (or company name if available)
- End with "Sincerely, [Candidate Name]"
- Use proper paragraph breaks
- No bullet points or lists - this is a letter, not a resume

Write the cover letter now.""",
            input_variables=["resume_text", "job_description", "job_title"]
        )

        self.chain = self.prompt | self.llm

    def generate(self, resume_text: str, job_description: str, job_title: str = "") -> dict:
        """Generate a cover letter.
        
        Args:
            resume_text: The candidate's resume text
            job_description: The target job description
            job_title: The target job title
            
        Returns:
            dict with cover_letter text
        """
        try:
            result = self.chain.invoke({
                "resume_text": resume_text[:3000],  # Limit context
                "job_description": job_description[:3000],
                "job_title": job_title or "the position"
            })

            cover_letter = result.content.strip()

            return {
                "cover_letter": cover_letter,
                "word_count": len(cover_letter.split()),
                "status": "success"
            }
        except Exception as e:
            return {
                "cover_letter": "",
                "word_count": 0,
                "status": "error",
                "error": str(e)
            }

    async def generate_async(self, resume_text: str, job_description: str, job_title: str = "") -> dict:
        """Generate a cover letter asynchronously."""
        try:
            result = await self.chain.ainvoke({
                "resume_text": resume_text[:3000],
                "job_description": job_description[:3000],
                "job_title": job_title or "the position"
            })

            cover_letter = result.content.strip()

            return {
                "cover_letter": cover_letter,
                "word_count": len(cover_letter.split()),
                "status": "success"
            }
        except Exception as e:
            return {
                "cover_letter": "",
                "word_count": 0,
                "status": "error",
                "error": str(e)
            }
