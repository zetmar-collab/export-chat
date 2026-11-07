# export-chat

A skill for Claude Code and Codex that exports the current chat session to a Markdown file.

It writes a verbatim transcript of user and assistant messages, plus a short record of tool
activity, to `chat-exports/chat-export-YYYY-MM-DD-HHMMSS.md` in the current working directory.
Secrets are redacted, existing files are never overwritten, and the output is UTF-8.

Trigger phrases: "export the chat", "save this conversation to Markdown",
"wyeksportuj czat", "zapisz rozmowę do pliku", "kopia czatu".

## Install

Copy this folder's `SKILL.md` into a skill directory named `export-chat`:

```bash
# Claude Code
mkdir -p ~/.claude/skills/export-chat && cp SKILL.md ~/.claude/skills/export-chat/

# Codex
mkdir -p ~/.codex/skills/export-chat && cp SKILL.md ~/.codex/skills/export-chat/
```

Start a new session so the skill is picked up.
