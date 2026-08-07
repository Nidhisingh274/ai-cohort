import json
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

# =====================
# STEP A: Load the saved embeddings and the chunk metadata
# =====================
print("Loading embeddings.npy...")
embeddings = np.load("embeddings.npy")
print(f"Embeddings shape: {embeddings.shape}")

print("\nLoading knowledge_base.jsonl for section labels...")
sections = []
with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        sections.append(chunk["section"])

print(f"Loaded {len(sections)} section labels: {sections}")

# =====================
# STEP B: Reduce 384 dimensions down to 2 using PCA
# =====================
print("\nRunning PCA to reduce to 2 dimensions...")
pca = PCA(n_components=2)
embeddings_2d = pca.fit_transform(embeddings)
print(f"Reduced shape: {embeddings_2d.shape}")

# =====================
# STEP C: Plot, color-coded by section
# =====================
print("\nCreating scatter plot...")

# Assign a distinct color to each unique section
unique_sections = list(set(sections))
color_map = plt.get_cmap("tab10", len(unique_sections))
section_to_color = {sec: color_map(i) for i, sec in enumerate(unique_sections)}

plt.figure(figsize=(8, 6))

for section in unique_sections:
    # Get indices of all points belonging to this section
    indices = [i for i, s in enumerate(sections) if s == section]
    x_vals = embeddings_2d[indices, 0]
    y_vals = embeddings_2d[indices, 1]
    plt.scatter(x_vals, y_vals, label=section, color=section_to_color[section], s=100)

plt.title("Knowledge Base Chunks - 2D Embedding Space (PCA)")
plt.xlabel("PCA Component 1")
plt.ylabel("PCA Component 2")
plt.legend()
plt.grid(True, alpha=0.3)

plt.savefig("embeddings_2d.png")
print("Saved: embeddings_2d.png")

plt.show()