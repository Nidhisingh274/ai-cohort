"""
Day 27 smoke test: run only 2 questions through RAGAS to confirm all four
metrics score correctly (especially answer_relevancy, which returned NaN
before the strictness fix) - without spending a full evaluation's tokens.
"""

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

from ragas_run import (
    load_eval_set,
    build_contexts,
    build_judges,
)
from retrieval_engine import retrieve
from rag_chatbot import generate_answer

answer_relevancy.strictness = 1

# Two questions only: one that should score well, one that exercises the fix
eval_rows = [
    r for r in load_eval_set()
    if r["question"] in (
        "What is the status of claim C1001?",
        "What procedure was claim C1001 filed for?",
    )
]

print(f"Smoke test on {len(eval_rows)} questions.\n")

records = []
for i, row in enumerate(eval_rows, 1):
    print(f"[{i}/{len(eval_rows)}] {row['question']}")
    retrieval_result = retrieve(row["question"])
    records.append({
        "question": row["question"],
        "contexts": build_contexts(retrieval_result),
        "answer": generate_answer(row["question"], retrieval_result["context"]),
        "ground_truth": row["ground_truth"],
    })

judge_llm, judge_embeddings = build_judges()

print("\nRunning RAGAS on 2 questions...\n")
result = evaluate(
    Dataset.from_list(records),
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=judge_llm,
    embeddings=judge_embeddings,
    run_config=RunConfig(timeout=180, max_workers=2),
)

print("\n" + "=" * 60)
print("SMOKE TEST RESULT")
print("=" * 60)
print(result)

df = result.to_pandas()
print("\nPer-question:")
print(df[["user_input", "faithfulness", "answer_relevancy",
          "context_precision", "context_recall"]].to_string())