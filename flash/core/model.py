"""The data FlasH works with: questions and decks, and their JSON form."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Question:
    """One multiple-choice question."""

    text: str
    options: list[str]
    answer: int = 0  # index of the correct option in `options`
    id: str = ""
    explanation: str = ""

    def to_dict(self) -> dict:
        """The question as a JSON-ready dict, in the format of the deck files (``"q"`` holds the text)."""
        d = {"id": self.id, "q": self.text, "options": self.options, "answer": self.answer}
        if self.explanation:
            d["explanation"] = self.explanation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        """Build a question from :meth:`to_dict` output; missing optional fields get their defaults."""
        return cls(
            text=d["q"],
            options=list(d["options"]),
            answer=int(d.get("answer", 0)),
            id=d.get("id", ""),
            explanation=d.get("explanation", ""),
        )


@dataclass
class Deck:
    """A named set of questions imported from one file."""

    id: str
    name: str
    source: str
    kind: str  # "bank" (parsed test bank), "generated" (offline), "ai"
    created: str
    questions: list[Question] = field(default_factory=list)

    def to_dict(self) -> dict:
        """The deck as a JSON-ready dict, as stored in ``decks/<id>.json``."""
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "kind": self.kind,
            "created": self.created,
            "questions": [q.to_dict() for q in self.questions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Deck":
        """Build a deck from :meth:`to_dict` output; tolerates files from older versions."""
        return cls(
            id=d["id"],
            name=d["name"],
            source=d.get("source", ""),
            kind=d.get("kind", "bank"),
            created=d.get("created", ""),
            questions=[Question.from_dict(q) for q in d.get("questions", [])],
        )
