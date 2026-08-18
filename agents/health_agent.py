"""Dependency-free canonical agent used for worker and runtime health checks."""


def health(_request: str):
    return {
        "success": True,
        "message": "Agent worker is healthy.",
        "status": "HEALTHY",
    }

