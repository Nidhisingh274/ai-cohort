import os
from dotenv import load_dotenv
from openai import OpenAI
from retrieval_engine import retrieve

# Load environment variables from .env
load_dotenv()

# =====================
# STEP 2: Connect to Groq via OpenAI-compatible SDK
# =====================
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

MODEL_NAME = "llama-3.1-8b-instant"

# =====================
# STEP 3: generate_answer(question, context) - grounded generation
# =====================
def generate_answer(question, context):
    """
    Send the question + retrieved context to the LLM with a grounding
    prompt, so it answers ONLY from the provided context.
    """
    system_prompt = """You are a warm, professional health coverage assistant. Members may be
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

    user_message = f"""Context: {context}

Question: {question}"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    return response.choices[0].message.content


# =====================
# STEP 4: retrieve_and_answer(question) - chains retrieve → generate
# =====================
def retrieve_and_answer(question):
    """
    Full RAG pipeline: retrieve relevant context, then generate a
    grounded answer using the LLM.
    """
    retrieval_result = retrieve(question)
    context = retrieval_result["context"]

    answer = generate_answer(question, context)

    return {
        "question": question,
        "classification": retrieval_result["classification"],
        "context": context,
        "answer": answer
    }


# =====================
# Quick manual test (only runs if this file is executed directly)
# =====================
if __name__ == "__main__":
    test_q = "What's my deductible on the Gold plan?"
    result = retrieve_and_answer(test_q)
    print(f"Question: {result['question']}")
    print(f"Classification: {result['classification']}")
    print(f"\nAnswer:\n{result['answer']}")