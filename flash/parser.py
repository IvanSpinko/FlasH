"""Parser for ready-made test banks (e.g. "Krok"-style question collections).

Typical layout handled here::

    12. Question text that may wrap
    over several lines?
    Correct answer            <- by convention the first option is correct
    Distractor
    Distractor that wraps
    onto a second line
    Distractor
    Distractor
    <blank line>

Numbering is optional. A correct answer can also be marked explicitly with a
leading/trailing ``*`` or ``+`` (then the position does not matter).
"""
from __future__ import annotations

import re
from collections import Counter

from .model import Question

_NUMBER_PREFIX = re.compile(r"^\s*(?:№\s*)?\d{1,4}\s*[.)]\s*")
_OPTION_LETTER = re.compile(r"^\s*[A-Ea-eА-Да-д]\s*[.)]\s+")
_MARK = re.compile(r"^\s*[*+]\s*|\s*[*+]\s*$")
_STEM_END = ("?", ":", "…")

MAX_OPTIONS = 8
MIN_OPTIONS = 3


def _is_continuation(prev: str, cur: str) -> bool:
    """True if ``cur`` is a wrapped tail of ``prev`` rather than a new item."""
    if not cur:
        return False
    stripped = cur.lstrip("\"'«“„ ")
    first = stripped[:1] or cur[0]
    if prev.endswith(("-", "/", ",", "(", "+", "–")) and not prev.endswith(" -"):
        return True
    if first.islower() and first.isalpha():
        return True
    return first in "),;/"


def _join(prev: str, cur: str) -> str:
    # "Гіпоксантинфосфорибозилтрансфера" + "зи" -> one word when the break
    # happened inside a word (no trailing space in the source).
    if prev.endswith("-") and cur[:1].islower():
        return prev + cur
    if prev.endswith(("/", "(")):
        return prev + cur
    if cur[:1].islower() and len(prev) > 0 and prev[-1].isalpha() and len(cur) <= 4:
        return prev + cur
    return f"{prev} {cur}"


def merge_wrapped(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if out and _is_continuation(out[-1], line):
            out[-1] = _join(out[-1], line)
        else:
            out.append(line)
    return out


_INCOMPLETE = -1  # stem found but its options continue in the next block


def _find_stem_end(lines: list[str]) -> int | None:
    """Index of the last stem line (options follow it).

    Returns ``_INCOMPLETE`` when the question mark is there but fewer than
    MIN_OPTIONS lines follow it (the rest is on the next page), and ``None``
    when no stem end can be recognised.
    """
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].rstrip().endswith("?"):
            return i if len(lines) - i - 1 >= MIN_OPTIONS else _INCOMPLETE
    longest = max((len(l) for l in lines), default=0)
    for i in range(len(lines) - 1 - MIN_OPTIONS, -1, -1):
        if lines[i].rstrip().endswith((":", "…")):
            nxt = lines[i + 1]
            # "При бронхоскопії: слизова оболонка ..." - a colon inside the
            # stem is followed by more full-width prose, not by a short option.
            if nxt[:1].islower() and len(nxt) >= max(25, 0.75 * longest):
                continue
            return i
    return None


_JOINERS = {
    "і", "i", "й", "та", "в", "у", "з", "із", "зі", "до", "на", "від", "для", "при", "по",
    "без", "або", "чи", "що", "and", "or", "of", "the", "a", "an", "to", "in", "with",
    "for", "by", "on", "и", "с", "к", "от", "при",
}


def _join_score(prev: str, cur: str, longest: int) -> float:
    score = 0.0
    if cur[:1].islower():
        score += 3
    if prev.endswith(("-", "/", ",", "(", "+")):
        score += 3
    last_word = prev.rsplit(" ", 1)[-1].lower()
    if last_word in _JOINERS:
        score += 3
    words = len(cur.split())
    score += 1.5 if words == 1 else (0.8 if words == 2 else 0)
    score += len(prev) / max(longest, 1)  # a full-width line is likely wrapped
    if prev.endswith((".", ")", "!")):
        score -= 2
    return score


