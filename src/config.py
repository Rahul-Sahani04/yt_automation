import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

NIM_API_KEY = os.environ["NIM_API_KEY"]
NIM_BASE_URL = os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
NIM_MODEL = os.environ.get("NIM_MODEL", "deepseek-ai/deepseek-v4-flash")

YT_CLIENT_SECRETS_FILE = os.environ.get(
    "YT_CLIENT_SECRETS_FILE", str(BASE_DIR / "client_secret.json")
)
YT_TOKEN_FILE = os.environ.get("YT_TOKEN_FILE", str(BASE_DIR / "token.json"))
YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",

    # Edit Videos
    
]

SOURCE_DIR = Path(os.environ.get("SOURCE_DIR", str(BASE_DIR / "incoming")))
UPLOADED_DIR = Path(os.environ.get("UPLOADED_DIR", str(BASE_DIR / "uploaded")))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(BASE_DIR / "work")))

DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "runs.db"))
REPORT_DIR = Path(os.environ.get("REPORT_DIR", str(BASE_DIR / "data" / "reports")))
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", str(BASE_DIR / "src" / "skills")))

for d in (SOURCE_DIR, UPLOADED_DIR, WORK_DIR, REPORT_DIR, SKILLS_DIR):
    d.mkdir(parents=True, exist_ok=True)

