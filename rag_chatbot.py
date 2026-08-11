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
    system_prompt = """Answer using ONLY the context below.
If the answer isn't in the context, say you don't know and suggest the member contact support.
This is not medical advice."""

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