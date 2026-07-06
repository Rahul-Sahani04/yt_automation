from openai import OpenAI

from . import config
from .retry import retry

_client = OpenAI(base_url=config.NIM_BASE_URL, api_key=config.NIM_API_KEY)

DESCRIPTION_PROMPT = (
    "You are a professional copywriter. Given the transcript below, write a detailed "
    "but concise YouTube video description in paragraphs, first person, confident tone, "
    "with 2-4 emojis and ending in 2-5 relevant hashtags.\n\nTranscript:\n{transcript}"
)

TAGS_PROMPT = (
    "Extract the top 5 trending, SEO-optimized YouTube tags for this video. "
    "Return ONLY the tags, one per line, lowercase, starting with #.\n\nTranscript:\n{transcript}"
)

TITLE_PROMPT = (
    "Write a single short, catchy, SEO-optimized YouTube title (max 100 characters) "
    "for this video. Return ONLY the title, no quotes, no extra text.\n\nTranscript:\n{transcript}"
)


def _complete(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=config.NIM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
        # thinking off: copywriting doesn't need chain-of-thought, saves latency/tokens
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )
    return response.choices[0].message.content.strip()


@retry(max_attempts=3)
def generate_description(transcript: str) -> str:
    return _complete(DESCRIPTION_PROMPT.format(transcript=transcript))


@retry(max_attempts=3)
def generate_tags(transcript: str) -> list[str]:
    text = _complete(TAGS_PROMPT.format(transcript=transcript))
    return [line.strip() for line in text.splitlines() if line.strip()]


@retry(max_attempts=3)
def generate_title(transcript: str) -> str:
    return _complete(TITLE_PROMPT.format(transcript=transcript)).replace("**", "")
