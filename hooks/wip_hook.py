#!/usr/bin/env python3
"""WIP plugin hook entry point.

Subcommands:
  inject    — SessionStart: emit prior session recap(s) as additional context.
  capture   — Stop / PreCompact / SessionEnd: kick off (backgrounded) haiku
              synthesis to update the current session's WIP file.
  worker    — Internal: the actual haiku-driven file write. Spawned detached
              from `capture` so the parent hook returns immediately.

All paths live under ~/.claude/wip/<sanitized-cwd>/<session-id>.md, where
<sanitized-cwd> is the cwd with `/` → `-` (matching Claude Code's own
projects/ directory naming).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WIP_ROOT = Path.home() / ".claude" / "wip"
STOP_DEBOUNCE_SECONDS = 600  # 10 minutes between haiku calls on Stop
KEEP_TOP_N = 10              # keep this many session files per project
LOAD_TOP_N = 5               # inject this many on SessionStart-without-match
TRANSCRIPT_TAIL_LINES = 800  # how much of the transcript to feed haiku
RE_ENTRANCY_FLAG = "WIP_HOOK_DISABLED"


def sanitize_cwd(cwd: str) -> str:
    """Convert a cwd to the leading-dash dashed form used by Claude Code.

    Mirrors the convention used in ~/.claude/projects/ — e.g.
    `/Users/joelthor/code/foo` → `-Users-joelthor-code-foo`.

    Args:
        cwd: Absolute working-directory path.

    Returns:
        Filesystem-safe directory name.
    """
    return "-" + cwd.lstrip("/").replace("/", "-")


def project_dir(cwd: str) -> Path:
    """Resolve the per-project WIP directory under ~/.claude/wip/.

    Args:
        cwd: Absolute working-directory path.

    Returns:
        Path to the project's WIP dir (not created).
    """
    return WIP_ROOT / sanitize_cwd(cwd)


def now_iso() -> str:
    """Return the current UTC time formatted for WIP file headers.

    Returns:
        ISO-ish timestamp string, e.g. `2026-05-19 22:15:03 UTC`.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read_hook_stdin() -> dict[str, Any]:
    """Parse the hook event payload from stdin.

    Claude Code delivers a JSON payload on stdin to every hook invocation.
    On parse failure we return an empty dict and let callers fall through.

    Returns:
        Hook payload dict. Empty on parse failure. Common keys: `cwd`,
        `session_id`, `transcript_path`, `hook_event_name`.
    """
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def cmd_inject() -> int:
    """Run the SessionStart inject path: emit recap(s), prune stale files.

    On a session that matches an existing `<session-id>.md` (resumption),
    that file's contents are emitted prefixed with a Session Resumption
    header. Otherwise the top-N (LOAD_TOP_N) most recent files for this
    cwd are emitted as Prior Session Recaps. After loading, any files
    beyond KEEP_TOP_N (by mtime) are unlinked — except the currently
    resumed file, which is always preserved.

    Returns:
        Process exit code (always 0).
    """
    if os.environ.get(RE_ENTRANCY_FLAG) == "1":
        return 0
    payload = read_hook_stdin()
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id", "")

    pdir = project_dir(cwd)
    if not pdir.is_dir():
        return 0

    current = pdir / f"{session_id}.md" if session_id else None
    files = sorted(
        (p for p in pdir.iterdir() if p.is_file() and p.suffix == ".md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if current and current.exists():
        content = current.read_text().strip()
        if content:
            print(f"## WIP Session Resumption\n\n{content}\n")
    elif files:
        chunks = [text for f in files[:LOAD_TOP_N] if (text := f.read_text().strip())]
        if chunks:
            joined = "\n\n---\n\n".join(chunks)
            print(
                "## WIP — Prior Session Recaps\n\n"
                f"For context, here is what happened in the last {len(chunks)} "
                f"session(s) for this project. Each block is one session.\n\n"
                f"{joined}\n"
            )

    # Prune after loading. Never delete the resumed session's file, even
    # if its mtime ranks it outside the top-N — its "Done this session"
    # history must survive a sparse-resumption gap.
    for stale in files[KEEP_TOP_N:]:
        if current is not None and stale == current:
            continue
        with contextlib.suppress(OSError):
            stale.unlink()
    return 0


def cmd_capture(event: str) -> int:
    """Handle Stop / PreCompact / SessionEnd: spawn a detached worker.

    The worker (a re-entrant call into this same script) runs the haiku
    synthesis in a new session group with closed std streams so it
    survives the parent hook's exit — critical for SessionEnd, where the
    main process is dying. For Stop, the worker is short-circuited if
    the WIP file's mtime is younger than STOP_DEBOUNCE_SECONDS (Stop
    fires per-turn; debouncing prevents per-reply haiku spend).

    Args:
        event: Hook event name (`Stop`, `PreCompact`, or `SessionEnd`).

    Returns:
        Process exit code (always 0; spawn errors are not surfaced since
        a failing hook would degrade the user's session for no benefit).
    """
    if os.environ.get(RE_ENTRANCY_FLAG) == "1":
        return 0
    payload = read_hook_stdin()
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path", "")

    if not session_id:
        return 0

    pdir = project_dir(cwd)
    pdir.mkdir(parents=True, exist_ok=True)
    wip_file = pdir / f"{session_id}.md"

    if event == "Stop" and wip_file.exists():
        age = time.time() - wip_file.stat().st_mtime
        if age < STOP_DEBOUNCE_SECONDS:
            return 0

    env = os.environ.copy()
    env[RE_ENTRANCY_FLAG] = "1"
    subprocess.Popen(
        [
            sys.executable,
            __file__,
            "worker",
            "--cwd", cwd,
            "--session-id", session_id,
            "--transcript", transcript_path,
            "--event", event,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
        close_fds=True,
    )
    return 0


def git_log(cwd: str) -> str:
    """Capture recent git log for inclusion in the haiku prompt.

    Args:
        cwd: Directory to run git in.

    Returns:
        Up to 15 lines of `git log --oneline`, or a sentinel string when
        the directory is not a git repo or git is unavailable.
    """
    try:
        return subprocess.check_output(
            ["git", "-C", cwd, "log", "--oneline", "-n", "15"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
    except Exception:
        return "(not a git repo or git unavailable)"


def tail_transcript(transcript_path: str, lines: int) -> str | None:
    """Write the last N lines of a transcript file to a tempfile.

    The full transcript jsonl can be huge — feeding all of it to Haiku
    is token-wasteful and slow. We tail it instead, then hand Haiku the
    tempfile path to Read selectively.

    Args:
        transcript_path: Absolute path to a transcript jsonl, or "".
        lines: How many trailing lines to capture.

    Returns:
        Path to the new tempfile, or None when the source is missing or
        the tail command fails. Caller is responsible for unlinking.
    """
    if not transcript_path or not Path(transcript_path).is_file():
        return None
    try:
        out = subprocess.check_output(
            ["tail", "-n", str(lines), transcript_path],
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    tf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", prefix="wip-tail-", delete=False
    )
    tf.write(out)
    tf.close()
    return tf.name


def extract_started(existing: str) -> str:
    """Find the `Started:` line in an existing WIP file body.

    Args:
        existing: Full text of the prior WIP file (may be empty).

    Returns:
        The preserved start timestamp, or `now_iso()` when none is
        found (first capture for the session).
    """
    for line in existing.splitlines():
        if line.startswith("Started:"):
            return line.removeprefix("Started:").strip()
    return now_iso()


def build_prompt(
    session_id: str,
    cwd: str,
    event: str,
    existing: str,
    git_log_text: str,
    transcript_file: str | None,
) -> str:
    """Build the haiku synthesis prompt for one capture.

    The prompt instructs haiku to PRESERVE the existing
    `## Done this session` block (append-only contract) and to REPLACE
    `## Known next steps` and `## Notes`. Append-only is enforced via
    prose only; haiku may occasionally drift, so this is a best-effort
    guarantee rather than a hard one.

    Args:
        session_id: Full session uuid.
        cwd: Project working directory.
        event: Triggering hook event name (`Stop`/`PreCompact`/
            `SessionEnd`/`manual`).
        existing: Prior WIP file content (may be empty).
        git_log_text: Output of recent `git log --oneline`.
        transcript_file: Path to a tailed-transcript tempfile, or None
            when transcript is unavailable.

    Returns:
        The complete prompt string to pass to `claude -p`.
    """
    project_name = Path(cwd).name
    short_id = session_id[:8]
    started = extract_started(existing)
    transcript_block = (
        f"3. **Conversation transcript tail** (jsonl, ~{TRANSCRIPT_TAIL_LINES} most recent lines):\n"
        f"   `{transcript_file}` — use the Read tool on this path. Scan for: commits made, "
        f"files edited, tests added, blockers mentioned, planned next steps."
        if transcript_file
        else "3. **Conversation transcript**: (not available for this run — work from inputs 1 + 2 only)"
    )
    existing_block = existing.strip() or "(no prior WIP file — first capture this session)"
    return (
        f"You are updating a session WIP recap file. Trigger: `{event}`.\n"
        f"Project: {project_name}   Session: {short_id}   cwd: {cwd}\n\n"
        f"## Inputs\n\n"
        f"1. **Existing WIP file** — PRESERVE the existing `## Done this session` list verbatim "
        f"and APPEND any newly-completed items. Never delete or rewrite already-recorded done items.\n"
        f"```\n{existing_block}\n```\n\n"
        f"2. **Recent git log** (use SHAs from here to annotate done items):\n"
        f"```\n{git_log_text}\n```\n\n"
        f"{transcript_block}\n\n"
        f"## Output\n\n"
        f"Produce ONLY the updated markdown — no commentary, no code fence wrapping, "
        f"no preface. Use exactly these section headers in this order:\n\n"
        f"```\n"
        f"# Session {short_id} — {project_name}\n"
        f"Started: {started}\n"
        f"Last updated: {now_iso()}\n"
        f"Source: {cwd}\n\n"
        f"## Done this session\n"
        f"- <terse item> [<sha-short>]\n"
        f"...\n\n"
        f"## Known next steps\n"
        f"- <terse item>\n"
        f"...\n\n"
        f"## Notes\n"
        f"<one-paragraph running context — replace fully each turn>\n"
        f"```\n\n"
        f"Be terse. Bullet items should fit on one line. Include short commit SHAs in brackets "
        f"after done items when the git log shows a matching commit. The `Known next steps` and "
        f"`Notes` sections are fully replaced each run (current understanding); `Done this session` "
        f"is append-only across runs in this same session."
    )


def _run_haiku_synthesis(prompt: str, timeout: float = 120.0) -> str:
    """Invoke haiku for WIP synthesis, preferring pcc when installed.

    Uses ``pcc ask`` when available: it runs in an isolated Claude Code
    config with CLAUDE.md suppressed, so no hooks, plugins, or session
    context can contaminate the output. Falls back to ``claude -p`` with
    ``--safe-mode`` and a stripped subprocess environment.

    Both paths apply identical tool restriction (``--allowedTools Read``,
    ``--safe-mode``, ``--permission-mode bypassPermissions``) so haiku
    cannot run arbitrary commands even if the prompt is injected.

    Args:
        prompt: Full synthesis prompt to send to haiku.
        timeout: Maximum seconds to wait for a response.

    Returns:
        Stripped stdout from the model, or "" on any failure.
    """
    # Strip session-identity env vars from both paths so a re-entrant
    # claude/pcc subprocess cannot inherit the parent session's identity.
    _SESSION_VARS = {
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_CHILD_SESSION",
        "CLAUDECODE",
        "AI_AGENT",
        "CODEX_COMPANION_SESSION_ID",
    }
    child_env = {k: v for k, v in os.environ.items() if k not in _SESSION_VARS}
    try:
        if shutil.which("pcc"):
            result = subprocess.run(
                [
                    "pcc", "ask", "--model", "haiku",
                    "--allowedTools", "Read",
                    "--safe-mode",
                    "--permission-mode", "bypassPermissions",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=child_env,
            )
        else:
            result = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--model", "haiku",
                    "--output-format", "text",
                    "--no-session-persistence",
                    "--safe-mode",
                    "--permission-mode", "bypassPermissions",
                    "--allowedTools", "Read",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=child_env,
            )
        return (result.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def cmd_worker(args: argparse.Namespace) -> int:
    """Run the actual haiku synthesis and write the WIP file.

    Detached child of `cmd_capture`. Spends ~few-thousand input tokens
    and ~few-hundred output tokens per call. On any haiku failure (timeout,
    missing binary, empty stdout) the existing file is preserved; only
    when there's no existing file do we write a deterministic fallback
    stub so that resumption still has something to inject.

    Args:
        args: Parsed argparse namespace with `cwd`, `session_id`,
            `transcript`, `event`.

    Returns:
        Process exit code (0 on success or on accepted-no-op).
    """
    pdir = project_dir(args.cwd)
    pdir.mkdir(parents=True, exist_ok=True)
    wip_file = pdir / f"{args.session_id}.md"

    existing = wip_file.read_text() if wip_file.exists() else ""
    log_text = git_log(args.cwd)
    transcript_file = tail_transcript(args.transcript, TRANSCRIPT_TAIL_LINES)

    prompt = build_prompt(
        session_id=args.session_id,
        cwd=args.cwd,
        event=args.event,
        existing=existing,
        git_log_text=log_text,
        transcript_file=transcript_file,
    )

    try:
        output = _run_haiku_synthesis(prompt)
    finally:
        if transcript_file:
            with contextlib.suppress(OSError):
                Path(transcript_file).unlink()

    if not output:
        if not wip_file.exists():
            short_id = args.session_id[:8]
            output = (
                f"# Session {short_id} — {Path(args.cwd).name}\n"
                f"Started: {now_iso()}\n"
                f"Last updated: {now_iso()}\n"
                f"Source: {args.cwd}\n\n"
                f"## Done this session\n(haiku unavailable; see git log)\n\n"
                f"## Known next steps\n(haiku unavailable)\n\n"
                f"## Notes\nRecent git log:\n```\n{log_text}\n```\n"
            )
        else:
            return 0

    if output.startswith("```"):
        lines = output.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        output = "\n".join(lines)

    wip_file.write_text(output.rstrip() + "\n")
    return 0


def main() -> int:
    """CLI entry point. Dispatches to inject/capture/worker.

    Returns:
        Process exit code. 0 on success; 1 on unknown subcommand
        (unreachable in practice because argparse rejects them first).
    """
    parser = argparse.ArgumentParser(prog="wip_hook")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inject")
    cap = sub.add_parser("capture")
    cap.add_argument("--event", required=True, choices=["Stop", "PreCompact", "SessionEnd"])
    work = sub.add_parser("worker")
    work.add_argument("--cwd", required=True)
    work.add_argument("--session-id", required=True)
    work.add_argument("--transcript", default="")
    work.add_argument("--event", required=True)
    args = parser.parse_args()

    if args.cmd == "inject":
        return cmd_inject()
    if args.cmd == "capture":
        return cmd_capture(args.event)
    if args.cmd == "worker":
        return cmd_worker(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
