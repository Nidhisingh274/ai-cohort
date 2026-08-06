import json

required_fields = ["id", "text", "source_file", "source_type", "plan_type", "section", "ingested_at"]
allowed_sections = {"coverage", "exclusions", "claims", "enrollment"}
allowed_source_types = {"structured", "unstructured"}

with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total chunks: {len(lines)}")

source_types_found = set()
all_valid = True

for i, line in enumerate(lines, 1):
    chunk = json.loads(line)
    
    for field in required_fields:
        if field not in chunk:
            print(f"❌ Line {i}: missing field '{field}'")
            all_valid = False
    
    if chunk.get("section") not in allowed_sections:
        print(f"❌ Line {i}: invalid section '{chunk.get('section')}'")
        all_valid = False
    
    if chunk.get("source_type") not in allowed_source_types:
        print(f"❌ Line {i}: invalid source_type '{chunk.get('source_type')}'")
        all_valid = False
    
    source_types_found.add(chunk.get("source_type"))

print(f"\nSource types found: {source_types_found}")

if "structured" in source_types_found and "unstructured" in source_types_found:
    print("✅ Both structured and unstructured chunks present")
else:
    print("❌ Missing one of structured/unstructured")

if all_valid:
    print("✅ All chunks have valid required fields")
else:
    print("❌ Some chunks have issues (see above)")