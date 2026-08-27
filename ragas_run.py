"""
Day 27: run the full RAG pipeline over the eval set and score it with RAGAS
on faithfulness, answer_relevancy, context_precision, and context_recall.

RAGAS needs a judge LLM and an embedding model. This project uses Groq's
OpenAI-compatible endpoint (openai/gpt-oss-20b) as the judge and the same
local all-MiniLM-L6-v2 model used by the retrieval engine, so no OpenAI
key is required.
"""

import os
import json
import argparse
from dotenv import load_dotenv

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

# Groq's API rejects n > 1, and answer_relevancy asks for `strictness`
# generations by default (3). Setting it to 1 keeps the metric working
# against a provider that only supports single generations.
answer_relevancy.strictness = 1

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from retrieval_engine import retrieve
from rag_chatbot import generate_answer

load_dotenv()

ROOT = os.path.dirname(os.path.abspath(__file__))
EVAL_SET_PATH = os.path.join(ROOT, "ragas_eval_set.jsonl")


def load_eval_set(path=EVAL_SET_PATH):
    """Load the question / ground-truth pairs."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_contexts(retrieval_result):
    """
    STEP 3: turn the retrieval result into the list-of-strings shape RAGAS
    expects for 'contexts'. Both the SQL rows and the vector chunks count as
    retrieved context, since both are what the answer was grounded in.
    """
    contexts = []
    for row in retrieval_result.get("sql_results", []):
        contexts.append(str(row))
    for chunk in retrieval_result.get("vector_results", []):
        contexts.append(chunk["text"])
    return contexts if contexts else ["(no context retrieved)"]


def run_pipeline(eval_rows):
    """STEP 3: run every question through the real RAG pipeline."""
    records = []
    for i, row in enumerate(eval_rows, 1):
        question = row["question"]
        print(f"[{i}/{len(eval_rows)}] {question}")

        retrieval_result = retrieve(question)
        contexts = build_contexts(retrieval_result)
        answer = generate_answer(question, retrieval_result["context"])

        records.append({
            "question": question,
            "contexts": contexts,
            "answer": answer,
            "ground_truth": row["ground_truth"],
        })
    return records


def build_judges():
    """
    Point RAGAS at Groq for judging and at the local model for embeddings.

    Groq's API rejects n > 1 ("'n' : number must be at most 1"), while RAGAS
    asks for 3 generations by default on some metrics. n=1 is set explicitly,
    and a longer timeout is given because the judge model is slower than the
    default allows on this connection.
    """
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ["GROQ_API_KEY"],
            model="openai/gpt-oss-20b",
            temperature=0,
            n=1,
            timeout=180,
            max_retries=3,
        )
    )
    judge_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )
    return judge_llm, judge_embeddings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline",
                        help="Label for this run, e.g. 'baseline' or 'after-fix'")
    args = parser.parse_args()

    eval_rows = load_eval_set()
    print(f"Loaded {len(eval_rows)} question / ground-truth pairs.\n")

    records = run_pipeline(eval_rows)

    dataset = Dataset.from_list(records)

    judge_llm, judge_embeddings = build_judges()

    print("\nRunning RAGAS evaluate()...\n")
    # STEP 4: the four metrics this mission requires
    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(timeout=180, max_workers=2),
    )

    print("\n" + "=" * 70)
    print(f"RAGAS SCORES ({args.label})")
    print("=" * 70)
    print(result)

    # Save per-question detail and the summary for the scorecard
    df = result.to_pandas()
    out_csv = os.path.join(ROOT, f"ragas_results_{args.label}.csv")
    df.to_csv(out_csv, index=False)
    print(f"\nPer-question scores written to {out_csv}")

    print("\nMean scores:")
    for metric in ["faithfulness", "answer_relevancy",
                   "context_precision", "context_recall"]:
        if metric in df.columns:
            print(f"  {metric:20s} {df[metric].mean():.4f}")


if __name__ == "__main__":
    main()