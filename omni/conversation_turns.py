from __future__ import annotations

import re
import threading
import time
from dataclasses import asdict, dataclass


@dataclass
class ConversationTurn:
    user: str
    assistant: str
    route: str
    created_at: float


class ConversationTurns:
    """Volatile context for short ambiguous follow-up turns.

    V1.1 keeps a stable conversational anchor so a failed clarification does
    not erase the useful recommendation/topic that the user is following up on.
    """

    TTL_SECONDS = 180.0
    MAX_ASSISTANT_CHARS = 1800

    def __init__(self):
        self._lock = threading.RLock()
        self._turn: ConversationTurn | None = None
        self._anchor: ConversationTurn | None = None

    @staticmethod
    def _low_value_response(text: str) -> bool:
        value = " ".join(str(text or "").lower().split())
        return any(
            marker in value
            for marker in (
                "i can't understand",
                "i cannot understand",
                "could you please rephrase",
                "provide more context",
                "could you please provide more context",
                "i'm not sure what you're referring to",
                "am i correct?",
            )
        )

    def remember(self, user: str, assistant: str, route: str = "") -> None:
        user = " ".join(str(user or "").split()).strip()
        assistant = str(assistant or "").strip()

        if not user or not assistant:
            return

        turn = ConversationTurn(
            user=user[:600],
            assistant=assistant[: self.MAX_ASSISTANT_CHARS],
            route=str(route or "")[:80],
            created_at=time.monotonic(),
        )

        with self._lock:
            self._turn = turn

            if not self._low_value_response(assistant):
                self._anchor = turn

    def latest(self, *, prefer_anchor: bool = False) -> dict | None:
        with self._lock:
            turn = self._anchor if prefer_anchor and self._anchor is not None else self._turn

            if turn is None:
                return None

            if time.monotonic() - turn.created_at > self.TTL_SECONDS:
                if turn is self._turn:
                    self._turn = None
                if turn is self._anchor:
                    self._anchor = None
                return None

            return asdict(turn)

    @staticmethod
    def is_ambiguous_followup(text: str) -> bool:
        value = " ".join(str(text or "").split()).strip()
        lowered = value.lower()

        if not value:
            return False

        explicit = {
            "why",
            "why?",
            "how so",
            "what happened",
            "what happened?",
            "explain",
            "explain that",
            "tell me more",
            "more",
            "what about it",
            "what about that",
            "and why",
        }

        if lowered in explicit:
            return True

        if re.match(
            r"^(?:go ahead with|go with|continue with|proceed with|"
            r"tell me about|play|choose|select)\b",
            lowered,
        ):
            return True

        words = re.findall(r"[A-Za-z0-9']+", value)

        if 1 <= len(words) <= 5:
            if re.match(
                r"^(?:open|close|launch|start|stop|search|find|diagnose|repair|"
                r"buy|sell|trade|analyze|analyse|show|create|make|write|run)\b",
                lowered,
            ):
                return False

            return True

        return False

    def augment(self, text: str) -> str:
        if not self.is_ambiguous_followup(text):
            return str(text or "")

        latest = self.latest(prefer_anchor=True)

        if not latest:
            return str(text or "")

        return (
            "Use the previous conversational turn only to resolve the current "
            "follow-up. Treat names/titles mentioned in the previous answer as "
            "likely referents when the user selects or repeats them. Do not invent "
            "facts or claim actions that were not performed.\n\n"
            f"Previous user request: {latest['user']}\n"
            f"Previous JARVIS response: {latest['assistant']}\n"
            f"Previous route: {latest['route']}\n\n"
            f"Current user follow-up: {str(text or '').strip()}"
        )


conversation_turns = ConversationTurns()
