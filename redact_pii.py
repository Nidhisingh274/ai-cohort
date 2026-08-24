"""
Day 25: PHI/PII redaction.

Patterns were chosen after scanning the project's own data:
- claims table / claims.csv: member_id (M1001), claim_id (C1001)
- raw_text/enrollment.txt: member name ("John Doe"), member ID, date of birth
- conversations table: free-text member messages, which may contain emails
  or phone numbers the member volunteers

All data in this project is synthetic - no real member data is used.
"""

import re

# =====================
# Redaction patterns
# =====================
PATTERNS = [
    # Member IDs like M1001
    (re.compile(r"\bM\d{4,}\b"), "[MEMBER_ID]"),

    # Claim IDs like C1001
    (re.compile(r"\bC\d{4,}\b"), "[CLAIM_ID]"),

    # Email addresses
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),

    # Phone numbers: 10-digit, with optional country code and separators
    (re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "[PHONE]"),

    # US-style SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),

    # Dates of birth / ISO dates like 1990-05-15
    (re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"), "[DATE]"),

    # Explicitly labelled member names, e.g. "Member Name: John Doe"
    (re.compile(r"(Member Name\s*:\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.IGNORECASE), r"\1[NAME]"),
]

# Known synthetic names appearing in this project's corpus (enrollment.txt,
# including the OCR variant captured on Day 5).
KNOWN_NAMES = ["John Doe", "John Dos"]


def redact_pii(text):
    """
    Redact PHI/PII from a string.

    Replaces member IDs, claim IDs, emails, phone numbers, SSNs, dates of
    birth, and known member names with bracketed placeholders. Returns the
    redacted string; non-string input is returned unchanged.
    """
    if not isinstance(text, str):
        return text

    redacted = text

    # Known names first, so they aren't partially masked by other patterns
    for name in KNOWN_NAMES:
        redacted = re.sub(re.escape(name), "[NAME]", redacted, flags=re.IGNORECASE)

    for pattern, replacement in PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return redacted


# =====================
# STEP 3: Unit tests - 3 sample strings containing fake PHI/PII
# =====================
def run_unit_tests():
    tests = [
        {
            "name": "Test 1: member ID and claim ID",
            "input": "Member M1001 filed claim C1001 for an X-ray on 2023-04-01.",
            "must_not_contain": ["M1001", "C1001", "2023-04-01"],
            "must_contain": ["[MEMBER_ID]", "[CLAIM_ID]", "[DATE]"],
        },
        {
            "name": "Test 2: name, date of birth, email",
            "input": "Member Name: John Doe, Date of Birth: 1990-05-15, contact john.doe@example.com",
            "must_not_contain": ["John Doe", "1990-05-15", "john.doe@example.com"],
            "must_contain": ["[NAME]", "[DATE]", "[EMAIL]"],
        },
        {
            "name": "Test 3: phone number and SSN",
            "input": "Call me at 555-123-4567 or verify with SSN 123-45-6789.",
            "must_not_contain": ["555-123-4567", "123-45-6789"],
            "must_contain": ["[PHONE]", "[SSN]"],
        },
    ]

    passed = 0
    for t in tests:
        result = redact_pii(t["input"])
        leaked = [s for s in t["must_not_contain"] if s in result]
        missing = [s for s in t["must_contain"] if s not in result]
        ok = not leaked and not missing

        print(f"\n{t['name']}")
        print(f"  Input:  {t['input']}")
        print(f"  Output: {result}")
        if ok:
            print("  PASS")
            passed += 1
        else:
            print("  FAIL")
            if leaked:
                print(f"    Leaked: {leaked}")
            if missing:
                print(f"    Missing placeholders: {missing}")

    print(f"\n{passed}/{len(tests)} unit tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    run_unit_tests()