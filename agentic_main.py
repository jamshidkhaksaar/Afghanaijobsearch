
import click
import os
from loguru import logger
from src.cv_parser import CVParser
from src.cover_letter_generator import CoverLetterGenerator
from src.gmail_agent import GmailAgent
from src.generic_applier import GenericPortalApplier
from src.llm.llm_manager import AIAdapter
from main import ConfigValidator, FileManager, init_browser
from pathlib import Path
import yaml
import shutil
import json

@click.command()
@click.option('--action', type=click.Choice(['update_cv', 'draft_email', 'apply_email', 'apply_portal']), required=True, help='Action to perform')
@click.option('--cv_path', help='Path to the PDF CV (required for update_cv)')
@click.option('--job_description', help='Job description text (required for draft_email/apply_email)')
@click.option('--recruiter_email', help='Recruiter email (required for apply_email)')
@click.option('--gmail_user', help='Your Gmail address (required for apply_email)')
@click.option('--gmail_password', help='Your Gmail App Password (required for apply_email)')
@click.option('--portal_url', help='URL of the job portal (required for apply_portal)')
def main(action, cv_path, job_description, recruiter_email, gmail_user, gmail_password, portal_url):

    # Initialize LLM
    try:
        data_folder = Path("data_folder")
        secrets_file, config_file, plain_text_resume_file, _ = FileManager.validate_data_folder(data_folder)
        parameters = ConfigValidator.validate_config(config_file)

        # Handle missing/empty key gracefully
        try:
            llm_api_key = ConfigValidator.validate_secrets(secrets_file, parameters.get("llm_model_type"))
        except Exception:
            click.echo("data_folder/secrets.yaml is missing or does not contain a valid API key for your selected llm_model_type.")
            api_key = click.prompt("Please enter your LLM API Key", hide_input=True)
            primary_key_field = ConfigValidator.primary_api_key_field(parameters.get("llm_model_type", ""))
            existing = {}
            if secrets_file.exists():
                with open(secrets_file, "r") as f:
                    existing = yaml.safe_load(f) or {}
            existing[primary_key_field] = api_key
            existing["llm_api_key"] = api_key
            with open(secrets_file, "w") as f:
                yaml.safe_dump(existing, f, sort_keys=False)
            click.echo(f"Saved API key to data_folder/secrets.yaml ({primary_key_field} and llm_api_key).")
            llm_api_key = api_key

        ai_adapter = AIAdapter(parameters, llm_api_key)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return

    if action == 'update_cv':
        if not cv_path:
            click.echo("Error: --cv_path is required for update_cv")
            return
        parser = CVParser(ai_adapter)
        try:
            text = parser.extract_text_from_pdf(cv_path)
            yaml_content = parser.parse_cv_to_yaml_structure(text)
            parser.save_to_yaml(yaml_content)
            # Copy PDF to data folder for attachment
            shutil.copy(cv_path, data_folder / "resume.pdf")
            click.echo("CV updated successfully and saved to data_folder/plain_text_resume.yaml and data_folder/resume.pdf")
        except Exception as e:
            click.echo(f"Error updating CV: {e}")

    elif action == 'draft_email':
        if not job_description:
            click.echo("Error: --job_description is required for draft_email")
            return
        generator = CoverLetterGenerator(ai_adapter)
        cover_letter = generator.generate_cover_letter(job_description)
        click.echo("--- Generated Cover Letter ---")
        click.echo(cover_letter)
        click.echo("------------------------------")

    elif action == 'apply_email':
        if not job_description:
             job_description = click.prompt("Please paste the job description")
        if not recruiter_email:
             recruiter_email = click.prompt("Please enter the recruiter's email")
        if not gmail_user:
             gmail_user = click.prompt("Please enter your Gmail address")
        if not gmail_password:
             gmail_password = click.prompt("Please enter your Gmail App Password", hide_input=True)

        if not all([job_description, recruiter_email, gmail_user, gmail_password]):
            click.echo("Error: Missing required information.")
            return

        generator = CoverLetterGenerator(ai_adapter)
        cover_letter = generator.generate_cover_letter(job_description)

        agent = GmailAgent(gmail_user, gmail_password)
        try:
            attachment = cv_path
            if not attachment and (data_folder / "resume.pdf").exists():
                attachment = str(data_folder / "resume.pdf")

            agent.send_email(
                to_email=recruiter_email,
                subject="Job Application",
                body=cover_letter,
                attachment_path=attachment
            )
            click.echo(f"Application sent to {recruiter_email} with attachment {attachment if attachment else 'None'}")
        except Exception as e:
            click.echo(f"Error sending email: {e}")

    elif action == 'apply_portal':
        if not portal_url:
            portal_url = click.prompt("Please enter the job portal URL")

        driver = None
        try:
            with open(plain_text_resume_file, "r") as f:
                resume_data = yaml.safe_load(f)

            # Flatten resume data for easier mapping
            flat_resume_data = {}
            if 'personal_information' in resume_data:
                for k, v in resume_data['personal_information'].items():
                    flat_resume_data[f"personal_information.{k}"] = v

            if 'education_details' in resume_data and isinstance(resume_data['education_details'], list) and len(resume_data['education_details']) > 0:
                edu = resume_data['education_details'][0]
                for k, v in edu.items():
                    if isinstance(v, (str, int, float)):
                        flat_resume_data[f"education.{k}"] = v

            if 'experience_details' in resume_data and isinstance(resume_data['experience_details'], list) and len(resume_data['experience_details']) > 0:
                exp = resume_data['experience_details'][0]
                for k, v in exp.items():
                    if isinstance(v, (str, int, float)):
                        flat_resume_data[f"experience.{k}"] = v

            if 'projects' in resume_data and isinstance(resume_data['projects'], list) and len(resume_data['projects']) > 0:
                 proj = resume_data['projects'][0]
                 for k, v in proj.items():
                     flat_resume_data[f"project.{k}"] = v

            if 'languages' in resume_data:
                flat_resume_data['languages'] = ", ".join([l.get('language', '') for l in resume_data['languages']])

            if 'interests' in resume_data:
                flat_resume_data['interests'] = ", ".join(resume_data['interests'])

            driver = init_browser()
            applier = GenericPortalApplier(driver, ai_adapter, flat_resume_data)
            applier.apply(portal_url)
            click.echo(f"Application process initiated for {portal_url}")
            click.echo("The browser will remain open for you to verify and complete the application.")
            input("Press Enter to close browser...")
        except Exception as e:
            click.echo(f"Error applying to portal: {e}")
        finally:
            if driver:
                driver.quit()

if __name__ == '__main__':
    main()
