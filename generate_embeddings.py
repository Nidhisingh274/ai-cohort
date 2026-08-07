import json
import numpy as np
from sentence_transformers import SentenceTransformer

# Load the embedding model (downloads it the first time you run this)
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded.")

def embed(text):
    """Convert a piece of text into a numeric vector (embedding)."""
    return model.encode(text)

# =====================
# STEP: Load knowledge_base.jsonl and embed every chunk
# =====================
print("\nLoading knowledge_base.jsonl...")

chunks = []
with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

print(f"Loaded {len(chunks)} chunks.")

print("\nGenerating embeddings for each chunk...")
all_embeddings = []

for i, chunk in enumerate(chunks):
    vector = embed(chunk["text"])
    all_embeddings.append(vector)
    print(f"  Embedded chunk {i+1}/{len(chunks)}: {chunk['id']}")

# Convert list of vectors into a single 2D numpy array
# Shape: (number_of_chunks, embedding_dimension)
embeddings_array = np.array(all_embeddings)
print(f"\nEmbeddings array shape: {embeddings_array.shape}")

# Save the embeddings array to disk
np.save("embeddings.npy", embeddings_array)
print("Saved: embeddings.npy")