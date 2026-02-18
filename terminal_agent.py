#!/usr/bin/env python3
# terminal_agent.py — Enterprise Terminal Agent v3
# - Project-only sandbox
# - Server auto-detect + healthcheck
# - Background server start (no hanging)
# - Hard-coded preferred workflow for THIS project: make run + scripts/smoke_test.py
# - Blocks flask run / unittest (wrong for this repo)
# - Session memory + output summarizer

import os
import sys
import json
import shlex
import socket
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

console = Console()

PROJECT_ROOT = Path.cwd()
SESSION_FILE = PROJECT_ROOT / ".agent_session.json"
MODEL = "gpt-4o-mini"

# Allowed command prefixes
ALLOWED_PREFIXES = [
    "ls", "pwd", "cat", "sed", "grep", "find", "head", "tail",
    "python3", "pip3", "make", "echo", "curl"
]

# Hard block dangerous + wrong-for-project commands
BLOCKED_TOKENS = {
    "sudo", "rm", "shutdown", "reboot", "killall", "mkfs", "dd",
    ">:",
    "curl|bash", "wget|bash",
    "lsof",
    "flask run",
    "python3 -m flask",
    "unittest",
}

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def load_session() -> Dict[str, Any]:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"history": []}
    return {"history": []}


def save_session(session: Dict[str, Any]) -> None:
    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def is_server_running(host: str = SERVER_HOST, port: int = SERVER_PORT) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def http_status_ok(url: str) -> bool:
    # Use curl (allowed) to check server responsiveness without extra deps
    try:
        p = subprocess.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' {shlex.quote(url)}",
            shell=True,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
        )
        code = (p.stdout or "").strip()
        return code == "200"
    except Exception:
        return False


def is_allowed(cmd: str) -> bool:
    lowered = cmd.lower()
    for tok in BLOCKED_TOKENS:
        if tok in lowered:
            return False
    parts = shlex.split(cmd)
    if not parts:
        return False
    return parts[0] in ALLOWED_PREFIXES


def run_command(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        shell=True,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
    )


def start_server_background() -> subprocess.Popen:
    # Start via make run but in background and capture output
    # Use a log file so we can inspect if needed
    log_path = PROJECT_ROOT / ".server.log"
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        "make run",
        shell=True,
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=log_f,
        text=True,
    )
    return proc


def stop_process(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def build_system_prompt(goal: str, session: Dict[str, Any], server_running: bool) -> str:
    recent = session.get("history", [])[-6:]
    return f"""
You are a SAFE terminal assistant for THIS project.

Project root: {PROJECT_ROOT}
This project uses:
- Server start: `make run` (Flask via app.py)
- Tests: `python3 scripts/smoke_test.py`
- Healthcheck: GET http://{SERVER_HOST}:{SERVER_PORT}/ should return 200

Hard rules:
- DO NOT use `flask run` or `python -m flask`.
- DO NOT use unittest discovery.
- Prefer `make` commands and existing scripts in /scripts.
- Only propose safe commands with these prefixes: {", ".join(ALLOWED_PREFIXES)}
- If server_running is true, do NOT propose starting it.

User goal:
{goal}

Recent history:
{json.dumps(recent, indent=2, ensure_ascii=False)}

Return STRICT JSON only:
{{
  "summary": "one sentence plan",
  "commands": [
    {{"cmd": "command", "rationale": "why"}}
  ],
  "notes": "short note"
}}
""".strip()


def propose_commands(client: OpenAI, goal: str, session: Dict[str, Any], server_running: bool) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": build_system_prompt(goal, session, server_running)},
        {"role": "user", "content": goal},
    ]
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,
    )
    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end + 1])
        raise


