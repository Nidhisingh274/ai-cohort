import chromadb
from sentence_transformers import SentenceTransformer

# =====================
# STEP A: Connect to the same Chroma collection
# =====================
print("Connecting to Chroma...")
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(name="coverage_kb")
print(f"Connected. Current count: {collection.count()}")

# =====================
# STEP B: Load the SAME embedding model used on Day 7
# =====================
print("\nLoading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text):
    return model.encode(text).tolist()

# =====================
# STEP C: Embed the test question
# =====================
test_question = "Is physical therapy covered under the Silver plan?"
print(f"\nTest question: {test_question}")
query_vector = embed(test_question)

# =====================
# STEP D: Run raw (unfiltered) query - Step 4 of mission
# =====================
print("\n=== RAW QUERY (no filter) ===")
raw_results = collection.query(
    query_embeddings=[query_vector],
    n_results=5
)

for i in range(len(raw_results["ids"][0])):
    print(f"\n--- Result {i+1} ---")
    print(f"ID: {raw_results['ids'][0][i]}")
    print(f"Distance: {raw_results['distances'][0][i]:.4f}")
    print(f"Plan type: {raw_results['metadatas'][0][i]['plan_type']}")
    print(f"Section: {raw_results['metadatas'][0][i]['section']}")
    print(f"Text: {raw_results['documents'][0][i][:200]}")

# =====================
# STEP E: Run filtered query (Silver plan only) - Step 6 of mission
# =====================
print("\n\n=== FILTERED QUERY (plan_type = Silver HMO) ===")
filtered_results = collection.query(
    query_embeddings=[query_vector],
    n_results=5,
    where={"plan_type": "Silver HMO"}
)

for i in range(len(filtered_results["ids"][0])):
    print(f"\n--- Result {i+1} ---")
    print(f"ID: {filtered_results['ids'][0][i]}")
    print(f"Distance: {filtered_results['distances'][0][i]:.4f}")
    print(f"Plan type: {filtered_results['metadatas'][0][i]['plan_type']}")
    print(f"Section: {filtered_results['metadatas'][0][i]['section']}")
    print(f"Text: {filtered_results['documents'][0][i][:200]}")