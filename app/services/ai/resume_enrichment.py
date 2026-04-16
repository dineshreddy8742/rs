"""Resume Enrichment Wizard - Analyzes weak bullets, asks questions, generates improvements."""

import json
import re
from typing import List, Dict, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.core.config import settings
from app.utils.token_tracker import TokenTracker


class WeakDescription(BaseModel):
    """A weak resume description that needs improvement."""
    section: str = Field(description="Which section: experience, project, or education")
    index: int = Field(description="Index of the item in that section")
    original_text: str = Field(description="The original weak description text")
    issue: str = Field(description="What's wrong: vague, lacks metrics, too generic, missing impact")
    clarifying_question: str = Field(description="A specific question to help the candidate improve this")


class ClarifyingQuestions(BaseModel):
    """Collection of clarifying questions for resume enrichment."""
    items: List[WeakDescription] = Field(description="List of weak descriptions with questions")


class EnhancedDescription(BaseModel):
    """An enhanced/improved resume description."""
    original: str = Field(description="The original text")
    improved: str = Field(description="The improved version with specific metrics and impact")
    changes_made: str = Field(description="Brief description of what was changed and why")


class EnrichmentResult(BaseModel):
    """Result of the enrichment process."""
    enhancements: List[EnhancedDescription] = Field(description="List of enhanced descriptions")


class ResumeEnrichmentWizard:
    """Analyzes resume, finds weak descriptions, asks questions, generates improvements."""

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
            temperature=0.3,
            api_key=self.api_key,
            api_base=self.api_base,
            feature="resume_enrichment",
            user_id=self.user_id
        )

        # Parser for structured output
        self.questions_parser = PydanticOutputParser(pydantic_object=ClarifyingQuestions)
        self.result_parser = PydanticOutputParser(pydantic_object=EnrichmentResult)

        # Prompt to find weak descriptions
        self.find_weak_prompt = PromptTemplate(
            template="""You are an expert resume reviewer. Analyze this resume and identify descriptions that are vague, lack metrics, or are too generic.

RESUME:
{resume_text}

JOB DESCRIPTION (optional, for context):
{job_description}

INSTRUCTIONS:
1. Find 3-6 descriptions that are weak (vague, lack specific metrics, too generic, or missing impact)
2. For each, explain what's wrong and ask ONE specific clarifying question
3. Focus on experience and project descriptions
4. Questions should help the candidate add specific numbers, outcomes, or technologies

Identify at most 6 weak items. Be specific about what's wrong with each.

{format_instructions}""",
            input_variables=["resume_text", "job_description"],
            partial_variables={"format_instructions": self.questions_parser.get_format_instructions()}
        )

        # Prompt to generate enhanced versions from answers
        self.enhance_prompt = PromptTemplate(
            template="""You are an expert resume writer. Rewrite these resume descriptions using the candidate's answers to make them more impactful and specific.

ORIGINAL DESCRIPTIONS AND CANDIDATE ANSWERS:
{qa_pairs}

JOB DESCRIPTION (for keyword alignment):
{job_description}

INSTRUCTIONS:
1. Rewrite each description to be specific, metric-driven, and impactful
2. Use the candidate's answers to add concrete details
3. Start each description with a strong action verb (Led, Built, Created, Designed, etc.)
4. Include numbers, percentages, or scale where possible
5. Keep each description to 1-2 sentences max
6. Do NOT fabricate facts - only use what the candidate provided
7. Make it sound professional but natural

{format_instructions}""",
            input_variables=["qa_pairs", "job_description"],
            partial_variables={"format_instructions": self.result_parser.get_format_instructions()}
        )

        self.find_weak_chain = self.find_weak_prompt | self.llm
        self.enhance_chain = self.enhance_prompt | self.llm

    def find_weak_descriptions(self, resume_text: str, job_description: str = "") -> dict:
        """Find weak descriptions and generate clarifying questions.
        
        Args:
            resume_text: The resume text
            job_description: Optional job description for context
            
        Returns:
            dict with list of WeakDescription items
        """
        try:
            result = self.find_weak_chain.invoke({
                "resume_text": resume_text[:4000],
                "job_description": job_description[:2000]
            })

            content = result.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                items = data.get("items", [])
                return {
                    "items": items,
                    "count": len(items),
                    "status": "success"
                }

            return {"items": [], "count": 0, "status": "success"}
        except Exception as e:
            return {"items": [], "count": 0, "status": "error", "error": str(e)}

    def enhance_descriptions(self, qa_pairs: List[Dict], job_description: str = "") -> dict:
        """Generate enhanced descriptions from candidate's answers.
        
        Args:
            qa_pairs: List of dicts with {original, answer} keys
            job_description: Optional job description for context
            
        Returns:
            dict with enhanced descriptions
        """
        try:
            qa_text = "\n\n".join([
                f"ORIGINAL: {qa['original']}\nCANDIDATE ANSWER: {qa.get('answer', 'No answer provided')}"
                for qa in qa_pairs
            ])

            result = self.enhance_chain.invoke({
                "qa_pairs": qa_text,
                "job_description": job_description[:2000]
            })

            content = result.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                enhancements = data.get("enhancements", [])
                return {
                    "enhancements": enhancements,
                    "count": len(enhancements),
                    "status": "success"
                }

            return {"enhancements": [], "count": 0, "status": "success"}
        except Exception as e:
            return {"enhancements": [], "count": 0, "status": "error", "error": str(e)}

    async def find_weak_descriptions_async(self, resume_text: str, job_description: str = "") -> dict:
        """Async version of find_weak_descriptions."""
        try:
            result = await self.find_weak_chain.ainvoke({
                "resume_text": resume_text[:4000],
                "job_description": job_description[:2000]
            })

            content = result.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                items = data.get("items", [])
                return {"items": items, "count": len(items), "status": "success"}
            return {"items": [], "count": 0, "status": "success"}
        except Exception as e:
            return {"items": [], "count": 0, "status": "error", "error": str(e)}

    async def enhance_description_async(self, qa_pairs: List[Dict], job_description: str = "") -> dict:
        """Async version of enhance_descriptions."""
        try:
            qa_text = "\n\n".join([
                f"ORIGINAL: {qa['original']}\nCANDIDATE ANSWER: {qa.get('answer', 'No answer provided')}"
                for qa in qa_pairs
            ])

            result = await self.enhance_chain.ainvoke({
                "qa_pairs": qa_text,
                "job_description": job_description[:2000]
            })

            content = result.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                enhancements = data.get("enhancements", [])
                return {"enhancements": enhancements, "count": len(enhancements), "status": "success"}
            return {"enhancements": [], "count": 0, "status": "success"}
        except Exception as e:
            return {"enhancements": [], "count": 0, "status": "error", "error": str(e)}
