
from langchain_core.prompts import PromptTemplate
from src.llm.llm_manager import AIAdapter
from loguru import logger
import yaml

class CoverLetterGenerator:
    def __init__(self, ai_adapter: AIAdapter):
        self.ai_adapter = ai_adapter

    def generate_cover_letter(self, job_description: str, resume_path: str = "data_folder/plain_text_resume.yaml") -> str:
        """Generates a professional cover letter."""
        logger.info("Generating cover letter...")

        resume_content = ""
        try:
            with open(resume_path, "r") as f:
                resume_data = yaml.safe_load(f)
                resume_content = yaml.dump(resume_data)
        except Exception as e:
            logger.error(f"Could not load resume data: {e}")
            return "Error: Could not load resume data."

        prompt = f"""
            You are a professional career coach and expert copywriter.
            Draft a highly professional, engaging, and tailored cover letter for the following job description,
            using the candidate's resume information.

            The cover letter should:
            1. Be professional and polite.
            2. Highlight relevant skills and experiences from the resume that match the job description.
            3. Express enthusiasm for the role and the company.
            4. Be concise (max 300-400 words).
            5. Have placeholders for [Hiring Manager Name] if not known.

            Resume:
            {resume_content}

            Job Description:
            {job_description}

            Cover Letter:
            """

        response = self.ai_adapter.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        return content.strip()
