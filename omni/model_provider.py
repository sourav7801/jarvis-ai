"""Model-provider interface and local Ollama implementation."""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .model_router import ModelProfile
from .runtime import audit_event


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    profile: ModelProfile
    timeout_seconds: float = 60.0
    json_mode: bool = False


@dataclass(frozen=True)
class GenerationResponse:
    text: str
    profile_id: str
    latency_ms: int


class ModelProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


class OllamaProvider:
    def __init__(self, url: str):
        self.url = url

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        if request.profile.provider.lower() != "ollama":
            raise ValueError("OllamaProvider received a non-Ollama profile.")
        if not request.prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        if request.timeout_seconds <= 0 or request.timeout_seconds > 300:
            raise ValueError("timeout_seconds must be in the range (0, 300].")

        payload = {
            "model": request.profile.model,
            "prompt": request.prompt,
            "stream": False,
        }
        if request.json_mode:
            payload["format"] = "json"
        raw = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.url,
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                http_request, timeout=request.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = str(body.get("response", "")).strip()
            if not text:
                raise RuntimeError("Ollama returned an empty response.")
            latency = int((time.perf_counter() - started) * 1000)
            audit_event(
                "model_provider",
                request.profile.id,
                "SUCCEEDED",
                {"latency_ms": latency, "response_characters": len(text)},
            )
            return GenerationResponse(text, request.profile.id, latency)
        except Exception as error:
            latency = int((time.perf_counter() - started) * 1000)
            audit_event(
                "model_provider",
                request.profile.id,
                "FAILED",
                {"latency_ms": latency, "error_type": type(error).__name__},
            )
            raise

