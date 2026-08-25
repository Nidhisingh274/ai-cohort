"""
Day 26 Step 6: run the same 15 questions through two prompt variants
(Day 12 Variant A vs Variant E) and log both answer sets side by side.

Everything except the system prompt is held constant: same retrieval
engine, same model, same temperature, same questions, same run.
"""

import os
from dotenv import load_dotenv
from retrieval_engine import retrieve
from rag_chatbot import client, MODEL_NAME
from token_utils import count_tokens

load_dotenv()

# =====================
# Variant A - Strict (Day 12)
# =====================
PROMPT_A = """You are a health coverage assistant.

Answer using ONLY the information in the context below. Do not guess or
add information not present in the context. If the context does not
contain the answer, respond exactly: "I don't have that information."

Be brief."""

# =====================
# Variant E - Hybrid (Day 12, current production)
# =====================
PROMPT_E = """You are a warm, professional health coverage assistant. Members may be
stressed about medical costs, so answer clearly, kindly, and concisely.

Before answering, internally check: (1) which plan the question refers
to, (2) whether the retrieved context actually contains the answer.

Answer using ONLY the information in the context below - do not guess
or add information not present there. If the plan isn't specified in
the question, ask the member to clarify which plan they mean rather
than guessing.

Example:
Q: What's my deductible on the Gold plan?
A: Your deductible on the Gold PPO plan is $2,000 per year.

If the context doesn't contain the answer, respond: "I don't have that
information in your plan documents. Please contact member support for
help."

This is not medical advice. For any medical questions, please consult a
licensed healthcare provider."""

VARIANTS = {"A": PROMPT_A, "E": PROMPT_E}

# =====================
# 15 questions, per the experiment design
# =====================
QUESTIONS = [
    # 6 plan/coverage questions across all three plans
    "What is the monthly premium for the Gold PPO plan?",
    "What is the annual deductible for the Silver HMO plan?",
    "What is the copay percentage on the Bronze HMO plan?",
    "What network type does the Gold PPO plan use?",
    "What is the out-of-pocket maximum on the Gold PPO plan?",
    "Which plan has the lowest monthly premium?",
    # 3 claim questions
    "What is the status of claim C1001?",
    "How much was claim C1001 for?",
    "What procedure was claim C1001 filed for?",
    # 3 questions not answerable from the corpus
    "Is physical therapy covered under the Silver HMO plan?",
    "Does the Bronze HMO plan cover dental cleanings?",
    "What is the vision benefit on the Gold PPO plan?",
    # 3 ambiguous questions with no plan named
    "What is my deductible?",
    "How much is my copay?",
    "What is my monthly premium?",
]


def answer_with_variant(question, system_prompt):
    """Generate one answer using the given system prompt."""
    retrieval_result = retrieve(question)
    context = retrieval_result["context"]

    user_message = f"""Context: {context}

Question: {question}"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def main():
    results = []

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'='*70}")
        print(f"Question {i}/15: {question}")
        print("=" * 70)

        row = {"n": i, "question": question}
        for label, prompt in VARIANTS.items():
            try:
                answer = answer_with_variant(question, prompt)
            except Exception as e:
                answer = f"[ERROR: {type(e).__name__}: {e}]"
            row[f"answer_{label}"] = answer
            row[f"tokens_{label}"] = count_tokens(answer)
            print(f"\n--- Variant {label} ({row[f'tokens_{label}']} tokens) ---")
            print(answer)

        results.append(row)

    # Write side-by-side output for scoring
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ab_raw_output.md")
    lines = [
        "# A/B Raw Output — Day 26",
        "",
        "Raw side-by-side answers from run_ab_test.py, before scoring. "
        "Scores and the conclusion live in ab_test_results.md.",
        "",
    ]
    for row in results:
        lines.append(f"## Q{row['n']}: {row['question']}\n")
        lines.append(f"**Variant A** ({row['tokens_A']} output tokens):\n")
        lines.append(row["answer_A"] + "\n")
        lines.append(f"**Variant E** ({row['tokens_E']} output tokens):\n")
        lines.append(row["answer_E"] + "\n")

    total_a = sum(r["tokens_A"] for r in results)
    total_e = sum(r["tokens_E"] for r in results)
    lines.append("## Output Token Totals\n")
    lines.append(f"- Variant A: {total_a} tokens across 15 answers "
                 f"(avg {total_a/15:.1f})")
    lines.append(f"- Variant E: {total_e} tokens across 15 answers "
                 f"(avg {total_e/15:.1f})")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n{'='*70}")
    print(f"Done. 15 questions x 2 variants = 30 answers.")
    print(f"Variant A total output tokens: {total_a}")
    print(f"Variant E total output tokens: {total_e}")
    print(f"Raw output written to ab_raw_output.md")
    print("=" * 70)


if __name__ == "__main__":
    main()