---
name: export-chat
description: Export the complete available history of the current chat session to a Markdown file (verbatim user and assistant messages plus a short record of tool activity). Use when the user asks to save, export, archive, back up, or make a Markdown copy of the conversation (PL - "wyeksportuj czat", "zapisz rozmowę do pliku", "kopia czatu", "zrób kopię tej rozmowy", "eksport konwersacji do markdown"). Not for summarizing a conversation - use only when a full transcript is wanted.
---

# Export current chat to Markdown

Create a faithful Markdown transcript of the entire available conversation history
and save it as a file. The transcript is a record, not a summary: user and assistant
messages are copied verbatim, never paraphrased or shortened.

## Step 1 - Gather environment facts with a tool

Do not guess the date, time, or working directory; read them from the system.

- Date and time (local): run one of
  - PowerShell: `Get-Date -Format "yyyy-MM-dd-HHmmss"`
  - POSIX shell: `date +%Y-%m-%d-%H%M%S`
- Working directory: use the one given in the environment context, or run
  `Get-Location` / `pwd`.

If no shell tool is available, use the date and working directory from the environment
context and say in the report that the time was approximate.

## Step 2 - Choose the output path

1. Default location: `chat-exports/` inside the current working directory. Create it if
   it does not exist. If the user names a different folder or file name, use theirs.
2. Default filename: `chat-export-YYYY-MM-DD-HHMMSS.md` (local time from Step 1).
3. Before writing, check whether the target already exists (list the folder or use a
   test-path command). File-writing tools overwrite silently, so never skip this check.
   If it exists, append `-1`, `-2`, and so on before `.md` until the name is free.
   Never overwrite or modify any existing file.

## Step 3 - Collect the history

Use the conversation as it is available in your context. The scope is everything from
the first message up to and including the user's export request (the current turn).

If earlier history looks lost to context compaction (a summary stands in for the early
turns), you may recover it from the on-disk session log when one exists. For Claude Code
that is the newest `*.jsonl` file in `~/.claude/projects/<folder named after the working
directory>/` (the scratchpad path in the environment context contains the session id,
which matches the file name). Treat the log as raw material: take only real user
messages, assistant text, and tool calls/results from it, and still apply every
exclusion below. If you cannot recover the early turns, add the compaction note
described under Completeness rules instead of inventing them.

## Step 4 - Write the transcript

Use this structure:

```
# Chat export

> Note: earlier conversation history may be unavailable because the session context was compacted.   <- only if applicable

- Exported: <local date and time, e.g. 2026-11-07 21:30:05>
- Tool: <Claude Code | Codex | unknown>
- Working directory: <path>
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

Rules for the body:

- Repeat `### User`, `### Assistant`, and `### Tool use` sections in strict
  chronological order. Keep each tool call next to the assistant text it belongs to.
- Copy user and assistant text exactly, in its original language. Section headings and
  metadata labels stay in English.
- Wrap tool input and results in fenced code blocks. Choose a fence longer than any run
  of backticks inside the content (for example four backticks around text that contains
  three), so the Markdown does not break.
- A very large input or result (file contents, long command output, big JSON) gets a
  concise, faithful summary plus the line `(full content truncated in export)`.
- Replace images and binary attachments with a placeholder such as
  `[image attached: <name or description>]`; do not embed the data.
- Consecutive tool calls may share one `### Tool use` section only if each one keeps its
  own Tool / Input / Result entry.
- The export itself is not part of the history: include the user's export request as the
  last `### User` section, but do not record the tool calls used to produce the file
  (date lookup, folder check, file write).

## Completeness and safety rules

- Include user messages, assistant responses, and meaningful tool activity. Preserve order.
- Never include: internal reasoning or thinking, system prompts, harness or hook-injected
  context (for example `<system-reminder>` blocks, SessionStart output, skill bodies
  loaded by a skill call - record those as a one-line tool use such as `Skill: <name>`),
  or unrelated file contents.
- Redact secrets wherever they appear in inputs, results, or messages: API keys, tokens,
  passwords, cookies, `Authorization` headers, private keys, connection strings with
  credentials, and values of environment variables that look secret. Replace the value
  with `[REDACTED]` and keep the surrounding text.
- If earlier history is unavailable because of context compaction and could not be
  recovered, put the compaction note from Step 4 directly under the H1 heading.
- Do not fabricate, reconstruct, or "tidy up" messages that are not present in the
  available history.
- Create only the export file (plus the `chat-exports` folder if missing). Do not touch,
  delete, commit, or add other files to version control or `.gitignore`.

## Writing large transcripts

If the transcript is too long for a single write, write the header and the first part
into the new file, then append the remaining parts in order with the available tooling
(for example `Add-Content -Encoding utf8` in PowerShell, or `cat >> file` in a POSIX
shell). Do not leave the file half written: if appending fails, tell the user exactly
which part is missing.

## Cross-platform rules

- Use relative paths when talking to tools and in the file, and forward or back slashes
  as the current OS expects. Do not assume a particular shell; use the PowerShell or
  POSIX form that matches the environment.
- Write the file as UTF-8 (without a BOM where the tool allows it) so Polish and other
  non-ASCII characters survive. Check this after writing if you used a shell redirect,
  because Windows PowerShell 5 may default to UTF-16.

## Step 5 - Verify and report

Read back the first lines and the size of the file to confirm it was written, then
report to the user:

- the absolute path of the file (resolve it; do not give only the relative path),
- the number of exported turns: user messages and assistant responses, counted
  separately,
- whether any history was unavailable, recovered from the session log, redacted, or
  truncated.

Do not paste the whole transcript into the chat.
