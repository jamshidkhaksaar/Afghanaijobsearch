
import streamlit as st
import yaml
import os
import shutil
from pathlib import Path
from src.cv_parser import CVParser
from src.cover_letter_generator import CoverLetterGenerator
from src.gmail_agent import GmailAgent
from src.generic_applier import GenericPortalApplier
from src.llm.llm_manager import AIAdapter
from main import ConfigValidator, FileManager, init_browser
from loguru import logger

# Setup Page
st.set_page_config(page_title="AIHawk Job Assistant", page_icon="🦅", layout="wide")

# Paths
DATA_FOLDER = Path("data_folder")
SECRETS_FILE = DATA_FOLDER / "secrets.yaml"
CONFIG_FILE = DATA_FOLDER / "config.yaml"
RESUME_FILE = DATA_FOLDER / "plain_text_resume.yaml"
PDF_RESUME_FILE = DATA_FOLDER / "resume.pdf"

# Ensure data folder exists
if not DATA_FOLDER.exists():
    DATA_FOLDER.mkdir()

# --- Helper Functions ---
def load_secrets():
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_secrets(api_key):
    with open(SECRETS_FILE, 'w') as f:
        yaml.dump({"llm_api_key": api_key}, f)

def get_ai_adapter(api_key):
    try:
        # Load config to get model type
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
        else:
            # Default fallback
            config = {'llm_model_type': 'openai', 'llm_model': 'gpt-4o-mini'}

        return AIAdapter(config, api_key)
    except Exception as e:
        st.error(f"Error initializing AI: {e}")
        return None

# --- UI Components ---

st.title("🦅 AIHawk: Agentic Job Application Assistant")

# Sidebar: Configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    # API Key Management
    secrets = load_secrets()
    api_key = secrets.get('llm_api_key', '')

    new_api_key = st.text_input("OpenAI API Key", value=api_key, type="password")
    if new_api_key != api_key:
        save_secrets(new_api_key)
        st.success("API Key saved!")
        api_key = new_api_key

    st.divider()

    # Search Settings Preview
    st.subheader("Current Search Criteria")
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
            st.write(f"**Locations:** {', '.join(config.get('locations', []))}")
            st.write(f"**Positions:** {', '.join(config.get('positions', []))}")
    else:
        st.warning("Config file not found.")

# Main Content Tabs
tab_resume, tab_cover_letter, tab_email, tab_portal = st.tabs([
    "📄 Resume Manager",
    "✍️ Cover Letter",
    "📧 Apply via Email",
    "🌐 Apply via Portal"
])

# Tab 1: Resume Manager
with tab_resume:
    st.header("Manage Your CV")
    st.write("Upload your PDF resume. AIHawk will read, parse, and remember it for future applications.")

    uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")

    if uploaded_file is not None:
        if st.button("Process & Save Resume"):
            if not api_key:
                st.error("Please set your API Key in the sidebar first.")
            else:
                with st.spinner("Reading and parsing resume..."):
                    try:
                        # Save PDF temporarily
                        temp_path = DATA_FOLDER / "temp_resume.pdf"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        # Initialize AI
                        adapter = get_ai_adapter(api_key)
                        parser = CVParser(adapter)

                        # Parse
                        text = parser.extract_text_from_pdf(str(temp_path))
                        yaml_content = parser.parse_cv_to_yaml_structure(text)
                        parser.save_to_yaml(yaml_content)

                        # Save final PDF
                        shutil.copy(temp_path, PDF_RESUME_FILE)
                        os.remove(temp_path)

                        st.success("Resume processed and saved successfully!")
                        st.balloons()

                        # Show parsed data
                        with st.expander("View Parsed Data"):
                            st.code(yaml_content, language='yaml')

                    except Exception as e:
                        st.error(f"Error processing resume: {e}")

    elif PDF_RESUME_FILE.exists():
        st.info("A resume is currently saved.")
        with open(PDF_RESUME_FILE, "rb") as pdf_file:
            st.download_button(label="Download Current Resume", data=pdf_file, file_name="resume.pdf", mime="application/pdf")

