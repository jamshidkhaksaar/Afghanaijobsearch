
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from src.llm.llm_manager import AIAdapter
from loguru import logger
import time
import json

class GenericPortalApplier:
    def __init__(self, driver: webdriver.Chrome, ai_adapter: AIAdapter, resume_data: dict):
        self.driver = driver
        self.ai_adapter = ai_adapter
        self.resume_data = resume_data

    def apply(self, url: str):
        """Attempts to apply to a job on a generic portal."""
        logger.info(f"Navigating to {url}")
        self.driver.get(url)
        time.sleep(5) # Wait for load

        # Iterate through pages (simple heuristic)
        max_pages = 5
        for page in range(max_pages):
            logger.info(f"Processing page {page + 1}...")
            if self.process_page():
                logger.info("Application seemingly submitted or finished.")
                break

            # Try to go to next page
            if not self.go_to_next_page():
                logger.info("No next page found. Stopping.")
                break
            time.sleep(3)

    def process_page(self) -> bool:
        """
        Analyzes and fills the current page.
        Returns True if it thinks it submitted the application.
        """
        # 1. Analyze inputs, selects, textareas
        elements_info = []
        valid_elements = []

        # Find Inputs
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(inputs):
            if inp.get_attribute("type") in ["hidden", "submit", "button", "image", "reset"]:
                continue
            if not inp.is_displayed():
                continue

            info = {
                "tag": "input",
                "index": len(valid_elements),
                "type": inp.get_attribute("type"),
                "name": inp.get_attribute("name"),
                "id": inp.get_attribute("id"),
                "placeholder": inp.get_attribute("placeholder")
            }
            # Label heuristic
            try:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{inp.get_attribute('id')}']")
                if labels:
                    info["label"] = labels[0].text
            except: pass

            elements_info.append(info)
            valid_elements.append(inp)

        # Find Textareas
        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
        for ta in textareas:
            if not ta.is_displayed(): continue
            info = {
                "tag": "textarea",
                "index": len(valid_elements),
                "name": ta.get_attribute("name"),
                "id": ta.get_attribute("id")
            }
            try:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{ta.get_attribute('id')}']")
                if labels:
                    info["label"] = labels[0].text
            except: pass
            elements_info.append(info)
            valid_elements.append(ta)

        # Find Selects
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        for sel in selects:
            if not sel.is_displayed(): continue
            info = {
                "tag": "select",
                "index": len(valid_elements),
                "name": sel.get_attribute("name"),
                "id": sel.get_attribute("id"),
                "options": [o.text for o in sel.find_elements(By.TAG_NAME, "option")[:10]] # limit options
            }
            try:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{sel.get_attribute('id')}']")
                if labels:
                    info["label"] = labels[0].text
            except: pass
            elements_info.append(info)
            valid_elements.append(sel)

        if not elements_info:
            logger.info("No fillable fields found on this page.")
            return False

        # 2. LLM Mapping
        prompt = f"""
        I have a web form with these fields:
        {json.dumps(elements_info, indent=2)}

        My resume data keys are: {list(self.resume_data.keys())}

        Return a JSON object mapping the field "index" (string) to the resume data key.
        Example: {{"0": "personal_information.name", "2": "education.degree"}}
        Only map confident matches.
        """

        try:
            response = self.ai_adapter.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            mapping = json.loads(content.strip())
        except Exception as e:
            logger.error(f"LLM Mapping failed: {e}")
            mapping = {}

        # 3. Fill Fields
        for idx_str, key in mapping.items():
            try:
                idx = int(idx_str)
                if 0 <= idx < len(valid_elements):
                    element = valid_elements[idx]
                    tag = elements_info[idx]["tag"]
                    value = self.resume_data.get(key)

                    if not value: continue

                    if tag in ["input", "textarea"]:
                        element.clear()
                        element.send_keys(str(value))
                    elif tag == "select":
                        Select(element).select_by_visible_text(str(value)) # Simplified
            except Exception as e:
                logger.warning(f"Failed to fill field {idx_str}: {e}")

        # 4. Check for Submit
        # Heuristic: Button with text "Submit", "Apply", "Complete"
        buttons = self.driver.find_elements(By.TAG_NAME, "button") + \
                  self.driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")

        for btn in buttons:
            try:
                text = btn.text.lower() if btn.tag_name == "button" else btn.get_attribute("value").lower()
                if any(x in text for x in ["submit", "apply", "complete application", "send"]):
                    logger.info(f"Found submit button: {text}")
                    # btn.click() # Uncomment to actually submit. For safety in this demo, we might skip or prompt.
                    # For agentic request, we should click.
                    btn.click()
                    return True
            except: pass

        return False

    def go_to_next_page(self) -> bool:
        """Finds and clicks a Next button."""
        buttons = self.driver.find_elements(By.TAG_NAME, "button") + \
                  self.driver.find_elements(By.TAG_NAME, "a")

        for btn in buttons:
            try:
                text = btn.text.lower()
                if "next" in text or "continue" in text or ">" in text:
                    logger.info(f"Found next button: {text}")
                    btn.click()
                    return True
            except: pass
        return False
