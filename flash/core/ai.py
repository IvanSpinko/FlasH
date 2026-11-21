"""Optional AI question generation with Claude.

Used for plain study text (not ready-made test banks). The heavy work runs on
Anthropic's servers, so a weak PC is fine - only internet and an API key are
needed. Everything else in FlasH works offline.
"""

from __future__ import annotations

import json

from .generator import detect_language, lines_to_text
from .model import Question

DEFAULT_MODEL = "claude-opus-5-5"
MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
# Server-side refusal fallbacks are available for these models.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}

CHUNK_CHARS = 12000

_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
                "required": ["question", "options", "correct_index", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

_PROMPT = {
    "uk": (
        "Ти складаєш тести для студента, який готується до іспиту. На основі наведеного "
        "фрагмента навчального матеріалу створи до {n} тестових питань українською мовою. "
        "Кожне питання має 5 варіантів відповіді, рівно один правильний; неправильні варіанти "
        "мають бути правдоподібними і з тієї ж теми. Питай про ключові факти, визначення, "
        "механізми і причинно-наслідкові зв'язки з тексту, не вигадуй фактів поза текстом. "
        "У полі explanation коротко поясни правильну відповідь."
    ),
    "en": (
        "You write practice tests for a student preparing for an exam. From the study material "
        "below, write up to {n} multiple-choice questions in English. Each question has 5 options "
        "with exactly one correct; wrong options must be plausible and on the same topic. Ask about "
        "key facts, definitions, mechanisms and cause-effect relations stated in the text; do not "
        "invent facts that are not in the text. In explanation, briefly justify the correct answer."
    ),
}


class AIError(Exception):
    """AI generation failed. The message is a short code ("auth", "rate_limit", "network") or the API's error."""

    pass


def is_available() -> bool:
    """True if the ``anthropic`` package is installed, so AI generation can run."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split ``text`` into pieces of at most ``size`` characters at paragraph breaks.

    A single paragraph longer than ``size`` is kept whole.
    """
    chunks, cur, cur_len = [], [], 0
    for para in text.split("\n"):
        if cur_len + len(para) > size and cur:
            chunks.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(para)
        cur_len += len(para) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def generate_questions(
    lines: list[str],
    api_key: str,
    model: str = DEFAULT_MODEL,
    per_chunk: int = 10,
    progress=None,
    cancelled=lambda: False,
) -> list[Question]:
    """Make multiple-choice questions from study text with Claude, one request per chunk of text.

    The prompt follows the text's language (Ukrainian or English). Questions with fewer than three
    options or a bad answer index are dropped; the correct option is moved to the front.
    ``progress(done, total)`` is called after each chunk and ``cancelled()`` is checked before each one.
    Raises :class:`AIError` if the package is missing or the API fails.
    """
    try:
        import anthropic
    except ImportError as e:
        raise AIError("anthropic package is not installed") from e

    client = anthropic.Anthropic(api_key=api_key or None)
    text = lines_to_text(lines)
    lang = detect_language(text)
    chunks = chunk_text(text)
    questions: list[Question] = []

    for i, chunk in enumerate(chunks):
        if cancelled():
            break
        kwargs = dict(
            model=model,
            max_tokens=16000,
            system=_PROMPT[lang].format(n=per_chunk),
            messages=[{"role": "user", "content": f"<material>\n{chunk}\n</material>"}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
        )
        try:
            if model in _FALLBACK_MODELS:
                response = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                response = client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise AIError("auth") from e
        except anthropic.RateLimitError as e:
            raise AIError("rate_limit") from e
        except anthropic.APIConnectionError as e:
            raise AIError("network") from e
        except anthropic.APIStatusError as e:
            raise AIError(f"API error {e.status_code}: {e.message}") from e

        if response.stop_reason == "refusal":
            if progress:
                progress(i + 1, len(chunks))
            continue
        payload = "".join(b.text for b in response.content if b.type == "text")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            if progress:
                progress(i + 1, len(chunks))
            continue
        for item in data.get("questions", []):
            opts = [o.strip() for o in item.get("options", []) if o.strip()]
            idx = item.get("correct_index", 0)
            if len(opts) < 3 or not (0 <= idx < len(opts)):
                continue
            opts.insert(0, opts.pop(idx))
            questions.append(
                Question(
                    text=item["question"].strip(),
                    options=opts,
                    answer=0,
                    explanation=item.get("explanation", "").strip(),
                )
            )
        if progress:
            progress(i + 1, len(chunks))
    return questions
