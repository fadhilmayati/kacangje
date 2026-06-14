"""
kacangje skills — reusable, tested prompt-behaviours for SME office work.

Mirrors the Claude Code / OpenCode model: a skill is a folder-or-file with
frontmatter (name, description, triggers) plus instruction body. Skills are
*knowledge the agent pulls in* — they shape how the small local model answers
a class of task (write a letter, draft a customer email), without needing a
bigger model or more tokens per call.

Auto-invoke: match_skill() picks a relevant skill from the query.
Manual: the REPL lets the user type /skill-name to force one.
"""

import os
import re
from pathlib import Path

KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path.home() / "kacangje")))
SKILLS_DIR = KACANGJE_DIR / "skills"

_STOPWORDS = {
    "yang", "untuk", "dengan", "saya", "anda", "ini", "itu", "apa", "tolong",
    "boleh", "nak", "the", "and", "for", "what", "how", "dan", "atau", "satu",
}


def _parse_frontmatter(text: str):
    """Parse a simple --- key: value --- frontmatter block. No YAML dep."""
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta, body


def _load_one(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    meta, body = _parse_frontmatter(text)
    name = meta.get("name") or path.stem
    triggers = [t.strip().lower() for t in meta.get("triggers", "").split(",") if t.strip()]
    return {
        "name": name,
        "description": meta.get("description", ""),
        "triggers": triggers,
        "instructions": body.strip(),
    }


def list_skills():
    """Return all available skills (sorted by name)."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    # Support both flat files (skills/foo.md) and folders (skills/foo/SKILL.md)
    for p in sorted(SKILLS_DIR.iterdir()):
        if p.is_file() and p.suffix == ".md":
            s = _load_one(p)
            if s:
                skills.append(s)
        elif p.is_dir():
            sk = p / "SKILL.md"
            if sk.exists():
                s = _load_one(sk)
                if s:
                    skills.append(s)
    return sorted(skills, key=lambda s: s["name"])


def get_skill(name: str):
    name = (name or "").strip().lower()
    for s in list_skills():
        if s["name"].lower() == name:
            return s
    return None


def _tokenize(text: str):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def match_skill(query: str):
    """Auto-invoke: pick the best-matching skill for a query, or None."""
    q = query.lower()
    q_tokens = _tokenize(query)
    best, best_score = None, 0
    for s in list_skills():
        score = 0
        for trig in s["triggers"]:
            if trig and trig in q:
                score += 3
        score += len(q_tokens & _tokenize(s["description"]))
        if score > best_score:
            best, best_score = s, score
    return best if best_score >= 3 else None
