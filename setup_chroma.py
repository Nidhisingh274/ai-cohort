import chromadb

# Create a persistent client - this saves data to disk so it survives restarts
client = chromadb.PersistentClient(path="./chroma_data")

# Create a collection (like a "table" for vectors)
collection = client.create_collection(name="coverage_kb")

print(f"Created collection: {collection.name}")

# Confirm it exists by listing all collections
all_collections = client.list_collections()
print(f"\nAll collections in this Chroma database:")
for c in all_collections:
    print(f"  - {c.name}")