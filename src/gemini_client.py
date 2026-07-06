import google.generativeai as genai

from . import config
from .retry import retry

genai.configure(api_key=config.GEMINI_API_KEY)

_MODEL = "models/gemini-2.5-flash"

TRANSCRIBE_PROMPT = (
    "Transcribe this audio accurately. Preserve original speech, grammar, and tone. "
    "Format clearly using line breaks. Do not translate."
)


@retry(max_attempts=3)
def transcribe_audio(audio_path: str) -> str:
    model = genai.GenerativeModel(_MODEL)
    audio_file = genai.upload_file(audio_path)
    response = model.generate_content([TRANSCRIBE_PROMPT, audio_file])
    return response.text.strip()
