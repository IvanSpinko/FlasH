"""Offline question generator for plain study text (lecture notes, textbooks).

Works without internet or a GPU, so it runs on any machine. Two kinds of
questions are produced:

* definition questions - from sentences like "X — це Y" / "X is a Y":
  "What is X?" with the right definition among definitions of other terms;
* fill-in-the-blank (cloze) questions - a key term is removed from a sentence
  and must be picked among similar terms from the same document.

Quality is lower than an AI generator, but it is instant and free.
"""

from __future__ import annotations

import random
import re
from collections import Counter

from .model import Question

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЇІЄҐ0-9«\"(])")
_WORD = re.compile(r"[A-Za-zА-Яа-яЇїІіЄєҐґ'’][A-Za-zА-Яа-яЇїІіЄєҐґ'’\-]*[A-Za-zА-Яа-яЇїІіЄєҐґ]")

_DEFINITION = re.compile(
    r"^(?P<term>[^,;:()]{2,60}?)\s*(?:[—–-]\s*(?:це|this is)\s+|\s[—–]\s+|\s+(?:називається|називають|є|is an?|are|refers to|means)\s+)(?P<defn>.{12,220})$",
    re.IGNORECASE,
)

_STOP = set(
    """
    і й та а але або чи що як це той ця цей ці які який яка яке якщо коли де для при по на в у з із зі до від
    за під над про без між через його її їх він вона воно вони ми ви ти я не ні так також тому може можуть
    бути було були буде є був була більш менше дуже лише тільки ще вже після перед може під час них ними
    the a an of and or to in on for with by is are was were be been being this that these those it its as at
    from which who whom what when where why how not no can may also than then there their they he she we you
    """.split()
)

TEMPLATES = {
    "uk": {
        "what_is": "Що таке «{term}»?",
        "cloze": "Заповніть пропуск: {sentence}",
    },
    "en": {
        "what_is": "What is “{term}”?",
        "cloze": "Fill in the blank: {sentence}",
    },
}

BLANK = "_____"


def detect_language(text: str) -> str:
    cyr = sum(1 for c in text[:20000] if "а" <= c.lower() <= "я" or c in "іїєґІЇЄҐ")
    lat = sum(1 for c in text[:20000] if "a" <= c.lower() <= "z")
    return "uk" if cyr >= lat else "en"


def lines_to_text(lines: list[str]) -> str:
    """Join wrapped lines back into paragraphs."""
    paras, cur = [], []
    for line in lines:
        if not line:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if cur and cur[-1].endswith("-") and line[:1].islower():
            cur[-1] = cur[-1][:-1] + line
        else:
            cur.append(line)
    if cur:
        paras.append(" ".join(cur))
    return "\n".join(paras)


def split_sentences(text: str) -> list[str]:
    out = []
    for para in text.split("\n"):
        for s in _SENT_SPLIT.split(para):
            s = s.strip()
            if 30 <= len(s) <= 300:
                out.append(s)
    return out


def _match_case(word: str, like: str) -> str:
    """Give a distractor the same first-letter case as the right answer."""
    if like[:1].isupper():
        return word[:1].upper() + word[1:]
    if word[1:2].isupper():  # abbreviation such as "АТФ" - leave as is
        return word
    return word[:1].lower() + word[1:]


def _suffix(word: str, n: int = 2) -> str:
    return word[-n:].lower()


def generate_questions(lines: list[str], limit: int = 300, seed: int | None = None) -> list[Question]:
    rng = random.Random(seed)
    text = lines_to_text(lines)
    lang = detect_language(text)
    tpl = TEMPLATES[lang]
    sentences = split_sentences(text)

    questions: list[Question] = []

    # 1) Definitions.
    defs: list[tuple[str, str]] = []
    for s in sentences:
        m = _DEFINITION.match(s.rstrip("."))
        if m:
            term = m.group("term").strip(' «»"')
            defn = m.group("defn").strip()
            if 1 <= len(term.split()) <= 6 and term.lower() not in _STOP:
                defs.append((term, defn[0].upper() + defn[1:]))
    seen_terms = set()
    unique_defs = []
    for term, defn in defs:
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            unique_defs.append((term, defn))
    if len(unique_defs) >= 4:
        for term, defn in unique_defs:
            others = [d for t, d in unique_defs if t != term]
            options = [defn] + rng.sample(others, min(4, len(others)))
            questions.append(Question(text=tpl["what_is"].format(term=term), options=options, answer=0))

    # 2) Cloze questions on rare, long "key" words.
    words = [w for s in sentences for w in _WORD.findall(s)]
    freq = Counter(w.lower() for w in words)
    vocab = sorted({w for w in words if len(w) >= 6 and w.lower() not in _STOP})
    by_suffix: dict[str, list[str]] = {}
    for w in vocab:
        by_suffix.setdefault(_suffix(w), []).append(w)

    used_sentences = set()
    candidates = sentences[:]
    rng.shuffle(candidates)
    for s in candidates:
        if len(questions) >= limit:
            break
        if s in used_sentences:
            continue
        keys = [w for w in _WORD.findall(s) if len(w) >= 6 and w.lower() not in _STOP and 1 <= freq[w.lower()] <= 6]
        if not keys:
            continue
        # Prefer capitalised terms (names, diseases) and longer words.
        key = max(keys, key=lambda w: (w[0].isupper() and s.find(w) > 0, len(w), -freq[w.lower()]))
        pool = [w for w in by_suffix.get(_suffix(key), []) if w.lower() != key.lower()]
        if len(pool) < 4:
            pool += [w for w in vocab if w.lower() != key.lower() and abs(len(w) - len(key)) <= 3 and w not in pool]
        pool = list({p.lower(): p for p in pool}.values())
        if len(pool) < 3:
            continue
        distractors = [_match_case(d, key) for d in rng.sample(pool, min(4, len(pool)))]
        blanked = re.sub(rf"(?<!\w){re.escape(key)}(?!\w)", BLANK, s, count=1)
        if BLANK not in blanked:
            continue
        questions.append(
            Question(
                text=tpl["cloze"].format(sentence=blanked),
                options=[key] + distractors,
                answer=0,
                explanation=s,
            )
        )
        used_sentences.add(s)

    return questions[:limit]
