import logging
from pathlib import Path
from openai import OpenAI

from . import config
from .retry import retry

logger = logging.getLogger(__name__)

_client = OpenAI(base_url=config.NIM_BASE_URL, api_key=config.NIM_API_KEY)
_skills_cache: str | None = None


def load_skills(skills_dir: Path | None = None, force_reload: bool = False) -> str:
    """Load skill instructions from .md files in skills_dir.

    Parses markdown files in the skills folder (e.g. SKILL.md), stripping frontmatter if present.
    Caches loaded skills unless force_reload is True.
    """
    global _skills_cache
    if _skills_cache is not None and not force_reload:
        return _skills_cache

    target_dir = skills_dir or config.SKILLS_DIR
    if not target_dir.exists():
        logger.warning("Skills directory %s does not exist.", target_dir)
        _skills_cache = ""
        return _skills_cache

    skill_files = list(target_dir.rglob("*.md"))
    if not skill_files:
        logger.info("No skill (.md) files found in %s", target_dir)
        _skills_cache = ""
        return _skills_cache

    skills_content = []
    for file_path in sorted(skill_files):
        try:
            text = file_path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    text = parts[2].strip()
            skills_content.append(text)
            try:
                rel_path = file_path.relative_to(config.BASE_DIR)
            except ValueError:
                rel_path = file_path
            logger.info("Loaded skill from %s", rel_path)
        except Exception as e:
            logger.warning("Failed to read skill file %s: %s", file_path, e)

    _skills_cache = "\n\n---\n\n".join(skills_content)
    logger.info("Loaded %d skill file(s) into NIM client.", len(skills_content))
    return _skills_cache


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
    skills = load_skills()
    messages = []
    if skills:
        messages.append(
            {
                "role": "system",
                "content": (
                    "You are an AI assistant producing YouTube video metadata. "
                    "You MUST strictly follow the following skill guidelines and rules:\n\n"
                    f"{skills}"
                ),
            }
        )
    messages.append({"role": "user", "content": prompt})

    response = _client.chat.completions.create(
        model=config.NIM_MODEL,
        messages=messages,
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
