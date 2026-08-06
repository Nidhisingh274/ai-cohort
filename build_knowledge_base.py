import os
import csv
import sqlite3
import json
from datetime import datetime, timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Counter for generating unique chunk IDs
chunk_id_counter = 1

def next_id():
    global chunk_id_counter
    current = chunk_id_counter
    chunk_id_counter += 1
    return f"chunk_{current:04d}"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# This will hold every chunk we create
all_chunks = []

# =====================
# STEP A: Convert plans.csv rows into structured chunks
# =====================
print("Processing plans (structured data)...")

with open("data/plans.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        text = (
            f"{row['plan_name']}: ${row['monthly_premium']}/month premium, "
            f"${row['annual_deductible']} deductible, "
            f"{row['copay_pct']}% copay, "
            f"network: {row['network_tier']} ({row['coverage_type']})"
        )
        chunk = {
            "id": next_id(),
            "text": text,
            "source_file": "data/plans.csv",
            "source_type": "structured",
            "plan_type": row["plan_name"],
            "section": "coverage",
            "ingested_at": now_iso()
        }
        all_chunks.append(chunk)

print(f"Added {len(all_chunks)} structured chunks from plans.csv")

# =====================
# STEP B: Chunk Day 5 unstructured text files
# =====================
print("\nProcessing raw_text files (unstructured data)...")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

# Map each file to a default section, and detect specific sections by keyword
raw_text_files = {
    "raw_text/benefits.txt": "coverage",
    "raw_text/claims_process.txt": "claims",
    "raw_text/enrollment.txt": "enrollment"
}

def detect_section(text_chunk, default_section):
    """Try to detect a more specific section based on keywords in the chunk."""
    lower = text_chunk.lower()
    if "exclusion" in lower or "not covered" in lower or "excluded" in lower:
        return "exclusions"
    if "claim" in lower and "process" in lower:
        return "claims"
    return default_section

unstructured_count = 0

for file_path, default_section in raw_text_files.items():
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found, skipping.")
        continue

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    text_chunks = splitter.split_text(content)

    for text_chunk in text_chunks:
        section = detect_section(text_chunk, default_section)
        chunk = {
            "id": next_id(),
            "text": text_chunk,
            "source_file": file_path,
            "source_type": "unstructured",
            "plan_type": "all",
            "section": section,
            "ingested_at": now_iso()
        }
        all_chunks.append(chunk)
        unstructured_count += 1

print(f"Added {unstructured_count} unstructured chunks from raw_text/ files")

# =====================
# STEP C: Write everything to knowledge_base.jsonl
# =====================
print(f"\nTotal chunks created: {len(all_chunks)}")

with open("knowledge_base.jsonl", "w", encoding="utf-8") as f:
    for chunk in all_chunks:
        f.write(json.dumps(chunk) + "\n")

print("Saved: knowledge_base.jsonl")

# =====================
# STEP D: Sanity check - print 5 random chunks
# =====================
import random

print("\n=== Sanity Check: 5 Random Chunks ===")
sample_chunks = random.sample(all_chunks, min(5, len(all_chunks)))
for c in sample_chunks:
    print(f"\n--- {c['id']} | section: {c['section']} | source: {c['source_file']} ---")
    print(c['text'][:300])  # print first 300 characters