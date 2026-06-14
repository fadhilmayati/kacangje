"""
kacangje tools — pre-process intent, execute tools, inject context.
Works with ANY model (no function calling API needed).
Architecture: user query → intent matching → tool execution → context injection → LLM answers
"""

import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path.home() / "kacangje")))
ACTIONS_DIR = KACANGJE_DIR / "actions"
ACTION_MANIFEST = ACTIONS_DIR / "manifest.json"
BRAIN_DIR = KACANGJE_DIR / "brain"
KNOWLEDGE_DIR = BRAIN_DIR / "knowledge"
MEMORY_FILE = BRAIN_DIR / "memory.jsonl"
PROFILE_FILE = BRAIN_DIR / "profile.json"

# Words too common to be useful for keyword retrieval.
_STOPWORDS = {
    "yang", "untuk", "dengan", "saya", "anda", "ini", "itu", "apa", "berapa",
    "boleh", "nak", "the", "and", "for", "what", "how", "much", "many", "is",
    "a", "an", "to", "of", "dan", "atau", "di", "ke", "dari", "pada", "tolong",
}

# ── Brain: local knowledge, memory, profile ───────────────────

def _tokenize(text: str) -> set:
    """Lowercase word tokens, minus stopwords and very short tokens."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def recall(query: str, max_snippets: int = 3) -> str:
    """Keyword-retrieve relevant grounding from brain/knowledge and memory.
    Returns a context string (possibly empty) to inject into the LLM prompt.
    Deterministic, offline, no model needed."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return ""

    scored = []

    # Knowledge notes — score by token overlap, weight the Keywords line higher.
    if KNOWLEDGE_DIR.exists():
        for f in sorted(KNOWLEDGE_DIR.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            doc_tokens = _tokenize(text)
            overlap = len(q_tokens & doc_tokens)
            # Bonus for explicit Keywords: line matches
            kw_line = ""
            for line in text.splitlines():
                if line.lower().startswith("keywords:"):
                    kw_line = line
                    break
            kw_bonus = len(q_tokens & _tokenize(kw_line)) * 2
            score = overlap + kw_bonus
            if score > 0:
                scored.append((score, f.stem, text.strip()))

    # Remembered facts
    for fact in _read_memory():
        doc_tokens = _tokenize(fact)
        score = len(q_tokens & doc_tokens)
        if score > 0:
            scored.append((score, "memory", fact))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    parts = []
    for _, name, text in scored[:max_snippets]:
        # Trim very long notes to keep token usage low
        snippet = text if len(text) <= 1200 else text[:1200] + "…"
        parts.append(f"[{name}]\n{snippet}")
    return "\n\n".join(parts)


def _read_memory() -> list:
    facts = []
    if MEMORY_FILE.exists():
        try:
            for line in MEMORY_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    facts.append(json.loads(line).get("fact", ""))
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
    return [f for f in facts if f]


def remember(fact: str) -> bool:
    """Append a short fact to brain memory (offline, local)."""
    fact = fact.strip()
    if not fact:
        return False
    try:
        BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"ts": datetime.now().strftime("%Y-%m-%d"), "fact": fact}
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def load_profile() -> dict:
    """Load the SME's own identity from brain/profile.json."""
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ── Tool Implementations ──────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (free, no API key).
    Falls back to a self-hosted SearXNG instance if ddgs is unavailable."""
    if not query or not query.strip():
        return "[Web search: query kosong]"
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            return "Tiada hasil carian."
        lines = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"Title: {title}\nSource: {href}\n{snippet}")
        return "\n\n".join(lines)
    except ImportError:
        # SearXNG is opt-in via SEARXNG_URL. Default port 8888 avoids colliding
        # with the kacangje web UI (which runs on 8080).
        try:
            import urllib.request
            import urllib.parse
            searxng_url = os.environ.get("SEARXNG_URL", "http://localhost:8888").rstrip("/")
            params = urllib.parse.urlencode({
                "q": query, "format": "json", "language": "ms", "safesearch": 1
            })
            req = urllib.request.Request(
                f"{searxng_url}/search?{params}",
                headers={"User-Agent": "kacangje/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            results = data.get("results", [])[:max_results]
            if not results:
                return "Tiada hasil carian."
            return "\n\n".join(
                f"Title: {r.get('title', '')}\nSource: {r.get('url', '')}\n{r.get('content', '')}"
                for r in results
            )
        except Exception as e:
            return (
                "[Web search tidak tersedia. Pasang 'ddgs' (pip install ddgs) "
                f"atau jalankan SearXNG dan set SEARXNG_URL. Ralat: {e}]"
            )
    except Exception as e:
        return f"[Ralat web search: {e}]"


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed.update({
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "float": float, "int": int,
    })
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)
        return json.dumps({"result": result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_action(action_id: str, action_params: dict = None, **kwargs) -> str:
    """Run a pre-built SME action script.
    action_params contains the parameters for the action script."""
    if action_params is None:
        action_params = kwargs.get("params", {})

    if not ACTION_MANIFEST.exists():
        return json.dumps({"error": "Action manifest not found"}, ensure_ascii=False)

    with open(ACTION_MANIFEST) as f:
        manifest = json.load(f)

    action_def = next((a for a in manifest.get("actions", []) if a["id"] == action_id), None)
    if not action_def:
        return json.dumps({
            "error": f"Action '{action_id}' tak jumpa",
            "available": [a["id"] for a in manifest.get("actions", [])]
        }, ensure_ascii=False)

    script_path = ACTIONS_DIR / action_def["file"]
    if not script_path.exists():
        return json.dumps({"error": f"Script {action_def['file']} not found"}, ensure_ascii=False)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), json.dumps(action_params)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr[:500]}, ensure_ascii=False)
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Action timeout (30s)"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Intent Matcher ────────────────────────────────────────────
# Matches queries to tools using keywords & patterns.
# Returns (tool_name, tool_args, confidence) or None.

INTENT_PATTERNS = [
    # Salary / EPF / SOCSO question → run_action gaji (has rates built in)
    {
        "tools": ["run_action:gaji"],
        "patterns": [
    # Require explicit *calculation* intent, not just a mention of EPF/SOCSO.
    # Informational rate questions fall through to the LLM + brain grounding.
    r"kira\s+gaji", r"gaji\s+(pekerja|bulanan)", r"payroll",
    r"\bgaji\b.*(?:pekerja|orang|bulanan)", r"(?:pekerja|orang).*\bgaji\b",
    r"gaji\s+untuk\s+\d+\s+(orang|pekerja)",
    r"pengiraan\s+gaji", r"berapakah\s+gaji",
    r"kira.*\b(epf|socso|eis|pcb)\b", r"\b(epf|socso|eis|pcb)\b.*\bgaji\b",
    r"potongan\s+gaji",
        ],
    },
    # Rate queries → web search (kadar EPF, SST, minimum wage)
    {
        "tools": ["web_search"],
        "patterns": [
            r"kadar\s+(cukai|epf|socso|sst).*sekarang",
            r"kadar\s+terkini",
            r"cukai\s+(pendapatan|jualan|perkhidmatan)",
            r"minimum\s*wage", r"gaji\s*minimum",
            r"berapa\s*(sst|cukai)",
            r"rate\s+(cukai|epf|sst)",
        ],
        "search_query": lambda q: f"{q} Malaysia 2026"
    },
    # Quotation → run_action quotation (check before invoice; "sebut harga" is distinct)
    {
        "tools": ["run_action:quotation"],
        "patterns": [
            r"sebut\s*harga", r"quotation", r"\bquote\b", r"sebutharga",
            r"buat\s+quote", r"tawaran\s+harga",
        ],
    },
    # Invoice → run_action invoice
    {
        "tools": ["run_action:invoice"],
        "patterns": [
            r"buat\s+invoice", r"invoice\s+untuk", r"invois",
            r"bil\s+untuk", r"generate\s+invoice",
        ],
    },
    # File organization → run_action susun-fail
    {
        "tools": ["run_action:susun-fail"],
        "patterns": [
            r"susun\s+fail", r"susun\s+folder", r"organize\s+(files|folder)",
            r"kemas\s+fail", r"urus\s+fail", r"pindah\s+fail",
        ],
    },
    # Excel / data analysis → run_action excel-analisis
    {
        "tools": ["run_action:excel-analisis"],
        "patterns": [
            r"analisis\s+(excel|data|jualan)", r"baca\s+(csv|excel|data)",
            r"profit\s+margin", r"analisa\s+data",
            r"carian\s+data", r"laporan\s+jualan",
        ],
    },
    # Math / calculation → calculate
    {
        "tools": ["calculate"],
        "patterns": [
            r"berapa\s+(\d+\s*[+\-*/]\s*\d+|peratus|percent)",
            r"kira\s+(\d+|peratus|percent)",
            r"tolong\s+hitung", r"hitung",
            r"\d+\s*[+\-*/%]\s*\d+",
            r"\d+\s*%\s*(daripada|drpd|dari|of|kali)\s*\d+",
        ],
    },
    # Current date → get_current_date
    {
        "tools": ["date"],
        "patterns": [
            r"hari\s+ini\s+(tarikh|hari|bila)", r"tarikh\s+sekarang",
            r"what\s+(day|date)\s+is\s+(it|today)",
        ],
    },
]


def match_intent(query: str) -> list:
    """Match a query against intent patterns.
    Returns list of (tool_name, args_dict) tuples."""
    q_lower = query.lower()
    matches = []

    for intent in INTENT_PATTERNS:
        for pattern in intent["patterns"]:
            if re.search(pattern, q_lower):
                for tool_spec in intent.get("tools", []):
                    if tool_spec == "web_search":
                        sq = intent.get("search_query", lambda q: q)
                        matches.append(("web_search", {"query": sq(q_lower)}))
                    elif tool_spec == "calculate":
                        expr = extract_math_expression(query)
                        if expr:
                            matches.append(("calculate", {"expression": expr}))
                    elif tool_spec.startswith("run_action:"):
                        action_id = tool_spec.split(":", 1)[1]
                        params = extract_params_for_action(q_lower, action_id)
                        matches.append(("run_action", {"action_id": action_id, "params": params}))
                    elif tool_spec == "date":
                        matches.append(("get_current_date", {}))
                break  # only first match per intent group

    return matches


def extract_math_expression(query: str):
    """Pull a clean arithmetic expression out of a natural-language query.
    Returns a Python-evaluable string, or None if no math is found."""
    q = query.lower()

    # "12% daripada 5000" / "12% of 5000" → (12/100)*5000
    m = re.search(r"(\d+\.?\d*)\s*%\s*(?:daripada|drpd|dari|of|x|kali)\s*(\d+\.?\d*)", q)
    if m:
        return f"({m.group(1)}/100)*{m.group(2)}"

    # Otherwise grab the arithmetic-looking span and strip stray '%'
    span = re.findall(r"[\d.\s+\-*/()]+", q)
    if span:
        candidate = max(span, key=len).strip()
        # must contain a digit and an operator to be a real calculation
        if re.search(r"\d", candidate) and re.search(r"[+\-*/]", candidate):
            return candidate
    return None


def extract_params_for_action(query: str, action_id: str) -> dict:
    """Extract numeric parameters from query text for an action."""
    params = {}
    q_lower = query.lower()

    if action_id == "gaji":
        # Worker count: number near 'pekerja', 'orang', 'worker'
        for pat in [r"(\d+)\s*(pekerja|orang|worker|staff)", r"(pekerja|orang|worker|staff)\s*(\d+)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                params["workers"] = int(m.group(1) if m.group(1).isdigit() else m.group(2))
                break
        params.setdefault("workers", 1)

        # Salary: number near 'RM' or 'gaji RM\d+'
        s = None
        for pat in [r"rm\s*(\d+[.,]?\d*)", r"gaji\s*(?:pokok\s*)?rm\s*(\d+[.,]?\d*)",
                     r"gaji[:\s]+(\d+[.,]?\d*)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                s = float(m.group(1).replace(",", ""))
                break
        params["gaji_pokok"] = s if s and s >= 100 else 1500

        # OT hours: number near 'OT', 'jam', 'hour', 'overtime'
        for pat in [r"(?:ot|overtime)\s*(\d+)[.\s]", r"(\d+)\s*(?:jam|hours?)\s*(?:ot|overtime|extra)",
                     r"(?:ot|overtime)\s*:?\s*(\d+)", r"(\d+)\s*(jam|hours?)\s*(lebih|extra)?"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                h = float(m.group(1))
                if 1 <= h <= 168:  # reasonble OT hours range
                    params["ot_hours"] = h
                    break

        # OT rate: number near 'x', 'kali' after OT mention
        ot_rate = re.search(r"ot\s.*?(\d+\.?\d*)\s*(x|kali)", q_lower)
        if ot_rate:
            params["ot_rate"] = float(ot_rate.group(1))

        # Allowances
        for pat in [r"(elaun|allowance|tambahan)\s*:?\s*rm?\s*(\d+)", r"rm?\s*(\d+)\s*(elaun|allowance|tambahan)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                params["elaun"] = float(m.group(2) if m.group(2).lstrip("-").isdigit() else m.group(1))
                break

    elif action_id in ("invoice", "quotation"):
        params = {"items": []}

    return params


# ── Answer Formatting (no LLM needed for action results) ──────

def format_action_answer(action_id: str, result_json: dict) -> str:
    """Format an action result as a natural language answer.
    No LLM needed — we format directly from the structured data."""
    if not result_json.get("success"):
        return f"Maaf, ada ralat: {result_json.get('error', 'unknown error')}"

    if action_id == "gaji":
        pw = result_json.get("per_worker", {})
        total = result_json.get("total", {})
        workers = total.get("workers", 1)

        lines = [f"📋 Pengiraan Gaji:"]
        lines.append(f"  Gaji pokok: RM{pw.get('gaji_pokok', 0):,.2f}")
        if pw.get("ot_pay", 0) > 0:
            lines.append(f"  OT: RM{pw['ot_pay']:,.2f}")
        if pw.get("elaun", 0) > 0:
            lines.append(f"  Elaun: RM{pw['elaun']:,.2f}")
        lines.append(f"  Gaji kasar: RM{pw.get('gaji_kasar', 0):,.2f}")
        lines.append(f"  ─── Potongan ───")
        lines.append(f"  EPF (pekerja): RM{pw.get('epf_employee', 0):,.2f}")
        lines.append(f"  EPF (majikan): RM{pw.get('epf_employer', 0):,.2f}")
        lines.append(f"  SOCSO: RM{pw.get('socso', 0):,.2f}")
        lines.append(f"  EIS: RM{pw.get('eis', 0):,.2f}")
        if pw.get("pcb", 0) > 0:
            lines.append(f"  PCB: RM{pw['pcb']:,.2f}")
        lines.append(f"  ───")
        lines.append(f"  **Gaji bersih seorang: RM{pw.get('gaji_bersih', 0):,.2f}**")
        if workers > 1:
            lines.append(f"  **Jumlah untuk {workers} pekerja: RM{total.get('gaji_bersih', 0):,.2f}**")
        # Trust layer: warnings + which rates were used
        for w in result_json.get("warnings", []):
            lines.append(f"  ⚠️ {w}")
        ru = result_json.get("rates_used", {})
        if ru:
            lines.append(
                f"  ─── Kadar {ru.get('year', '')}: EPF {ru.get('epf_employee_pct')}% "
                f"· SOCSO {ru.get('socso_pct')}% · EIS {ru.get('eis_pct')}% ───"
            )
        if result_json.get("disclaimer"):
            lines.append(f"  ℹ️ {result_json['disclaimer']}")
        return "\n".join(lines)

    elif action_id == "invoice":
        return (
            f"📄 Invois sedia!\n"
            f"  Client: {result_json.get('client', 'N/A')}\n"
            f"  No: {result_json.get('invoice_no', 'N/A')}\n"
            f"  Jumlah: RM{result_json.get('total', 0):,.2f}\n"
            f"  Item: {result_json.get('items', 0)} perkara\n"
        )

    elif action_id == "quotation":
        return (
            f"📝 Sebut harga sedia!\n"
            f"  Client: {result_json.get('client', 'N/A')}\n"
            f"  No: {result_json.get('quote_no', 'N/A')}\n"
            f"  Jumlah: RM{result_json.get('total', 0):,.2f}\n"
            f"  Sah sehingga: {result_json.get('valid_until', 'N/A')}\n"
        )

    elif action_id == "susun-fail":
        status = result_json.get("summary", "")
        return f"📁 {status}"

    elif action_id == "excel-analisis":
        return result_json.get("summary", "Analisis siap.")

    # Fallback
    return result_json.get("summary", "Siap.")


def format_search_answer(query: str, results: str) -> str:
    """Format web search results."""
    return (
        f"🔍 Hasil carian untuk '{query}':\n\n{results}\n\n"
        f"(Sumber: carian web)"
    )


# ── Main Processing ───────────────────────────────────────────

def process_query(user_query: str) -> dict:
    """Process a user query:
    1. Match intent
    2. Execute tools
    3. Return answer ready for user
    Returns: {answer: str, tool_used: str, tool_result: str, use_llm: bool}
    
    If use_llm is True, the caller should pass to LLM for final formatting.
    If False, the answer is ready to return directly.
    """
    matches = match_intent(user_query)

    if not matches:
        return {
            "answer": None,
            "tool_used": None,
            "tool_result": None,
            "use_llm": False,  # Nothing to do, let LLM handle directly
        }

    # Process tools
    context_parts = []
    tool_used = None
    tool_result = None
    formatted_answer = None
    use_llm = True

    for tool_name, tool_args in matches:
        if tool_name == "web_search":
            result = web_search(**tool_args)
            tool_used = "web_search"
            tool_result = result
            formatted_answer = format_search_answer(
                tool_args.get("query", ""), result
            )
            use_llm = False  # Direct answer

        elif tool_name == "calculate":
            result = calculate(**tool_args)
            tool_used = "calculate"
            tool_result = result
            # Format calculate result
            try:
                data = json.loads(result)
                if "result" in data:
                    formatted_answer = f"🧮 Hasil: {data['result']}"
                else:
                    formatted_answer = f"Ralat: {data.get('error', '')}"
            except Exception:
                formatted_answer = result
            use_llm = False

        elif tool_name == "run_action":
            result = run_action(**tool_args)
            tool_used = f"action:{tool_args.get('action_id', '')}"
            tool_result = result
            try:
                data = json.loads(result)
                formatted_answer = format_action_answer(
                    tool_args.get("action_id", ""), data
                )
                use_llm = False  # Direct answer
            except json.JSONDecodeError:
                context_parts.append(
                    f"[ACTION RESULT: {tool_args.get('action_id', '')}]\n{result}\n"
                )

        elif tool_name == "get_current_date":
            now = datetime.now()
            formatted_answer = f"📅 Hari ini: {now.strftime('%A, %d %B %Y')}, {now.strftime('%H:%M')}"
            use_llm = False

    return {
        "answer": "\n".join(context_parts) if context_parts else formatted_answer,
        "tool_used": tool_used,
        "tool_result": tool_result,
        "use_llm": use_llm,
    }


# ── System Prompt ─────────────────────────────────────────────

SYSTEM_PROMPT = """Anda adalah pembantu AI pejabat untuk SME Malaysia.

