#!/usr/bin/env python3
"""
kacangje REPL — interactive prompt with slash commands.

Mirrors the OpenCode / Claude Code UX (slash menu, skills, sessions) but for
SME office work, not coding. Stdlib only — runs anywhere Python 3.8+ runs.

Slash commands:
  /help            tunjuk bantuan
  /skills          senarai skill (taip /<nama-skill> untuk guna)
  /actions         senarai action (gaji, invois, sebut harga ...)
  /gaji ...        kira gaji terus
  /cari <soalan>   carian web
  /ingat <fakta>   simpan fakta ke brain memory
  /model [nama]    tunjuk / tukar model
  /bersih          kosongkan sesi
  /keluar          keluar
Taip teks biasa untuk berbual dengan AI (tools auto-trigger).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Make `lib` and project root importable regardless of how we're launched.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for p in (str(_ROOT), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib.tools import (
    build_messages, web_search, remember, calculate, match_intent,
)
from lib.skills import list_skills, get_skill

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Colors
C = {
    "blue": "\033[0;34m", "green": "\033[0;32m", "cyan": "\033[0;36m",
    "yellow": "\033[1;33m", "dim": "\033[90m", "bold": "\033[1m", "nc": "\033[0m",
}


def c(text, color):
    return f"{C.get(color, '')}{text}{C['nc']}"


def pick_model():
    """Pick the best available Ollama model, or None if Ollama is down."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            models = [m.get("name", "") for m in json.loads(resp.read()).get("models", [])]
    except Exception:
        return None, []
    for pref in ("malaysian-7b-dialect", "malaysian-1.5b-reasoning", "qwen2.5:7b"):
        for m in models:
            if m.startswith(pref):
                return m, models
    return (models[0] if models else None), models


def chat_ollama(model, messages, extra_skill=None):
    """Stream a chat completion from Ollama and print it."""
    if extra_skill:
        # prepend skill instructions to the system message
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += f"\n\n[SKILL: {extra_skill['name']}]\n{extra_skill['instructions']}"
        else:
            messages.insert(0, {"role": "system", "content": extra_skill["instructions"]})
    payload = {"model": model, "messages": messages, "stream": True,
               "options": {"temperature": 0.3}}
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            buf = b""
            for raw in resp:
                buf += raw
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not d.get("done"):
                        sys.stdout.write(d.get("message", {}).get("content", ""))
                        sys.stdout.flush()
            print()
    except urllib.error.URLError as e:
        print(c(f"⚠ Ollama tak dapat dihubungi: {e.reason}", "yellow"))


def print_help():
    print(c("\n  Slash commands:", "cyan"))
    rows = [
        ("/help", "tunjuk bantuan ini"),
        ("/skills", "senarai skill — taip /<nama-skill> untuk paksa guna"),
        ("/actions", "senarai action (gaji, invois, sebut harga, susun-fail)"),
        ("/cari <soalan>", "carian web (maklumat terkini)"),
        ("/ingat <fakta>", "simpan fakta ke brain"),
        ("/model [nama]", "tunjuk atau tukar model"),
        ("/bersih", "kosongkan sejarah sesi"),
        ("/keluar", "keluar (atau Ctrl+C)"),
    ]
    for cmd, desc in rows:
        print(f"    {c(cmd, 'green'):28} {c(desc, 'dim')}")
    print(f"\n  {c('Taip teks biasa untuk berbual — tools auto-trigger.', 'dim')}\n")


def cmd_skills():
    skills = list_skills()
    if not skills:
        print(c("  Tiada skill dijumpai.", "yellow"))
        return
    print(c("\n  Skills tersedia:", "cyan"))
    for s in skills:
        print(f"    {c('/' + s['name'], 'green'):28} {c(s['description'], 'dim')}")
    print()


def cmd_actions():
    from lib.tools import ACTION_MANIFEST
    try:
        manifest = json.loads(Path(ACTION_MANIFEST).read_text(encoding="utf-8"))
    except Exception:
        print(c("  Tiada action manifest.", "yellow"))
        return
    print(c("\n  Actions tersedia:", "cyan"))
    for a in manifest.get("actions", []):
        print(f"    {c(a['id'], 'green'):16} {c(a.get('description', ''), 'dim')}")
    print()


def handle_slash(line, state):
    """Handle a /command. Returns True to continue REPL, False to exit."""
    parts = line[1:].split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("keluar", "exit", "quit", "q"):
        return False
    elif cmd in ("help", "h", "?"):
        print_help()
    elif cmd == "skills":
        cmd_skills()
    elif cmd == "actions":
        cmd_actions()
    elif cmd == "bersih":
        state["history"] = []
        print(c("  ✓ Sesi dikosongkan.", "green"))
    elif cmd == "ingat":
        if arg and remember(arg):
            print(c(f"  ✓ Diingat: {arg}", "green"))
        else:
            print(c("  Guna: /ingat <fakta>", "yellow"))
    elif cmd == "cari":
        if not arg:
            print(c("  Guna: /cari <soalan>", "yellow"))
        else:
            print(c("  🔍 Mencari...", "dim"))
            print(web_search(arg))
    elif cmd == "model":
        if arg:
            state["model"] = arg
            print(c(f"  ✓ Model ditukar: {arg}", "green"))
        else:
            print(c(f"  Model semasa: {state.get('model') or '—'}", "blue"))
    else:
        # Maybe it's a skill: /skill-name <input>
        skill = get_skill(cmd)
        if skill:
            if not state.get("model"):
                print(c("  ⚠ Ollama tak jalan — skill perlukan model.", "yellow"))
                return True
            user_text = arg or input(c(f"  {skill['name']} > ", "blue"))
            msgs = [{"role": "system", "content": ""},
                    {"role": "user", "content": user_text}]
            chat_ollama(state["model"], msgs, extra_skill=skill)
        else:
            print(c(f"  Command tak dikenal: /{cmd}. Taip /help.", "yellow"))
    return True


def run():
    model, _ = pick_model()
    state = {"model": model, "history": []}

    print(c("\n  🇲🇾  kacangje prompt", "cyan") + c("  — taip /help untuk command, /keluar untuk keluar", "dim"))
    if model:
        print(c(f"  Model: {model}", "dim"))
    else:
        print(c("  ⚠ Ollama tak jalan. Tools (gaji, cari, kira) masih boleh guna; chat AI perlukan Ollama.", "yellow"))
    print()

    while True:
        try:
            line = input(c("anda > ", "blue")).strip()
        except (EOFError, KeyboardInterrupt):
            print(c("\n  Jumpa lagi! 👋", "cyan"))
            break
        if not line:
            continue
        if line.startswith("/"):
            if not handle_slash(line, state):
                print(c("  Jumpa lagi! 👋", "cyan"))
                break
            continue

        # Normal turn: route through tools (deterministic) → else LLM.
        result = build_messages(line)
        if result.get("direct_answer"):
            print(result["direct_answer"])
        elif state.get("model"):
            chat_ollama(state["model"], result["messages"])
        else:
            print(c("  ⚠ Tiada tool padan & Ollama tak jalan. Cuba /help.", "yellow"))
        print()


if __name__ == "__main__":
    run()