# Tab 2: Cover Letter
with tab_cover_letter:
    st.header("Draft a Cover Letter")

    job_desc = st.text_area("Paste the Job Description here", height=200)

    if st.button("Generate Draft"):
        if not api_key:
            st.error("Please set your API Key in the sidebar.")
        elif not job_desc:
            st.warning("Please enter a job description.")
        else:
            with st.spinner("Drafting your letter..."):
                adapter = get_ai_adapter(api_key)
                generator = CoverLetterGenerator(adapter)
                draft = generator.generate_cover_letter(job_desc)
                st.session_state['current_cover_letter'] = draft

    if 'current_cover_letter' in st.session_state:
        st.subheader("Your Draft:")
        edited_letter = st.text_area("Edit your letter", value=st.session_state['current_cover_letter'], height=300)
        st.session_state['current_cover_letter'] = edited_letter # Update state with edits

# Tab 3: Apply via Email
with tab_email:
    st.header("Apply via Email")

    col1, col2 = st.columns(2)
    with col1:
        recruiter_email = st.text_input("Recruiter's Email")
        subject_line = st.text_input("Email Subject", value="Job Application")
    with col2:
        gmail_user = st.text_input("Your Gmail Address")
        gmail_pass = st.text_input("Gmail App Password", type="password")

    # Use cover letter from Tab 2 if available
    default_body = st.session_state.get('current_cover_letter', "")
    email_body = st.text_area("Email Body", value=default_body, height=300, help="You can generate this in the Cover Letter tab first.")

    attach_resume = st.checkbox("Attach Saved Resume (PDF)", value=True)

    if st.button("Send Application"):
        if not all([recruiter_email, gmail_user, gmail_pass, email_body]):
            st.error("Missing required fields.")
        else:
            with st.spinner("Sending email..."):
                try:
                    agent = GmailAgent(gmail_user, gmail_pass)
                    attachment = str(PDF_RESUME_FILE) if (attach_resume and PDF_RESUME_FILE.exists()) else None

                    agent.send_email(
                        to_email=recruiter_email,
                        subject=subject_line,
                        body=email_body,
                        attachment_path=attachment
                    )
                    st.success(f"Application sent to {recruiter_email}!")
                except Exception as e:
                    st.error(f"Failed to send email: {e}")

# Tab 4: Apply via Portal
with tab_portal:
    st.header("Automated Portal Applier")
    st.write("Enter a job application URL. AIHawk will launch a browser, analyze the form, and attempt to fill it using your saved resume data.")

    portal_url = st.text_input("Job Portal URL")

    if st.button("Launch Agent"):
        if not api_key:
            st.error("Please set your API Key.")
        elif not portal_url:
            st.warning("Please enter a URL.")
        elif not RESUME_FILE.exists():
            st.error("No resume data found. Please go to the Resume Manager tab first.")
        else:
            status_text = st.empty()
            status_text.info("Initializing Agent...")

            try:
                # Load Resume Data
                with open(RESUME_FILE, "r") as f:
                    resume_data = yaml.safe_load(f)

                # Flatten Data (Logic copied/adapted from agentic_main.py)
                flat_resume_data = {}
                # Personal Info
                if 'personal_information' in resume_data:
                    for k, v in resume_data['personal_information'].items():
                        flat_resume_data[f"personal_information.{k}"] = v

                # Education
                if 'education_details' in resume_data and isinstance(resume_data['education_details'], list) and len(resume_data['education_details']) > 0:
                    edu = resume_data['education_details'][0]
                    for k, v in edu.items():
                        if isinstance(v, (str, int, float)):
                            flat_resume_data[f"education.{k}"] = v

                # Experience
                if 'experience_details' in resume_data and isinstance(resume_data['experience_details'], list) and len(resume_data['experience_details']) > 0:
                    exp = resume_data['experience_details'][0]
                    for k, v in exp.items():
                        if isinstance(v, (str, int, float)):
                            flat_resume_data[f"experience.{k}"] = v

                # Projects
                if 'projects' in resume_data and isinstance(resume_data['projects'], list) and len(resume_data['projects']) > 0:
                     proj = resume_data['projects'][0]
                     for k, v in proj.items():
                         flat_resume_data[f"project.{k}"] = v

                if 'languages' in resume_data:
                    flat_resume_data['languages'] = ", ".join([l.get('language', '') for l in resume_data['languages']])

                if 'interests' in resume_data:
                    flat_resume_data['interests'] = ", ".join(resume_data['interests'])

                # Launch
                status_text.info(f"Launching browser for {portal_url}...")

                adapter = get_ai_adapter(api_key)
                driver = init_browser() # This comes from main.py
                applier = GenericPortalApplier(driver, adapter, flat_resume_data)

                applier.apply(portal_url)

                status_text.success("Agent finished processing the page(s). Please check the browser window to verify and submit.")

            except Exception as e:
                status_text.error(f"Agent failed: {e}")
