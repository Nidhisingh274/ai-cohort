# MCP Test Notes — Day 23

## Server Setup

Server file: mcp_server.py
Server name: coverage-mcp-server
Tools exposed: check_coverage, get_claim_status
SDK used: mcp (Python MCP SDK v1.29.0), via FastMCP

## SDK Version Note

The mcp package released a breaking v2.0.0 (July 2026) that removed mcp.server.fastmcp and FastMCP in favor of a new MCPServer API. This project pins mcp<2.0 (installed: 1.29.0) to keep using the documented FastMCP decorator-based API (@mcp.tool()), which remains stable on the 1.x branch.

## Client Registration (Claude Desktop)

Client: Claude Desktop (Windows)
Config location: claude_desktop_config.json, edited via Settings > Developer > Local MCP servers > Edit Config
Registration confirmed: Yes. After adding the mcpServers entry and restarting the app, Settings > Developer showed coverage-mcp-server with status "running", and the server logs confirmed a successful handshake (ListToolsRequest, ListPromptsRequest, ListResourcesRequest all returned results).

## Test 1: get_claim_status (Claude Desktop) - PASSED

Question asked: "Use the coverage-mcp-server's get_claim_status tool to check the status of claim C1001"

Tool call observed: Claude prompted "Claude wants to use get_claim_status from coverage-mcp-server" with an Allow Once / Always Allow permission dialog, confirming the tool was correctly identified and invoked.

Result returned: Status Pending, Member ID M1001, Plan ID P101, Procedure X-ray, Claim amount $250, Date filed April 1 2023 - an exact match to the Day 4 claims.csv source data. Response was near-instant.

## Test 2: check_coverage (Claude Desktop) - TIMED OUT

Question asked: "Use the coverage-mcp-server's check_coverage tool to check if physical therapy is covered under Silver HMO"

Tool call observed: The tool was correctly identified and invoked (server logs show CallToolRequest received), but Claude Desktop cancelled the call after its 4-minute client-side timeout.

Root cause (confirmed from server logs at %LOCALAPPDATA%\Claude\logs): check_coverage calls Day 10's vector_lookup(), which loads the all-MiniLM-L6-v2 sentence-transformers model. On this machine (8GB RAM, CPU-only, no GPU), that load takes roughly 4.5-5 minutes, exceeding the client's 4-minute timeout. The server logs confirm the tool DOES complete and return a result (Message from server: id=4 result(1 blocks)) - just ~45-90 seconds after the client already gave up waiting.

Fixes attempted: lazy-loading the model so it only loads on first tool use (kept - lets the server start instantly); forcing HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE to skip Hugging Face network round-trips; making the coverage.db and chroma_data paths absolute; and loading the model eagerly at server startup (reverted - this made the server itself fail to start, since the startup then also exceeded the client's connect timeout). None brought the load under the 4-minute window on this hardware.

## Test 3: Cross-Client Verification (GitHub Copilot Chat) - BOTH TOOLS PASSED

To confirm the server itself is correct (and that the timeout above is a hardware/timeout-window issue rather than a code bug), the same server was registered with GitHub Copilot Chat in VS Code (via VS Code's dedicated mcp.json configuration).

check_coverage: Correctly invoked with input plan_name = "Silver HMO", question = "Is physical therapy covered?". Returned the Silver HMO structured plan data ($1,500 deductible, 20% copay) combined with the top relevant policy chunks from vector_lookup(). No chunk specifically mentioned physical therapy (a known data gap since Day 9), so the client correctly told the member to contact support rather than guessing.

get_claim_status: Correctly invoked with input claim_id = "C1001", returning {'claim_id': 'C1001', 'member_id': 'M1001', 'plan_id': 'P101', 'procedure': 'X-ray', 'claim_amount': 250, 'status': 'Pending', 'date_filed': '2023-04-01 00:00:00'} - again an exact match to source data.

This confirms both tools, the manifest, and the vector_lookup + plans-table integration are all implemented correctly.

## Additional Observation: Cline

The same server was also registered with Cline (VS Code extension). Registration succeeded (green connected status after a lazy-loading fix that prevented a startup timeout), and tools were discovered. However, when asked coverage questions - both implicitly and with the MCP tool named explicitly - Cline's free ox-alpha model chose to answer using its own built-in terminal tools (running sqlite3 queries against coverage.db directly) rather than invoking the registered MCP tool.

## Summary

| Client | check_coverage | get_claim_status |
|---|---|---|
| Claude Desktop | Timed out (model load exceeds 4-min client timeout) | Passed |
| GitHub Copilot Chat | Passed | Passed |
| Cline | Tool not selected by model | Tool not selected by model |

Across three MCP clients, registration and tool discovery worked every time. Both tools were verified working end-to-end. Two distinct client-side realities emerged that are worth noting for real MCP deployments: (1) clients enforce their own tool-call timeouts, which a slow local model load can exceed regardless of server correctness, and (2) automatic tool selection is not guaranteed when a client has competing built-in tools, even with the MCP tool named explicitly in the prompt.