# export-chat

A skill for Claude Code and Codex that exports the current chat session to a Markdown file.

It writes a verbatim transcript of user and assistant messages, plus a short record of tool
activity, to `chat-exports/chat-export-YYYY-MM-DD-HHMMSS.md` in the current working directory.
Secrets are redacted, existing files are never overwritten, and the output is UTF-8.

## Usage

Ask the agent in plain language. Trigger phrases include:

- "export the chat", "save this conversation to Markdown", "make a Markdown copy of this chat"
- "wyeksportuj czat", "zapisz rozmowę do pliku", "kopia czatu", "eksport konwersacji do markdown"

You can name your own folder or file name in the request; otherwise the default location above
is used. When it finishes, the agent reports the absolute path of the file, the number of
exported user and assistant turns, and whether any history was unavailable, recovered,
redacted, or truncated.

This skill is for a full transcript. For a summary of the conversation, ask for a summary instead.

## What the export looks like

```markdown
# Chat export

- Exported: 2026-11-07 21:30:05
- Tool: Claude Code
- Working directory: C:\Users\you\project
- Scope: Full available conversation history in this session

## Conversation

### User
<message verbatim>

### Assistant
<response verbatim>

### Tool use
- Tool: <tool name>
- Input: <relevant input, secrets redacted>
- Result: <relevant result or concise summary>
```

## Behavior

- **Verbatim, in order.** User and assistant text is copied exactly, in its original language;
  headings and metadata labels stay in English.
- **Real time and paths.** The date, time, and working directory are read from the system with
  a command (PowerShell or POSIX), not guessed.
- **No overwriting.** If the target file exists, `-1`, `-2`, and so on is appended to the name.
  The skill creates only the export file (and the `chat-exports` folder if missing).
- **Redaction.** API keys, tokens, passwords, cookies, `Authorization` headers, private keys,
  and credentialed connection strings are replaced with `[REDACTED]`.
- **Excluded.** Internal reasoning, system prompts, hook-injected context such as
  `<system-reminder>` blocks, and the bodies of loaded skills are left out.
- **Large content.** Very large tool inputs or results get a faithful summary marked
  `(full content truncated in export)`. Images and binary attachments become placeholders.
- **Safe Markdown.** Tool input and results are wrapped in code fences long enough to
  survive backticks inside the content.
- **Long transcripts** are written in parts and appended in order.

## Limitations

- The transcript is built from the conversation available in the model's context. If the
  session was compacted, the skill adds a note at the top. In Claude Code it may try to
  recover earlier turns from the session log (`~/.claude/projects/<folder>/<session>.jsonl`);
  if that fails, those turns are simply missing and the skill says so rather than inventing them.
- Redaction is pattern-based and best-effort. Check the exported file before sharing it.
- The export lands in your working directory, which may be a git repository. The skill does not
  touch `.gitignore` or commit the file; add `chat-exports/` to `.gitignore` yourself if needed.

## Install

Copy `SKILL.md` into a skill directory named `export-chat`:

```bash
# Claude Code
mkdir -p ~/.claude/skills/export-chat && cp SKILL.md ~/.claude/skills/export-chat/

# Codex
mkdir -p ~/.codex/skills/export-chat && cp SKILL.md ~/.codex/skills/export-chat/
```

Start a new session so the skill is picked up.
