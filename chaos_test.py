"""Day 24 chaos test: break one MCP tool, confirm the fallback triggers."""
import multi_agent

print("=" * 70)
print("CHAOS TEST: breaking the get_claim_status MCP tool")
print("=" * 70)


def broken_get_claim_status(claim_id):
    raise RuntimeError("Simulated tool failure (chaos test)")


original = multi_agent._get_claim_status_via_protocol
multi_agent._get_claim_status_via_protocol = broken_get_claim_status


def broken_wrapper(input_str: str) -> str:
    return multi_agent.resilient_tool_call(
        multi_agent._get_claim_status_via_protocol, input_str.strip(),
        tool_name="get_claim_status"
    )


multi_agent.claims_tools[0].func = broken_wrapper

category, answer = multi_agent.ask("What's the status of claim C1001?", "chaos-test-broken")
print(f"\nRouted to: {category}")
print(f"Answer returned to member: {answer}")
print(f"\nFallback triggered: {'trouble' in answer.lower() or 'support' in answer.lower()}")

multi_agent._get_claim_status_via_protocol = original


def restored_wrapper(input_str: str) -> str:
    return multi_agent.resilient_tool_call(
        multi_agent._get_claim_status_via_protocol, input_str.strip(),
        tool_name="get_claim_status"
    )


multi_agent.claims_tools[0].func = restored_wrapper

print("\n" + "=" * 70)
print("CHAOS TEST: tool restored, re-testing")
print("=" * 70)

category, answer = multi_agent.ask("What's the status of claim C1001?", "chaos-test-restored")
print(f"\nRouted to: {category}")
print(f"Answer returned to member: {answer}")