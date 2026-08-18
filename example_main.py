from bootstrap import *  # registers tools
from core.model import FunctionModelProvider
from core.orchestrator import JarvisAgent


def your_existing_ai_function(messages):
    """
    Replace this with your existing Ollama/OpenAI/Codex model call.

    It must accept a list like:
      [{"role":"system","content":"..."}, {"role":"user","content":"..."}]

    and return raw model text.
    """
    raise NotImplementedError("Connect your current model here.")


def main():
    model = FunctionModelProvider(your_existing_ai_function)
    jarvis = JarvisAgent(model=model)

    while True:
        text = input("\nYOU > ").strip()

        if text.lower() in {"exit", "quit"}:
            break

        answer = jarvis.run(text)
        print(f"\nJARVIS > {answer}")


if __name__ == "__main__":
    main()
