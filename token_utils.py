"""
Day 26: token counting helper.

tiktoken's cl100k_base encoding is used as a provider-agnostic
approximation. The project calls Groq's OpenAI-compatible endpoint
(openai/gpt-oss-20b), which does not publish a tiktoken encoding of its
own, so cl100k_base is used consistently for both prompt and completion
counts. This gives stable relative numbers for budgeting and comparison,
even if absolute counts differ slightly from the provider's own billing.
"""

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    """Return the number of tokens in a string. Non-strings count as 0."""
    if not isinstance(text, str):
        return 0
    return len(_ENCODING.encode(text))


def count_message_tokens(messages):
    """Count tokens across a list of {role, content} chat messages."""
    if not messages:
        return 0
    return sum(count_tokens(m.get("content", "")) for m in messages)


if __name__ == "__main__":
    samples = [
        "What is my deductible?",
        "Your annual deductible for the Silver HMO plan is $1,500.",
        "",
    ]
    for s in samples:
        print(f"{count_tokens(s):>4} tokens | {s!r}")