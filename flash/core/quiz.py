"""Test session logic (independent from the UI, so it can be unit-tested)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .model import Deck, Question

MODES = ("smart", "random", "ordered", "mistakes", "unseen")


@dataclass
class Item:
    """A question inside a test, with its options in the order shown and the user's choice."""

    question: Question
    order: list[int]  # order[i] = index in question.options shown at position i
    chosen: int | None = None  # displayed position the user picked

    @property
    def options(self) -> list[str]:
        """The answer options in the order they are shown."""
        return [self.question.options[i] for i in self.order]

    @property
    def correct_pos(self) -> int:
        """Where the correct answer is shown (index into :attr:`options`)."""
        return self.order.index(self.question.answer)

    @property
    def is_correct(self) -> bool:
        """True once the user picked the correct answer."""
        return self.chosen is not None and self.chosen == self.correct_pos


def select_questions(
    deck: Deck,
    stats: dict[str, dict],
    mode: str = "smart",
    count: int | None = None,
    start: int = 1,
    end: int | None = None,
    rng: random.Random | None = None,
) -> list[Question]:
    """Pick questions for a test. ``start``/``end`` are 1-based, inclusive."""
    rng = rng or random.Random()
    end = end or len(deck.questions)
    pool = deck.questions[max(start, 1) - 1 : end]

    if mode == "ordered":
        chosen = pool
    elif mode == "mistakes":
        chosen = [q for q in pool if stats.get(q.id, {}).get("wrong", 0) > 0 and stats[q.id]["streak"] < 2]
        rng.shuffle(chosen)
    elif mode == "unseen":
        chosen = [q for q in pool if q.id not in stats]
        rng.shuffle(chosen)
    elif mode == "random":
        chosen = pool[:]
        rng.shuffle(chosen)
    else:  # smart: weak and unseen first, well-known questions last

        def weight(q: Question) -> float:
            s = stats.get(q.id)
            if s is None:
                return 2.0
            w = 1.0 + s["wrong"] / max(s["seen"], 1) * 3 - min(s["streak"], 4) * 0.6
            return max(w, 0.05)

        # Weighted random order (Efraimidis-Spirakis): key = u ** (1 / w).
        chosen = sorted(pool, key=lambda q: rng.random() ** (1.0 / weight(q)), reverse=True)

    if count:
        chosen = chosen[:count]
    return list(chosen)


@dataclass
class Session:
    """One test in progress: the questions, the current position and the answers so far."""

    deck_id: str
    items: list[Item]
    index: int = 0
    finished: bool = field(default=False)

    @classmethod
    def create(cls, deck_id: str, questions: list[Question], shuffle_options: bool = True, rng=None):
        """Start a test on ``questions``, shuffling each question's options unless ``shuffle_options`` is False.

        ``rng`` makes the shuffle repeatable in tests.
        """
        rng = rng or random.Random()
        items = []
        for q in questions:
            order = list(range(len(q.options)))
            if shuffle_options:
                rng.shuffle(order)
            items.append(Item(question=q, order=order))
        return cls(deck_id=deck_id, items=items)

    @property
    def current(self) -> Item | None:
        """The question waiting for an answer, or None when the test is over."""
        return self.items[self.index] if self.index < len(self.items) else None

    def answer(self, position: int) -> bool:
        """Answer the current question with the option shown at ``position``; returns whether it was right.

        Raises ``ValueError`` if there is no open question or it was already answered.
        """
        item = self.current
        if item is None or item.chosen is not None:
            raise ValueError("No open question")
        item.chosen = position
        return item.is_correct

    def next(self) -> Item | None:
        """Move to the next question and return it (None at the end, which also sets :attr:`finished`)."""
        self.index += 1
        if self.index >= len(self.items):
            self.finished = True
        return self.current

    @property
    def answered(self) -> list[Item]:
        """The questions answered so far."""
        return [i for i in self.items if i.chosen is not None]

    @property
    def score(self) -> int:
        """How many questions were answered correctly."""
        return sum(1 for i in self.items if i.is_correct)

    @property
    def mistakes(self) -> list[Item]:
        """The questions answered wrong."""
        return [i for i in self.answered if not i.is_correct]
