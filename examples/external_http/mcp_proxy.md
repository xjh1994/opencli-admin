# Bridging external_http to MCP

The `external_http` processor speaks plain HTTP, not MCP. MCP (Model
Context Protocol, anthropic.com/news/model-context-protocol) is the
emerging open standard for agent ↔ tool wiring -- a different layer of
the stack. They compose cleanly, though, and this note sketches how.

## Two integration shapes

### A. MCP server *behind* an external_http backend (recommended)

Your agent backend (e.g. `pydantic_ai_tagger.py` or `anthropic_tagger.py`)
consumes MCP servers as **tools**. opencli-admin still talks to the
backend over plain HTTP via `external_http`.

```
opencli-admin ──HTTP──▶ agent backend ──MCP──▶ external tools
                              │                  ├─ Brave Search MCP
                              │                  ├─ GitHub MCP
                              │                  └─ filesystem MCP
                              ▼
                       Anthropic / OpenAI / local LLM
```

This is the natural composition: `external_http` is the **dispatch** layer
(opencli-admin → some agent), MCP is the **tool plane** (agent → external
capabilities). Most production agent stacks end up here.

Wiring example (Pydantic AI):

```python
# in your backend's _build_agent()
from pydantic_ai.mcp import MCPServerStdio

brave = MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-brave-search"])
agent = Agent(model, mcp_servers=[brave], output_type=Enrichment)
```

### B. opencli-admin as an MCP client (future, requires RFC)

opencli-admin itself becomes an MCP client and the agent backend exposes
an MCP server. This means changing opencli-admin's pipeline: it pulls
the agent's capabilities, sends records as MCP messages, and receives
typed responses.

This is **out of scope** for the `external_http` processor. It would be
a separate processor (`mcp_client`), tracked as a v2 RFC. For now,
shape A covers the practical need.

## Why not bake MCP into the contract today

- MCP's transport (stdio / HTTP+SSE / streamable HTTP) is still
  stabilizing across SDKs as of 2026-05.
- Many production agent backends (dify, langflow, n8n) don't yet speak
  MCP. Requiring it would shrink the addressable backend set.
- Plain HTTP + JSON keeps the contract universal. Agents that *do* use
  MCP layer it underneath their HTTP surface (shape A) with zero
  changes to opencli-admin.

## See also

- `anthropic_tagger.py` -- minimal HTTP backend; can be extended to call
  MCP servers as Anthropic's `tools=[...]` parameter once their SDK ships
  first-class MCP client support.
- `pydantic_ai_tagger.py` -- Pydantic AI already has `mcp_servers=[...]`
  on `Agent`. The example shows the bare bones; uncomment one line to
  add MCP tools.
