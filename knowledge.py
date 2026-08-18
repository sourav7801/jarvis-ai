from sentence_transformers import SentenceTransformer
import chromadb
import hashlib


class JarvisKnowledge:
    def __init__(
        self,
        database_path="./data/chroma",
        collection_name="jarvis_knowledge",
    ):
        print("Loading embedding model...")

        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        print("Opening ChromaDB...")

        self.client = chromadb.PersistentClient(
            path=database_path
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def add(self, text, source="unknown"):
        """
        Add a piece of knowledge to Jarvis memory.
        """

        text = text.strip()

        if not text:
            raise ValueError("Cannot add empty text.")

        # Create a stable unique ID from the content.
        content_hash = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()[:16]

        document_id = f"{source}_{content_hash}"

        embedding = self.model.encode(
            [text]
        )[0].tolist()

        self.collection.upsert(
            ids=[document_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[
                {
                    "source": source
                }
            ],
        )

        return document_id

    def search(self, query, n_results=5):
        """
        Search Jarvis memory using semantic similarity.
        """

        query = query.strip()

        if not query:
            return []

        query_embedding = self.model.encode(
            [query]
        )[0].tolist()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):
            output.append(
                {
                    "text": document,
                    "source": metadata.get(
                        "source",
                        "unknown",
                    ),
                    "distance": distance,
                }
            )

        return output

    def count(self):
        """
        Return the number of stored knowledge items.
        """

        return self.collection.count()


if __name__ == "__main__":

    print("\n=== JARVIS KNOWLEDGE ENGINE ===")

    knowledge = JarvisKnowledge()

    print(
        "Knowledge items:",
        knowledge.count(),
    )

    print(
        "\nKnowledge engine initialized successfully."
    )