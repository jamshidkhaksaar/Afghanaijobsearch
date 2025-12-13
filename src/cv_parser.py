
import yaml
import os
from pdfminer.high_level import extract_text
from src.llm.llm_manager import AIAdapter
from loguru import logger

class CVParser:
    def __init__(self, ai_adapter: AIAdapter):
        self.ai_adapter = ai_adapter

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extracts raw text from a PDF file."""
        logger.info(f"Extracting text from {pdf_path}")
        try:
            text = extract_text(pdf_path)
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise

    def parse_cv_to_yaml_structure(self, cv_text: str) -> str:
        """Uses LLM to parse raw CV text into the expected YAML structure."""
        logger.info("Parsing CV text using LLM...")

        # Load the example structure to guide the LLM
        example_structure = ""
        try:
            # Try main data folder first, then example
            if os.path.exists("data_folder/plain_text_resume.yaml"):
                 with open("data_folder/plain_text_resume.yaml", "r") as f:
                    example_structure = f.read()
            elif os.path.exists("data_folder_example/plain_text_resume.yaml"):
                with open("data_folder_example/plain_text_resume.yaml", "r") as f:
                    example_structure = f.read()
        except Exception as e:
            logger.warning(f"Could not load example structure: {e}")

        prompt = f"""
            You are an expert resume parser. I will provide you with the raw text of a resume and an example YAML structure.
            Your task is to extract information from the resume and populate the YAML structure accordingly.

            Return ONLY the valid YAML string. Do not include markdown code blocks (```yaml ... ```).

            Example YAML Structure:
            {example_structure}

            Raw Resume Text:
            {cv_text}

            Parsed YAML:
            """

        response = self.ai_adapter.invoke(prompt)

        # Cleanup response if it contains markdown
        content = response.content if hasattr(response, 'content') else str(response)
        if "```yaml" in content:
            content = content.split("```yaml")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return content.strip()

    def save_to_yaml(self, yaml_content: str, output_path: str = "data_folder/plain_text_resume.yaml"):
        """Saves the parsed YAML content to a file."""
        logger.info(f"Saving parsed CV to {output_path}")
        try:
            # Validate YAML before saving
            parsed_data = yaml.safe_load(yaml_content)
            with open(output_path, "w", encoding='utf-8') as f:
                yaml.dump(parsed_data, f, allow_unicode=True, sort_keys=False)
            logger.success("CV saved successfully.")
        except yaml.YAMLError as e:
            logger.error(f"Generated content is not valid YAML: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to save YAML: {e}")
            raise
