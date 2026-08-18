from sentence_transformers import SentenceTransformer
import chromadb

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Creating ChromaDB...")
client = chromadb.PersistentClient(path="./data/chroma")

collection = client.get_or_create_collection(
    name="jarvis_knowledge"
)

documents = [
    "Jarvis is a local AI assistant.",
    "Jarvis can store and retrieve knowledge using a vector database.",
    "The embedding model converts text into numerical vectors.",
    "ChromaDB stores embeddings and allows semantic search.",
]

print("Adding knowledge...")
embeddings = model.encode(documents).tolist()

collection.upsert(
    ids=["doc1", "doc2", "doc3", "doc4"],
    documents=documents,
    embeddings=embeddings,
)

print("Searching knowledge...")

query = "How does Jarvis remember information?"
query_embedding = model.encode([query]).tolist()

results = collection.query(
    query_embeddings=query_embedding,
    n_results=2,
)

print("\n=== SEARCH RESULTS ===")

for i, document in enumerate(results["documents"][0], 1):
    print(f"{i}. {document}")

print("\n=== RAG TEST PASSED ===")
print("Documents stored:", collection.count())