TUGAS ANDA:
- Menjawab soalan umum dan perbualan biasa
- Menulis email, surat, dokumen dalam BM
- Membantu dengan tugas pejabat harian

PANDUAN:
1. Jawab dalam Bahasa Malaysia. Campur Inggeris jika perlu.
2. RINGKAS dan tepat.
3. Bersikap membantu dan mesra."""


def build_messages(user_query: str) -> dict:
    """Build messages for the LLM.
    Returns: {messages: list, tool_used: str or None, tool_result: str or None, direct_answer: str or None}
    
    If direct_answer is set, the caller should return it directly without calling the LLM.
    """
    result = process_query(user_query)

    if not result["use_llm"] and result["answer"]:
        return {
            "messages": [],
            "tool_used": result["tool_used"],
            "tool_result": result["tool_result"],
            "direct_answer": result["answer"],
        }

    # Ground the model with local brain knowledge + SME profile (offline RAG).
    system_content = SYSTEM_PROMPT

    # Auto-invoke a skill if one strongly matches (Claude Code / OpenCode style).
    try:
        from lib.skills import match_skill
    except Exception:
        try:
            from skills import match_skill  # when lib is on sys.path
        except Exception:
            match_skill = None
    if match_skill:
        skill = match_skill(user_query)
        if skill:
            system_content += f"\n\n[SKILL: {skill['name']}]\n{skill['instructions']}"

    grounding = recall(user_query)
    if grounding:
        system_content += (
            "\n\nMAKLUMAT RUJUKAN TEMPATAN (guna jika relevan, jangan reka angka):\n"
            + grounding
        )
    profile = load_profile()
    if profile.get("company_name"):
        system_content += f"\n\nSYARIKAT PENGGUNA: {profile.get('company_name')}"

    messages = [{"role": "system", "content": system_content}]
    messages.append({"role": "user", "content": user_query})

    return {
        "messages": messages,
        "tool_used": result["tool_used"],
        "tool_result": result["tool_result"],
        "direct_answer": None,
    }
