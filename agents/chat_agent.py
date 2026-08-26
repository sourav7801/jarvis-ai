import re

import requests


# ============================================================
# JARVIS CHAT AGENT
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


UNVERIFIED_ORIGIN_CLAIM = re.compile(
    r"\b(?:famous (?:line|quote)|from the (?:film|movie)|spoken by|"
    r"mahabharata|ramayana|ancient (?:epic|text)|you meant|"
    r"correct phrase would be|roughly translates? to)\b",
    flags=re.IGNORECASE,
)


def _truthful_chat_message(query, message):
    """Fail closed when the small local model invents cultural provenance."""

    text = str(message or "").strip()
    if not text:
        return "I could not form a reliable answer. Please rephrase the sentence."
    if UNVERIFIED_ORIGIN_CLAIM.search(text):
        heard = re.sub(r"\s+", " ", str(query or "")).strip()
        return (
            f'I may be misunderstanding the sentence "{heard[:240]}". '
            "I will not invent a translation, quotation, film, person, or historical origin. "
            "Please repeat it more slowly in Hindi, Hinglish, or English, or ask me to verify it on the web."
        )
    return text


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
10. Do not invent factual metadata about named songs, films, artists, books, people,
    albums, or other named works. If uncertain, say so instead of fabricating.
11. Never fabricate song lyrics. If verified lyrics were not supplied in the prompt,
    do not make them up. Offer a summary or meaning instead.
12. When prior conversational context is present, resolve references such as
    "first one", "that song", "go ahead with it", or a repeated title against it
    before interpreting them as unrelated entities.
13. A transcript may contain misheard Hindi, Hinglish, names, or background speech.
    If its meaning is unclear, quote the words you received and ask the user to
    repeat or rephrase. Never manufacture a translation or continue a guessed story.
14. Never claim that an unclear phrase comes from a film, song, book, epic,
    historical person, or quotation unless verified evidence is supplied in this
    prompt. Sounding plausible is not evidence.
15. Do not "correct" the user's wording unless the correction is certain and
    necessary. Prefer: "I may have heard that incorrectly."

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
                    "options": {"temperature": 0.1},
                },
                timeout=120,
            )

            response.raise_for_status()

            data = response.json()

            message = data.get(
                "response",
                "",
            ).strip()
            message = _truthful_chat_message(query, message)

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
