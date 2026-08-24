"""
Day 25 Step 2: scan knowledge_base.jsonl and the SQL tables in coverage.db
for likely PHI/PII columns and values, so redact_pii() covers what actually
exists in this project's data.
"""

import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "coverage.db")
KB_PATH = os.path.join(ROOT, "knowledge_base.jsonl")

# Column names that commonly carry PHI/PII in healthcare data
PII_COLUMN_HINTS = [
    "member", "patient", "name", "dob", "birth", "ssn", "email",
    "phone", "address", "claim_id", "procedure", "diagnosis",
]

# Value shapes that indicate an identifier in free text
VALUE_PATTERNS = {
    "member_id": r"\bM\d{4,}\b",
    "claim_id": r"\bC\d{4,}\b",
    "date": r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b",
    "email": r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
    "phone": r"\b(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "person_name": r"(Member Name|Signature)\s*:\s*[A-Z][a-z]+\s+[A-Z][a-z]+",
}


def scan_sql_tables():
    print("=" * 70)
    print("Scanning SQL tables in coverage.db")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]

    findings = {}
    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        flagged = [c for c in cols
                   if any(hint in c.lower() for hint in PII_COLUMN_HINTS)]
        findings[table] = {"columns": cols, "flagged": flagged}

        print(f"\nTable: {table}")
        print(f"  All columns: {cols}")
        print(f"  Flagged as likely PHI/PII: {flagged if flagged else 'none'}")

    conn.close()
    return findings


def scan_knowledge_base():
    print("\n" + "=" * 70)
    print("Scanning knowledge_base.jsonl for identifier-shaped values")
    print("=" * 70)

    if not os.path.exists(KB_PATH):
        print(f"  {KB_PATH} not found - skipping")
        return {}

    hits = {k: [] for k in VALUE_PATTERNS}
    chunk_count = 0

    with open(KB_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk_count += 1
            record = json.loads(line)
            text = record.get("text", "")
            chunk_id = record.get("id", "?")

            for label, pattern in VALUE_PATTERNS.items():
                for match in re.findall(pattern, text):
                    value = match if isinstance(match, str) else match[0]
                    hits[label].append((chunk_id, value))

    print(f"\nScanned {chunk_count} chunks.\n")
    for label, found in hits.items():
        if found:
            print(f"  {label}: {len(found)} hit(s)")
            for chunk_id, value in found[:5]:
                print(f"    - {chunk_id}: {value}")
        else:
            print(f"  {label}: none")

    return hits


def main():
    sql_findings = scan_sql_tables()
    kb_hits = scan_knowledge_base()

    print("\n" + "=" * 70)
    print("Summary: fields redact_pii() must cover")
    print("=" * 70)

    all_flagged = set()
    for table, info in sql_findings.items():
        all_flagged.update(info["flagged"])
    for label, found in kb_hits.items():
        if found:
            all_flagged.add(label)

    for field in sorted(all_flagged):
        print(f"  - {field}")

    print("\nAll data in this project is synthetic; no real member data is used.")


if __name__ == "__main__":
    main()