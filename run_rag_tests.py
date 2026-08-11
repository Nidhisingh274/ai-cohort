from rag_chatbot import retrieve_and_answer

# Same 10 questions as Day 10, for direct comparison
test_questions = [
    "What's my deductible on the Gold plan?",
    "What is my copay?",
    "Is physical therapy covered under the Silver plan?",
    "Status of claim C1001",
    "How do I file a claim?",
    "Is maternity care covered on the Bronze plan?",
    "What's the monthly premium for Silver HMO?",
    "Are pre-existing conditions excluded?",
    "What's my copay on the Gold plan and is dental covered?",
    "How much is the Bronze plan deductible and what does it cover?"
]

print(f"Running {len(test_questions)} questions through full RAG pipeline...\n")
print("=" * 70)

all_results = []

for i, question in enumerate(test_questions, 1):
    result = retrieve_and_answer(question)
    all_results.append(result)

    print(f"\nTest {i}: {question}")
    print(f"Classification: {result['classification']}")
    print(f"Answer: {result['answer']}")
    print("-" * 70)

print(f"\nAll {len(test_questions)} tests completed.")