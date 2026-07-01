"""UI configuration for AgentOps Hub Streamlit frontend."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
_s = get_settings()

API_BASE_URL = _s.ui_api_base_url
API_KEY = _s.api_key
API_TIMEOUT_CHAT = 180
API_TIMEOUT_INGEST = 180
API_TIMEOUT_DEFAULT = 15
APP_TITLE = "AgentOps Hub"
APP_SUBTITLE = "Autonomous Multi-Agent Knowledge Worker"
PAGE_ICON = chr(0x1F9E0)
SUPPORTED_FILE_TYPES = ["txt", "md", "pdf", "docx"]
MAX_FILE_SIZE_MB = 50
MAX_MESSAGE_HISTORY = 100
