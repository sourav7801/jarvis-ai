import requests


# ============================================================
# JARVIS CHAT AGENT
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


class ChatAgent:

    def __init__(self):
        self.name = "chat"

    def chat(self, query):

        prompt = f"""
You are JARVIS, a helpful local AI assistant.

The user is having a normal conversation with you.

Rules:

1. Be helpful and natural.
2. Answer the user's question directly.
3. Keep responses reasonably concise.
4. Do not invent tools.
5. Do not claim that you performed actions you did not perform.
6. Do not route the request to another agent.
7. Do not output JSON.
8. Answer normally.
9. Never claim a current or recent price, quote, headline, score, office-holder,
   market condition, or other time-sensitive fact without verified data supplied
   in this prompt. If the user asks for live/current information, say that the
   conversational agent cannot verify it; do not guess or cite your last update.

USER:

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

            message = data.get(
                "response",
                "",
            ).strip()

            return {
                "success": True,
                "type": "chat",
                "message": message,
            }

        except Exception as e:

            return {
                "success": False,
                "type": "chat",
                "message": f"Chat agent error: {e}",
            }


chat_agent = ChatAgent()


def chat(query):

    return chat_agent.chat(query)


if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS CHAT AGENT TEST")
    print("=" * 60)

    result = chat(
        "Hi Jarvis, how are you?"
    )

    print(
        result.get(
            "message",
            result,
        )
    )
