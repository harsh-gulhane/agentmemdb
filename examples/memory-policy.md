# Memory policy prompt

Agents use memory more consistently when they are told when to save and when to search. Paste the policy below into your agent's instructions file (`CLAUDE.md` for Claude Code, `AGENTS.md` for omp, Codex and others), or put a shorter version in the `instructions` key of the agentmemdb config file so every connected client receives it.

```markdown
## Long-term memory (agentmemdb)

You have a long-term memory shared with my other AI agents, through the `memory` MCP server.

At the start of a task:
- If I mention past work, a person, a service or a ticket, call `search_memory` (or `find_by_entity`) before answering.
- If a result belongs to a thread, call `get_thread` for the full history.

After each exchange that produced something worth keeping:
- Call `save_memory` with a short topic and a concise summary: what was asked, what you found or did, decisions and their reasons, and key facts (names, IDs, numbers, links).
- Choose a category: decision, incident, research, project, howto, config, person or conversation.
- Set importance: critical for incidents and outages, high for decisions and changes, normal for general work, low for minor notes.
- Add entities for the people, services, repos and tickets involved, e.g. [{"type":"service","value":"billing-api"}].
- Use the same thread_id for memories about the same piece of work.
- If save_memory reports possible duplicates, prefer `append_memory` on the existing memory next time.

Do not save:
- Greetings, acknowledgements or anything with no lasting value.
- Secrets such as passwords, tokens or private keys.
```

## Shorter config version

```json
{
  "instructions": "Search memory before answering questions about past work. After each non-trivial exchange, save a concise memory of decisions (with their reasons), findings and facts worth keeping. Use importance high for decisions and critical for incidents. Never save secrets."
}
```
