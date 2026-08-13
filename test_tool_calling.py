from tool_calling_chatbot import ask_with_tools, TOOL_CALL_LOG

# =====================
# STEP 5: 5 questions that should trigger a tool, + 1 that shouldn't
# =====================
test_questions = [
    "Is an X-ray covered under plan P101?",              # should trigger check_coverage
    "What's the status of claim C1001?",                  # should trigger get_claim_status
    "Can you give me the full details of plan P102?",     # should trigger get_plan_details
    "How much would I pay out of pocket for surgery on plan P101?",  # should trigger estimate_out_of_pocket_cost
    "Is a checkup covered under plan P103?",               # should trigger check_coverage (again, different args)
    "What is a deductible in general?",                    # should trigger NO tool - general question
]

print(f"Running {len(test_questions)} test questions...\n")
print("=" * 70)

for i, question in enumerate(test_questions, 1):
    answer = ask_with_tools(question)
    print(f"\nTest {i}: {question}")
    print(f"Answer: {answer}")
    print("-" * 70)

print(f"\nAll {len(test_questions)} tests completed.")
print(f"\nTotal tool calls logged: {len(TOOL_CALL_LOG)}")

# Save the log to JSON so we can turn it into a markdown file
import json as json_module
with open("tool_call_log_raw.json", "w", encoding="utf-8") as f:
    json_module.dump(TOOL_CALL_LOG, f, indent=2, default=str)
print("Raw log saved to tool_call_log_raw.json")