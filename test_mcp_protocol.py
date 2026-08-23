"""Test whether calling the Day 23 MCP tools over the full protocol
completes within the mission's 10-second budget on this machine."""
import asyncio
import time
from multi_agent import call_mcp_tool_over_protocol


async def main():
    print("=" * 70)
    print("Testing get_claim_status over full MCP protocol")
    print("=" * 70)
    start = time.time()
    try:
        result = await asyncio.wait_for(
            call_mcp_tool_over_protocol("get_claim_status", {"claim_id": "C1001"}),
            timeout=120,   # generous, just to measure actual time
        )
        print(f"SUCCESS in {time.time() - start:.1f}s")
        print(f"Result: {result}")
    except asyncio.TimeoutError:
        print(f"TIMED OUT after {time.time() - start:.1f}s (limit was 120s)")
    except Exception as e:
        print(f"ERROR after {time.time() - start:.1f}s: {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("Testing check_coverage over full MCP protocol")
    print("=" * 70)
    start = time.time()
    try:
        result = await asyncio.wait_for(
            call_mcp_tool_over_protocol(
                "check_coverage",
                {"plan_name": "Silver HMO", "question": "What is my deductible?"},
            ),
            timeout=300,   # generous
        )
        print(f"SUCCESS in {time.time() - start:.1f}s")
        print(f"Result: {result[:300]}...")
    except asyncio.TimeoutError:
        print(f"TIMED OUT after {time.time() - start:.1f}s (limit was 300s)")
    except Exception as e:
        print(f"ERROR after {time.time() - start:.1f}s: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())