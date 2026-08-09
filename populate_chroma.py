import json
import numpy as np
import chromadb

# =====================
# STEP A: Load knowledge_base.jsonl (Day 6)
# =====================
print("Loading knowledge_base.jsonl...")
chunks = []
with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))
print(f"Loaded {len(chunks)} chunks.")

# =====================
# STEP B: Load embeddings.npy (Day 7)
# =====================
print("\nLoading embeddings.npy...")
embeddings = np.load("embeddings.npy")
print(f"Embeddings shape: {embeddings.shape}")

# Sanity check - counts must match, same order as Day 7 generation
assert len(chunks) == embeddings.shape[0], "Mismatch between chunks and embeddings count!"
print("Counts match - chunks and embeddings are aligned.")

# =====================
# STEP C: Connect to the SAME persistent Chroma client/collection from Day 8
# =====================
print("\nConnecting to Chroma...")
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(name="coverage_kb")
print(f"Connected to collection: {collection.name}")

# =====================
# STEP D: Prepare data for upsert (Chroma needs separate lists)
# =====================
print("\nPreparing data for upsert...")

ids = [chunk["id"] for chunk in chunks]
documents = [chunk["text"] for chunk in chunks]
embeddings_list = embeddings.tolist()  # Chroma wants plain Python lists, not numpy arrays

# Metadata: everything except 'id' and 'text' (those are handled separately)
metadatas = []
for chunk in chunks:
    metadata = {
        "source_file": chunk["source_file"],
        "source_type": chunk["source_type"],
        "plan_type": chunk["plan_type"],
        "section": chunk["section"],
        "ingested_at": chunk["ingested_at"]
    }
    metadatas.append(metadata)

print(f"Prepared {len(ids)} records for upsert.")

# =====================
# STEP E: Upsert in batches of ~100 (we only have a few, but this is the right pattern)
# =====================
BATCH_SIZE = 100

print(f"\nUpserting in batches of {BATCH_SIZE}...")
for i in range(0, len(ids), BATCH_SIZE):
    batch_ids = ids[i:i+BATCH_SIZE]
    batch_embeddings = embeddings_list[i:i+BATCH_SIZE]
    batch_documents = documents[i:i+BATCH_SIZE]
    batch_metadatas = metadatas[i:i+BATCH_SIZE]

    collection.upsert(
        ids=batch_ids,
        embeddings=batch_embeddings,
        documents=batch_documents,
        metadatas=batch_metadatas
    )
    print(f"  Upserted batch {i//BATCH_SIZE + 1}: {len(batch_ids)} records")

print("\nAll chunks upserted successfully!")

# =====================
# STEP F: Verify count matches (Step 3 of mission)
# =====================
count = collection.count()
print(f"\nCollection count: {count}")
print(f"Expected (chunk total): {len(chunks)}")

if count == len(chunks):
    print("✅ Collection count matches chunk total!")
else:
    print("⚠️ Mismatch — count does not match chunk total.")