"""Open tests, kept in the API's memory.

A test is only needed while someone is taking it, so it isn't saved to disk;
the answers themselves are saved as progress straight away. To stop a busy or
abused server from filling its memory, tests are forgotten when they have been
idle for too long, and the oldest go first once there are too many.
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from collections.abc import Callable

from ..core.quiz import Session


class TestSessions:
    """A size- and time-limited store of open tests, keyed by a random id."""

    __test__ = False  # not a test case, despite the name

    def __init__(
        self, max_open: int = 1000, idle_seconds: float = 6 * 3600, clock: Callable[[], float] = time.monotonic
    ):
        """``clock`` returns the time in seconds; tests pass a fake one to move time forward."""
        if max_open < 1:
            raise ValueError("max_open must be at least 1")
        self.max_open = max_open
        self.idle_seconds = idle_seconds
        self._clock = clock
        # Least recently used first, so expiring and evicting only look at the front.
        self._items: OrderedDict[str, tuple[Session, float]] = OrderedDict()

    def __len__(self) -> int:
        """The number of tests kept right now (expired ones are dropped first)."""
        self._expire()
        return len(self._items)

    def add(self, session: Session) -> str:
        """Keep a new test and return its id. May forget the least recently used test."""
        self._expire()
        test_id = uuid.uuid4().hex
        self._items[test_id] = (session, self._clock())
        while len(self._items) > self.max_open:
            self._items.popitem(last=False)
        return test_id

    def get(self, test_id: str) -> Session | None:
        """The test with this id, or None if it never existed, expired or was evicted.

        Reading a test counts as using it, so it stays for another ``idle_seconds``.
        """
        self._expire()
        entry = self._items.get(test_id)
        if entry is None:
            return None
        self._items[test_id] = (entry[0], self._clock())
        self._items.move_to_end(test_id)
        return entry[0]

    def drop_deck(self, deck_id: str) -> int:
        """Forget every open test of a deck (used when the deck is deleted); returns how many."""
        doomed = [tid for tid, (session, _) in self._items.items() if session.deck_id == deck_id]
        for tid in doomed:
            del self._items[tid]
        return len(doomed)

    def _expire(self) -> None:
        limit = self._clock() - self.idle_seconds
        while self._items:
            first_id, (_, used) = next(iter(self._items.items()))
            if used > limit:
                break
            del self._items[first_id]
