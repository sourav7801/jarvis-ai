import requests
import json


# ============================================================
# JARVIS CODING AGENT
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


class CodingAgent:

    def __init__(self):

        self.name = "coding"


    # ========================================================
    # ASK LOCAL AI
    # ========================================================

    def ask(self, query):

        prompt = f"""
You are JARVIS Coding Agent.

You are a professional software engineer.

Your job is to help the user with programming.

Rules:

1. Write correct, practical code.
2. Prefer Python unless another language is requested.
3. Explain important parts briefly.
4. Never pretend that code was executed if it was not.
5. Never invent files, libraries, APIs, or tool results.
6. If the user asks to modify code, clearly show the replacement.
7. Preserve the user's existing architecture when possible.
8. Do not execute shell commands.
9. Do not claim to have changed files.
10. Return useful code directly.

USER REQUEST:

{query}
"""

        try:

            response = requests.post(

                OLLAMA_URL,

                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },

                timeout=120,

            )

            response.raise_for_status()

            data = response.json()

            return data.get(
                "response",
                ""
            ).strip()


        except Exception as e:

            return (
                "Coding agent error: "
                f"{e}"
            )


    # ========================================================
    # PUBLIC RESEARCH METHOD
    # ========================================================

    def coding(self, query):

        result = self.ask(query)

        return {

            "success": True,

            "type": "coding",

            "message": result,

        }


# ============================================================
# GLOBAL AGENT
# ============================================================

coding_agent = CodingAgent()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def coding(query):

    return coding_agent.coding(
        query
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS CODING AGENT TEST")
    print("=" * 60)

    result = coding(
        "Write a Python function that checks whether a number is prime."
    )

    print()

    print(
        result.get(
            "message",
            result
        )
    )