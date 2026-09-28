from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

def test_streamlit_app_initial_render():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    assert len(at.chat_message) >= 1
    assert "GlobalTech HR Automation Agent" in at.chat_message[0].markdown[0].value

def test_streamlit_app_employee_selection():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Change active employee to index 1 (Sarah Lin / EMP-102)
    at.sidebar.selectbox[0].select_index(1).run()
    assert len(at.exception) == 0
    assert len(at.chat_message) >= 1

def test_streamlit_app_demo_button_trigger():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Click Demo 1 (Onboarding Roadmap)
    at.sidebar.button[0].click().run()
    assert len(at.exception) == 0
    # Expect 3 messages: initial assistant, user query, assistant response
    assert len(at.chat_message) >= 3
    last_msg = at.chat_message[-1].markdown[0].value
    assert "EMP-NEW-01" in last_msg or "Jordan Hayes" in last_msg or "Onboarding" in last_msg