def ai_summarize_output(client: OpenAI, goal: str, combined_output: str) -> str:
    messages = [
        {"role": "system", "content": "Summarize the terminal output and recommend next step. Be short and practical."},
        {"role": "user", "content": f"Goal: {goal}\n\nTerminal output:\n{combined_output}"},
    ]
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def smart_plan_if_goal_matches(goal: str, server_running: bool) -> Dict[str, Any]:
    g = goal.lower()
    if ("start" in g and "server" in g and "smoke" in g) or ("run smoke" in g and "server" in g):
        cmds = []
        if not server_running:
            cmds.append({"cmd": "__START_SERVER_BG__", "rationale": "Start server in background via make run"})
            cmds.append({"cmd": f"curl -s -o /dev/null -w '%{{http_code}}' http://{SERVER_HOST}:{SERVER_PORT}/", "rationale": "Healthcheck server returns 200"})
        cmds.append({"cmd": "python3 scripts/smoke_test.py", "rationale": "Run the 5 smoke tests"})
        return {
            "summary": "Start server (if needed), verify health, run smoke tests.",
            "commands": cmds,
            "notes": "Server start is handled in background to avoid blocking the terminal."
        }
    return {}


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]ERROR:[/red] OPENAI_API_KEY is not set.")
        sys.exit(1)

    if len(sys.argv) < 2:
        console.print("Usage: python3 terminal_agent.py \"your goal\"")
        sys.exit(2)

    goal = " ".join(sys.argv[1:]).strip()
    session = load_session()
    server_running = is_server_running()

    console.print(Panel(
        f"[bold]Goal:[/bold] {goal}\n[bold]Project:[/bold] {PROJECT_ROOT}\n[bold]Server running:[/bold] {server_running}",
        title="Terminal Agent"
    ))

    client = OpenAI(api_key=api_key)

    # Prefer hardcoded smart plan for known workflows
    proposal = smart_plan_if_goal_matches(goal, server_running)
    if not proposal:
        proposal = propose_commands(client, goal, session, server_running)

    console.print(Panel(
        f"[bold]Plan:[/bold] {proposal.get('summary','')}\n[bold]Notes:[/bold] {proposal.get('notes','')}",
        title="AI Proposal"
    ))

    commands = proposal.get("commands", [])
    if not commands:
        console.print("[yellow]No commands proposed.[/yellow]")
        sys.exit(0)

    # Validate commands (special token allowed: __START_SERVER_BG__)
    validated: List[Dict[str, str]] = []
    for item in commands:
        cmd = str(item.get("cmd", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not cmd:
            continue

        if cmd == "__START_SERVER_BG__":
            validated.append({"cmd": cmd, "rationale": rationale})
            continue

        if server_running and cmd in ("make run", "./scripts/dev.sh"):
            continue

        if not is_allowed(cmd):
            console.print(Panel(f"[red]Blocked or not allowed command:[/red]\n{cmd}", title="Safety"))
            sys.exit(4)

        validated.append({"cmd": cmd, "rationale": rationale})

    console.print(Syntax(json.dumps(validated, indent=2, ensure_ascii=False), "json"))

    if not Confirm.ask("Execute these commands now?", default=False):
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    combined_parts: List[str] = []
    server_proc: subprocess.Popen = None

    for i, c in enumerate(validated, start=1):
        cmd = c["cmd"]
        rationale = c["rationale"]

        console.print(Panel(f"[bold]{i}. {cmd}[/bold]\n{rationale}", title="Running"))

        if cmd == "__START_SERVER_BG__":
            server_proc = start_server_background()
            # Wait up to 10s for server to become healthy
            url = f"http://{SERVER_HOST}:{SERVER_PORT}/"
            ok = False
            for _ in range(20):
                time.sleep(0.5)
                if http_status_ok(url):
                    ok = True
                    break
            out = f"Started server in background (pid={server_proc.pid}). Healthcheck: {'OK' if ok else 'NOT READY'}"
            console.print(Panel(out, title="server"))
            combined_parts.append(out)
            session.setdefault("history", []).append({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "goal": goal,
                "command": "make run (background)",
                "exit_code": 0,
                "stdout_preview": out[:600],
                "stderr_preview": "",
            })
            save_session(session)
            continue

        result = run_command(cmd)
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stdout:
            console.print(Panel(stdout[:4000], title="stdout"))
        if stderr:
            console.print(Panel(stderr[:4000], title="[yellow]stderr[/yellow]"))

        combined = f"$ {cmd}\n(exit={result.returncode})\n"
        if stdout:
            combined += f"\n[stdout]\n{stdout}\n"
        if stderr:
            combined += f"\n[stderr]\n{stderr}\n"
        combined_parts.append(combined)

        session.setdefault("history", []).append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "goal": goal,
            "command": cmd,
            "exit_code": result.returncode,
            "stdout_preview": stdout[:600],
            "stderr_preview": stderr[:600],
        })
        save_session(session)

        if result.returncode != 0:
            console.print(Panel(f"Command failed with exit code {result.returncode}. Stopping.", title="[red]Stopped[/red]"))
            break

    combined_output = "\n".join(combined_parts).strip()

    # Summarize output and propose next step
    try:
        analysis = ai_summarize_output(client, goal, combined_output)
        console.print(Panel(analysis, title="AI Analysis"))
    except Exception as e:
        console.print(Panel(str(e), title="[yellow]AI analysis failed[/yellow]"))

    # Optional: if we started server in background, keep it running and tell user how to stop
    if server_proc is not None:
        console.print(Panel(
            "Server is running in the background.\n"
            "To stop it, find PID in .server.log or run: `lsof` is blocked here; easiest is to stop it from the terminal where you started it.\n"
            "Alternative: restart your terminal session or stop by PID manually (outside this agent).",
            title="Note"
        ))

    console.print("[green]Done.[/green]")


if __name__ == "__main__":
    main()
