import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
CUSTOMERS_DIR = BASE_DIR / "customers"
TEMPLATES_DIR = BASE_DIR / "templates"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("MSP_MODEL", "claude-sonnet-4-6")
DEFAULT_TEMPLATE = os.getenv("MSP_DEFAULT_TEMPLATE", "default")
