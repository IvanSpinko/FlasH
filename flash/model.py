from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Question:
    text: str
    options: list[str]
    answer: int = 0  # index of the correct option in `options`
    id: str = ""
    explanation: str = ""

    def to_dict(self) -> dict:
        d = {"id": self.id, "q": self.text, "options": self.options, "answer": self.answer}
        if self.explanation:
            d["explanation"] = self.explanation
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(
            text=d["q"],
            options=list(d["options"]),
            answer=int(d.get("answer", 0)),
            id=d.get("id", ""),
            explanation=d.get("explanation", ""),
        )


@dataclass
class Deck:
    id: str
    name: str
    source: str
    kind: str  # "bank" (parsed test bank), "generated" (offline), "ai"
    created: str
    questions: list[Question] = field(default_factory=list)

    def to_dict(self) -> dict:
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
        return cls(
            id=d["id"],
            name=d["name"],
            source=d.get("source", ""),
            kind=d.get("kind", "bank"),
            created=d.get("created", ""),
            questions=[Question.from_dict(q) for q in d.get("questions", [])],
        )
