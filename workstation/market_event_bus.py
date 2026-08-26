"""Bounded, failure-isolated in-process market-event distribution."""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Any, Callable

from workstation.market_data_contract import MarketEventEnvelope, MarketEventType


Subscriber = Callable[[MarketEventEnvelope], None]


class MarketEventBus:
    def __init__(self, *, capacity: int = 2_000):
        self.capacity = max(10, min(int(capacity), 100_000))
        self._events: deque[dict[str, Any]] = deque(maxlen=self.capacity)
        self._subscribers: dict[str, tuple[set[str] | None, Subscriber]] = {}
        self._lock = RLock()
        self._published = 0
        self._subscriber_errors = 0

    def subscribe(self, name: str, callback: Subscriber, event_types: set[MarketEventType] | None = None) -> None:
        if not str(name).strip() or not callable(callback):
            raise ValueError("Subscriber name and callback are required.")
        normalized = {item.value for item in event_types} if event_types else None
        with self._lock:
            self._subscribers[str(name)] = (normalized, callback)

    def unsubscribe(self, name: str) -> None:
        with self._lock:
            self._subscribers.pop(str(name), None)

    def publish(self, event: MarketEventEnvelope) -> dict[str, Any]:
        if not isinstance(event, MarketEventEnvelope):
            raise TypeError("Only validated MarketEventEnvelope instances may be published.")
        with self._lock:
            self._events.append(event.as_dict())
            self._published += 1
            subscribers = list(self._subscribers.items())
        delivered = 0
        errors = 0
        for _name, (event_types, callback) in subscribers:
            if event_types is not None and event.datum.event_type not in event_types:
                continue
            try:
                callback(event)
                delivered += 1
            except Exception:
                errors += 1
        if errors:
            with self._lock:
                self._subscriber_errors += errors
        return {
            "accepted": True, "event_id": event.event_id, "delivered": delivered,
            "subscriber_errors": errors, "paper_only": True, "live_execution": False,
        }

    def snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)[-max(1, min(int(limit), self.capacity)):]
            return {
                "capacity": self.capacity, "retained": len(self._events),
                "published": self._published, "subscriber_errors": self._subscriber_errors,
                "subscribers": sorted(self._subscribers), "events": events,
                "paper_only": True, "live_execution": False,
            }


MARKET_EVENT_BUS = MarketEventBus()