def _split_options(raw: list[str], expected: int) -> list[str]:
    if len(raw) <= expected:
        return raw
    # Each item keeps its raw line segments so pairs are scored on the lines
    # that actually touch (the last line of one item, the first of the next).
    items: list[list[str]] = []
    for line in raw:
        if items and _is_continuation(items[-1][-1], line):
            items[-1].append(line)
        else:
            items.append([line])
    longest = max(len(l) for l in raw)
    # Still too many lines: wrapped options whose tail starts with a capital
    # ("... фактора" / "Касла"). Join the most likely pairs until it fits.
    while len(items) > expected:
        def score(j: int) -> float:
            s = _join_score(items[j - 1][-1], items[j][0], longest)
            return s - 1.5 * (len(items[j - 1]) - 1 + len(items[j]) - 1)

        k = max(range(1, len(items)), key=score)
        items[k - 1 : k + 1] = [items[k - 1] + items[k]]

    out = []
    for segs in items:
        text = segs[0]
        for seg in segs[1:]:
            text = _join(text, seg)
        out.append(text)
    return out


def _strip_option_letters(options: list[str]) -> list[str]:
    if all(_OPTION_LETTER.match(o) for o in options):
        return [_OPTION_LETTER.sub("", o, count=1) for o in options]
    return options


_BULLET = re.compile(r"^[-‐‑‒–—―•·▪●]+\s*(?=\w)")
MAX_OPTION_LEN = 250


def _clean_option(text: str) -> str:
    return _BULLET.sub("", text.strip()).rstrip(";").strip()


def try_parse(lines: list[str], expected: int = 5) -> Question | None:
    lines = [l for l in lines if l]
    if len(lines) < 1 + MIN_OPTIONS:
        return None
    lines = list(lines)
    lines[0] = _NUMBER_PREFIX.sub("", lines[0], count=1)

    end = _find_stem_end(lines)
    if end == _INCOMPLETE:
        return None
    if end is not None:
        stem_lines, raw_opts = lines[: end + 1], lines[end + 1:]
        options = _split_options(raw_opts, expected)
    else:
        # No "?" / ":" - assume the last `expected` logical lines are options.
        logical = merge_wrapped(lines)
        if len(logical) < expected + 1:
            return None
        stem_lines, options = logical[:-expected], logical[-expected:]

    if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
        return None
    stem = " ".join(stem_lines).strip()
    if len(stem) < 8:
        return None

    options = _strip_option_letters([_clean_option(o) for o in options])
    correct = 0
    marked = [i for i, o in enumerate(options) if _MARK.search(o)]
    if len(marked) == 1:
        correct = marked[0]
    options = [_MARK.sub("", o).strip() for o in options]
    if any(not o or len(o) > MAX_OPTION_LEN for o in options) or len(set(options)) < len(options) - 1:
        return None
    if correct != 0:
        options.insert(0, options.pop(correct))
    return Question(text=stem, options=options, answer=0)


def _blocks(lines: list[str]) -> list[list[str]]:
    blocks, cur = [], []
    for line in lines:
        if line:
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


def _split_numbered(block: list[str]) -> list[list[str]]:
    """Split a block that holds several numbered questions without blank lines."""
    parts, cur = [], []
    for line in block:
        if _NUMBER_PREFIX.match(line) and cur:
            parts.append(cur)
            cur = []
        cur.append(line)
    if cur:
        parts.append(cur)
    return parts


def parse_question_bank(lines: list[str], expected: int | None = None) -> list[Question]:
    blocks = [p for b in _blocks(lines) for p in _split_numbered(b)]
    if expected is None:
        expected = _guess_option_count(blocks)

    questions: list[Question] = []
    pending: list[str] = []
    for block in blocks:
        candidate = pending + block
        q = try_parse(candidate, expected)
        if q is not None:
            questions.append(q)
            pending = []
            continue
        # A page break can split a question: options that spilled onto the next
        # page arrive as a stem-less fragment. Attach them to the previous question.
        if (
            not pending
            and questions
            and len(questions[-1].options) < expected
            and not _NUMBER_PREFIX.match(block[0])
            and not any(l.endswith("?") for l in block)
        ):
            prev = questions[-1]
            extra = _split_options(merge_wrapped(block), expected - len(prev.options))
            if len(prev.options) + len(extra) <= expected:
                prev.options.extend(extra)
                continue
        pending = candidate if len(candidate) < 60 else []
    return questions


def _guess_option_count(blocks: list[list[str]]) -> int:
    counts = Counter()
    for b in blocks:
        end = _find_stem_end(b)
        if end is not None and end != _INCOMPLETE:
            n = len(b) - end - 1
            if MIN_OPTIONS <= n <= MAX_OPTIONS:
                counts[n] += 1
    return counts.most_common(1)[0][0] if counts else 5


def looks_like_question_bank(lines: list[str], questions: list[Question]) -> bool:
    if len(questions) < 3:
        return False
    used = sum(1 + len(q.options) for q in questions)
    non_empty = sum(1 for l in lines if l)
    return used / max(non_empty, 1) > 0.35
