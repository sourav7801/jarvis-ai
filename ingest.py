from pathlib import Path
from knowledge import JarvisKnowledge


def chunk_text(text, chunk_size=500, overlap=100):
    """
    Split text into overlapping chunks.
    """

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def ingest_file(file_path, knowledge):
    """
    Read a TXT or Markdown file and add its chunks to Jarvis memory.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    if path.suffix.lower() not in [".txt", ".md"]:
        raise ValueError(
            "Only .txt and .md files are supported currently."
        )

    text = path.read_text(
        encoding="utf-8"
    )

    chunks = chunk_text(text)

    print(f"File: {path.name}")
    print(f"Chunks: {len(chunks)}")

    for index, chunk in enumerate(chunks):
        knowledge.add(
            chunk,
            source=f"{path.name}:chunk_{index}",
        )

    return len(chunks)


if __name__ == "__main__":

    print("\n=== JARVIS DOCUMENT INGESTION ===")

    knowledge = JarvisKnowledge()

    # Create a small test document.
    test_file = Path("./data/jarvis_test.txt")

    test_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    test_file.write_text(
        """
Jarvis is a local AI assistant.

Jarvis can store knowledge locally using ChromaDB.

Text is converted into numerical embeddings using
the all-MiniLM-L6-v2 embedding model.

The knowledge engine can later retrieve relevant
information when the user asks a question.
""".strip(),
        encoding="utf-8",
    )

    count = ingest_file(
        test_file,
        knowledge,
    )

    print(
        f"\nSuccessfully ingested {count} chunks."
    )

    print(
        "Total knowledge items:",
        knowledge.count(),
    )

    print(
        "\n=== DOCUMENT INGESTION TEST PASSED ==="
    )