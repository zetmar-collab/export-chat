#!/usr/bin/env python3
"""Export a Claude Code session log (.jsonl) to a Markdown transcript.

Reads ~/.claude/projects/<encoded working directory>/<session id>.jsonl and writes
chat-exports/chat-export-YYYY-MM-DD-HHMMSS.md (never overwriting an existing file).

Included: real user messages, assistant text, tool calls and their results.
Excluded: thinking blocks, hook/system records, <system-reminder> blocks, sub-agent
(sidechain) records, and everything after the last real user message (that is the export
request itself, plus the tool calls used to run this script).

Standard library only. Usage: python export_session.py --help
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED]"),
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*(?:bearer|basic|token)\s+)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                r"github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
                r"xox[abprs]-[A-Za-z0-9-]{10,}|hf_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9*]{10,})"),
     "[REDACTED]"),
    (re.compile(r"(?i)\b((?:api[_-]?key|secret|token|password|passwd|pwd|cookie|client[_-]?secret)"
                r"[\"']?\s*[:=]\s*[\"']?)([^\s\"',;]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)([^\s@/]+)(@)"), r"\1[REDACTED]\3"),
]


class Stats:
    def __init__(self) -> None:
        self.user_turns = 0
        self.assistant_turns = 0
        self.tool_uses = 0
        self.truncated = 0
        self.redactions = 0
        self.skipped_images = 0


def redact(text: str, stats: Stats) -> str:
    for pattern, repl in SECRET_PATTERNS:
        text, n = pattern.subn(repl, text)
        stats.redactions += n
    return text


def fence(text: str, lang: str = "") -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def clip(text: str, limit: int, stats: Stats) -> str:
    if limit > 0 and len(text) > limit:
        stats.truncated += 1
        return text[:limit] + f"\n... (full content truncated in export; {len(text)} characters total)"
    return text


def encode_dir(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def find_session_file(projects: Path, cwd: str, session: str | None) -> Path:
    if session:
        p = Path(session)
        if p.is_file():
            return p
        sid = p.stem
        hits = sorted(projects.glob(f"*/{sid}.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
        if hits:
            return hits[0]
        sys.exit(f"error: session '{session}' not found under {projects}")
    folder = projects / encode_dir(cwd)
    files = sorted(folder.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True) if folder.is_dir() else []
    if not files:
        sys.exit(f"error: no session logs in {folder}. Pass --session <id or path>.")
    return files[0]


def block_text(content) -> str:
    """Flatten a message/tool_result content value to text."""
    if isinstance(content, str):
        return content
    parts = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
        elif isinstance(b, dict) and b.get("type") == "image":
            parts.append("[image]")
    return "\n".join(parts)


SYSTEM_BLOCK = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def user_prompt_text(message: dict, stats: Stats) -> str | None:
    """Return the text of a real user prompt, or None for tool results / injected context."""
    content = message.get("content")
    if isinstance(content, str):
        text = content
    else:
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content or []):
            return None
        parts = []
        for b in content or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif b.get("type") == "image":
                stats.skipped_images += 1
                parts.append("[image attached]")
        text = "\n".join(parts)
    text = SYSTEM_BLOCK.sub("", text).strip()
    return text or None


def load_records(path: Path, include_sidechains: bool):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant"):
                continue
            if rec.get("isSidechain") and not include_sidechains:
                continue
            if not isinstance(rec.get("message"), dict):
                continue
            yield rec


def build_events(records: list[dict], stats: Stats):
    """Turn records into ordered events: ('user'|'assistant'|'tool', payload)."""
    events = []
    results = {}
    for rec in records:
        if rec["type"] == "user" and isinstance(rec["message"].get("content"), list):
            for b in rec["message"]["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    results[b.get("tool_use_id")] = b

    for rec in records:
        msg = rec["message"]
        if rec["type"] == "user":
            if rec.get("isMeta"):
                continue
            text = user_prompt_text(msg, stats)
            if text is not None:
                events.append(("user", text, rec.get("timestamp")))
            continue
        content = msg.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for b in content or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                events.append(("assistant", b["text"], rec.get("timestamp")))
            elif b.get("type") == "tool_use":
                res = results.get(b.get("id"))
                events.append(("tool", (b, res), rec.get("timestamp")))
    return events


def format_input(inp) -> str:
    """Readable tool input: JSON, but multi-line strings are shown with real line breaks."""
    if not isinstance(inp, dict):
        return json.dumps(inp, ensure_ascii=False, indent=2)
    simple = {k: v for k, v in inp.items() if not (isinstance(v, str) and "\n" in v)}
    multi = {k: v for k, v in inp.items() if isinstance(v, str) and "\n" in v}
    parts = [json.dumps(simple, ensure_ascii=False, indent=2)] if simple or not multi else []
    for key, value in multi.items():
        parts.append(f"--- {key} ---\n{value}")
    return "\n".join(parts)


def render(events, cwd: str, source: Path, args, stats: Stats) -> str:
    out = ["# Chat export", ""]
    if args.compacted_note:
        out += ["> Note: earlier conversation history may be unavailable because the session "
                "context was compacted.", ""]
    out += [
        f"- Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- Tool: Claude Code",
        f"- Working directory: {cwd}",
        "- Scope: Full available conversation history in this session",
        f"- Source: session log `{source.name}`",
        "",
        "## Conversation",
        "",
    ]
    last_kind = None
    for kind, payload, _ts in events:
        if kind == "user":
            stats.user_turns += 1
            out += ["### User", "", redact(payload, stats), ""]
        elif kind == "assistant":
            text = redact(payload, stats)
            if last_kind == "assistant":
                out += [text, ""]  # continuation of the same response
            else:
                stats.assistant_turns += 1
                out += ["### Assistant", "", text, ""]
        else:
            block, res = payload
            stats.tool_uses += 1
            inp = redact(format_input(block.get("input", {})), stats)
            inp = clip(inp, args.max_input, stats)
            if res is None:
                result_text = "(no result recorded)"
            else:
                result_text = redact(block_text(res.get("content")), stats)
                result_text = clip(result_text, args.max_result, stats)
            out += [
                "### Tool use", "",
                f"- Tool: `{block.get('name', 'unknown')}`",
                "- Input:", "", fence(inp), "",
                "- Result:", "", fence(result_text or "(empty)"), "",
            ]
        last_kind = kind
    return "\n".join(out).rstrip() + "\n"


def write_unique(directory: Path, base: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    n = 0
    while True:
        name = f"{base}.md" if n == 0 else f"{base}-{n}.md"
        target = directory / name
        try:
            with open(target, "x", encoding="utf-8", newline="\n") as fh:  # 'x' never overwrites
                fh.write(text)
            return target
        except FileExistsError:
            n += 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", help="session id or path to a .jsonl file (default: newest log for the cwd)")
    ap.add_argument("--cwd", default=os.getcwd(), help="working directory the session ran in (default: current)")
    ap.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--out-dir", help="output folder (default: <cwd>/chat-exports)")
    ap.add_argument("--max-input", type=int, default=3000, help="max characters of a tool input (0 = no limit)")
    ap.add_argument("--max-result", type=int, default=4000, help="max characters of a tool result (0 = no limit)")
    ap.add_argument("--include-sidechains", action="store_true", help="also include sub-agent records")
    ap.add_argument("--keep-trailing", action="store_true",
                    help="keep everything after the last user message (default: drop it)")
    ap.add_argument("--compacted-note", action="store_true", help="add the context-compaction note")
    args = ap.parse_args()

    source = find_session_file(Path(args.projects_dir), args.cwd, args.session)
    stats = Stats()
    records = list(load_records(source, args.include_sidechains))
    events = build_events(records, stats)

    if not args.keep_trailing:
        last_user = max((i for i, e in enumerate(events) if e[0] == "user"), default=None)
        if last_user is not None:
            events = events[: last_user + 1]
    if not events:
        sys.exit(f"error: no conversation content found in {source}")

    text = render(events, args.cwd, source, args, stats)
    base = "chat-export-" + datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path(args.cwd) / "chat-exports"
    target = write_unique(out_dir, base, text)

    print(f"file: {target.resolve()}")
    print(f"source: {source}")
    print(f"user turns: {stats.user_turns}")
    print(f"assistant responses: {stats.assistant_turns}")
    print(f"tool calls: {stats.tool_uses}")
    print(f"truncated items: {stats.truncated}")
    print(f"redactions: {stats.redactions}")


if __name__ == "__main__":
    main()
