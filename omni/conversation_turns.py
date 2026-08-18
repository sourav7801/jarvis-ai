from __future__ import annotations

import difflib
import re
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field


@dataclass
class ConversationTurn:
    user: str
    assistant: str
    route: str
    created_at: float
    entities: tuple[str, ...] = field(default_factory=tuple)


class ConversationTurns:
    """Volatile working memory for conversational follow-ups.

    V2.1 keeps a small bounded history plus a stable useful anchor. Low-value
    clarification failures never replace the anchor. Lightweight entity hints
    let phrases such as "first one", "that song", and typoed repeated titles
    resolve against the user's recent conversation without making durable memory
    claims.
    """

    TTL_SECONDS = 300.0
    MAX_ASSISTANT_CHARS = 1800
    HISTORY_SIZE = 6

    def __init__(self):
        self._lock = threading.RLock()
        self._turn: ConversationTurn | None = None
        self._anchor: ConversationTurn | None = None
        self._history: deque[ConversationTurn] = deque(maxlen=self.HISTORY_SIZE)

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
                "i don't know what you mean",
                "i didn't suggest",
                "i did not suggest",
                "i don't have prior context",
                "i do not have prior context",
                "i don't have any context",
                "i do not have any context",
                "i don't have context about",
                "i do not have context about",
                "could you please provide more information",
                "clarify which song",
                "i don't have access to the previous conversation",
                "i do not have access to the previous conversation",
                "i'm a new conversation",
                "i am a new conversation",
                "each time you interact with me",
            )
        )

    @staticmethod
    def _extract_entities(text: str) -> tuple[str, ...]:
        value = str(text or "")
        found: list[str] = []

        # Quoted names/titles are the strongest low-cost signal.
        for match in re.finditer(r'["“]([^"”\n]{2,120})["”]', value):
            item = " ".join(match.group(1).split()).strip(" .,:;-")
            if item and item.casefold() not in {x.casefold() for x in found}:
                found.append(item)

        # Also accept concise numbered recommendation labels before a dash/colon.
        for line in value.splitlines():
            match = re.match(
                r"^\s*\d+[.)]\s+(.{2,100}?)(?:\s+[–—-]\s+|\s*:\s+|$)",
                line,
            )
            if not match:
                continue
            item = " ".join(match.group(1).split()).strip(' "\'“”.,:;-')
            if (
                item
                and len(item.split()) <= 12
                and item.casefold() not in {x.casefold() for x in found}
            ):
                found.append(item)

        return tuple(found[:12])

    def _expired(self, turn: ConversationTurn) -> bool:
        return time.monotonic() - turn.created_at > self.TTL_SECONDS

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
            entities=self._extract_entities(assistant),
        )

        with self._lock:
            self._turn = turn
            self._history.append(turn)

            if not self._low_value_response(assistant):
                self._anchor = turn

    def latest(self, *, prefer_anchor: bool = False) -> dict | None:
        with self._lock:
            turn = self._anchor if prefer_anchor and self._anchor is not None else self._turn

            if turn is None:
                return None

            if self._expired(turn):
                if turn is self._turn:
                    self._turn = None
                if turn is self._anchor:
                    self._anchor = None
                return None

            return asdict(turn)

    def history(self, limit: int = 3, *, useful_only: bool = True) -> tuple[dict, ...]:
        limit = max(1, min(int(limit), self.HISTORY_SIZE))

        with self._lock:
            turns = list(self._history)

        result = []
        for turn in reversed(turns):
            if self._expired(turn):
                continue
            if useful_only and self._low_value_response(turn.assistant):
                continue
            result.append(asdict(turn))
            if len(result) >= limit:
                break

        return tuple(reversed(result))

    @staticmethod
    def is_explanation_followup(text: str) -> bool:
        value = " ".join(str(text or "").lower().split()).strip()
        return value in {
            "why",
            "why?",
            "how so",
            "explain",
            "explain that",
            "why did that happen",
            "why did it happen",
        }

    @staticmethod
    def is_reference_followup(text: str) -> bool:
        """Recognize semantic references even when the sentence is long.

        Examples:
        - Can you give me the lyrics of first one song which you suggested me?
        - Tell me more about the second one you recommended.
        - What was that movie you mentioned earlier?
        """
        value = " ".join(str(text or "").lower().split()).strip()
        if not value:
            return False

        reference_words = (
            r"first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|"
            r"that one|this one|that song|this song|that movie|this movie|"
            r"the one|it"
        )
        prior_words = (
            r"suggested|recommend(?:ed)?|mentioned|listed|gave|told|"
            r"previous|earlier|above|before"
        )

        if re.search(rf"\b(?:{reference_words})\b", value) and re.search(
            rf"\b(?:{prior_words})\b", value
        ):
            return True

        if re.search(
            r"\b(?:which|that)\s+you\s+(?:suggested|recommended|mentioned|listed|gave)\b",
            value,
        ):
            return True

        if re.search(
            r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:give|tell|show|explain)\b",
            value,
        ) and re.search(rf"\b(?:{reference_words})\b", value):
            return True

        return False

    @classmethod
    def is_ambiguous_followup(cls, text: str) -> bool:
        value = " ".join(str(text or "").split()).strip()
        lowered = value.lower()

        if not value:
            return False

        if cls.is_reference_followup(value):
            return True

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
            "that one",
            "this one",
            "the first one",
            "the second one",
            "the third one",
        }

        if lowered in explicit:
            return True

        if re.match(
            r"^(?:go ahead with|go with|continue with|proceed with|"
            r"tell me about|play|choose|select|give me (?:the )?"
            r"(?:first|second|third|fourth|fifth))\b",
            lowered,
        ):
            return True

        words = re.findall(r"[A-Za-z0-9']+", value)

        if 1 <= len(words) <= 6:
            if re.match(
                r"^(?:open|close|launch|start|stop|search|find|diagnose|repair|"
                r"buy|sell|trade|analyze|analyse|show|create|make|write|run)\b",
                lowered,
            ):
                return False

            return True

        return False

    @staticmethod
    def _normal(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))

    def reference_hint(self, text: str) -> str | None:
        latest = self.latest(prefer_anchor=True)
        if not latest:
            return None

        entities = tuple(latest.get("entities") or ())
        if not entities:
            return None

        lowered = self._normal(text)

        ordinal_map = {
            "first": 0,
            "1st": 0,
            "second": 1,
            "2nd": 1,
            "third": 2,
            "3rd": 2,
            "fourth": 3,
            "4th": 3,
            "fifth": 4,
            "5th": 4,
        }
        for token, index in ordinal_map.items():
            if re.search(rf"\b{re.escape(token)}\b", str(text or "").casefold()):
                if index < len(entities):
                    return entities[index]

        if lowered in {"that one", "this one", "it", "that", "this"}:
            return entities[0]

        # Repeated title with a small typo: "lagg ja gale" -> "Lag Jaa Gale".
        best = None
        best_score = 0.0
        for entity in entities:
            target = self._normal(entity)
            if not target:
                continue
            score = difflib.SequenceMatcher(None, lowered, target).ratio()
            if target in lowered or lowered in target:
                score = max(score, 0.92)
            if score > best_score:
                best = entity
                best_score = score

        return best if best_score >= 0.62 else None

    def augment(self, text: str) -> str:
        hint = self.reference_hint(text)

        if not self.is_ambiguous_followup(text) and not hint:
            return str(text or "")

        latest = self.latest(prefer_anchor=True)

        if not latest:
            return str(text or "")

        recent = self.history(3, useful_only=True)

        history_lines = []
        for index, turn in enumerate(recent, start=1):
            history_lines.append(
                f"Recent turn {index} user: {turn['user']}\n"
                f"Recent turn {index} JARVIS: {turn['assistant']}"
            )

        hint_text = (
            f"\nResolved reference hint: {hint}\n"
            if hint
            else ""
        )

        return (
            "CONVERSATION FOLLOW-UP. Use recent conversational context only to "
            "resolve the current follow-up. Do not reinterpret it as a new unrelated "
            "request. Treat names/titles from the previous answer as likely referents "
            "when the user selects, numbers, or approximately repeats them. Do not "
            "invent facts, lyrics, metadata, or actions. Never say that prior context "
            "is unavailable when it is explicitly included below.\n\n"
            + "\n\n".join(history_lines)
            + "\n\n"
            + f"Previous user request: {latest['user']}\n"
            + f"Previous JARVIS response: {latest['assistant']}\n"
            + hint_text
            + f"Stable previous route: {latest['route']}\n"
            + f"Current user follow-up: {str(text or '').strip()}"
        )


conversation_turns = ConversationTurns()
