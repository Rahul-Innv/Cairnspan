# Claude Code Handoff

Use this when Claude Code should delegate a bounded task to Codex.

```text
Use the Cairnspan skill at:
<path to Cairnspan>\skills\cairnspan

Goal:
Start a fresh Codex CLI session for the task below using the user's local Codex OAuth-backed session, capture the Codex thread id, event JSONL, transcript, final answer, and Cairnspan summary, then report the result. Do not assume Claude Code and Codex share skills, MCP servers, or auth; verify failures from the Cairnspan logs.

Target workspace:
<absolute path>

Codex capability required:
<for example: $imagegen, OpenAI Docs MCP, Playwright MCP, web search, repo edits>

Permissions:
<read-only | workspace-write>

Task for Codex:
<bounded prompt>

Request file:
<absolute path to UTF-8 text file containing the bounded prompt>

Use:
python "<path to Cairnspan>\skills\cairnspan\scripts\start_codex_session.py" --cwd "<target workspace>" --prompt-file "<request file>" --sandbox <read-only|workspace-write> --timeout-seconds 120 --max-output-bytes 1048576 --execute

After it finishes, inspect:
- cairnspan-summary.json
- final.md
- events.jsonl
- transcript.log

Return:
- whether Codex started
- thread id if present
- files/artifacts produced
- whether the required Codex capability was available
- exact blocker if it failed
```
