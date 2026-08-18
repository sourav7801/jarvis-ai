from sentence_transformers import SentenceTransformer
import chromadb


DB_PATH = "./data/chroma"
COLLECTION_NAME = "jarvis_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


print("=== JARVIS RAG ENGINE ===")
print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Opening ChromaDB...")

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

print(f"Knowledge items: {collection.count()}")


def search_knowledge(query, n_results=3):
    """
    Search Jarvis's knowledge base using semantic similarity.
    """

    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(n_results, collection.count())
    )

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    return [
        {
            "id": doc_id,
            "document": document,
            "distance": distance
        }
        for doc_id, document, distance
        in zip(ids, documents, distances)
    ]


if __name__ == "__main__":

    if collection.count() == 0:
        print("\nKnowledge base is empty.")
        print("Run ingest.py first.")
        raise SystemExit

    print("\n=== RAG SEARCH TEST ===")

    query = "What is Jarvis?"

    print(f"\nQuestion: {query}")

    results = search_knowledge(query)

    for i, result in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print("ID:", result["id"])
        print("Distance:", result["distance"])
        print("Content:", result["document"])

    print("\n=== RAG ENGINE TEST PASSED ===")