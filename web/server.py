#!/usr/bin/env python3
"""
kacangje web — Python stdlib-only web server for SME AI assistant.
Serves a chat UI, proxies Ollama API, hosts SME templates.
Zero dependencies beyond Python 3.8+.
"""

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse, unquote

# ── Config ────────────────────────────────────────────────────────
HOST = os.environ.get("KACANGJE_HOST", "0.0.0.0")
PORT = int(os.environ.get("KACANGJE_PORT", "8080"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen2.5:7b-instruct"
KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path.home() / "kacangje")))
TEMPLATES_DIR = KACANGJE_DIR / "templates"

# ── Helpers ───────────────────────────────────────────────────────

def ollama_available():
    """Check if Ollama is reachable."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return len(data.get("models", [])) > 0, data.get("models", [])
    except Exception:
        return False, []


def load_templates():
    """Load SME templates from templates/ directory."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for f in sorted(TEMPLATES_DIR.iterdir()):
        if f.suffix == ".json":
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        templates.extend(data)
                    else:
                        templates.append(data)
            except Exception:
                pass
    return templates


def get_system_info():
    """Return system info for the UI footer."""
    info = {"platform": sys.platform}
    try:
        import subprocess
        if sys.platform == "darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=2
            )
            info["cpu"] = result.stdout.strip()
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=2
            )
            mem_bytes = int(result.stdout.strip())
            info["ram_gb"] = round(mem_bytes / (1024**3), 1)
        else:
            info["cpu"] = "Unknown"
            info["ram_gb"] = 0
    except Exception:
        info["cpu"] = "Unknown"
        info["ram_gb"] = 0
    return info


# ── Request Handler ───────────────────────────────────────────────

class KacangjeHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """Quieter logging."""
        if args[0].startswith("GET /api/"):
            return  # don't log API polling
        sys.stderr.write(f"[kacangje] {args[0]} {args[1]} {args[2]}\n")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path):
        """Serve a static file from web/ directory."""
        web_dir = KACANGJE_DIR / "web"
        filepath = web_dir / path
        try:
            filepath.resolve().relative_to(web_dir.resolve())
        except ValueError:
            self.send_response(403)
            self.end_headers()
            return
        if not filepath.exists() or filepath.is_dir():
            self.send_response(404)
            self.end_headers()
            return
        with open(filepath, "rb") as f:
            data = f.read()
        ext = filepath.suffix
        mime_map = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript",
            ".css": "text/css",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".svg": "image/svg+xml",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ── API Routes ──
        if path == "/api/status":
            avail, raw_models = ollama_available()
            model_names = [m.get("name", "") for m in raw_models] if raw_models else []
            info = get_system_info()
            templates = load_templates()
            self._send_json({
                "ollama": avail,
                "models": model_names,
                "system": info,
                "templates": templates,
            })
            return

        if path == "/api/templates":
            self._send_json(load_templates())
            return

        # ── Serve static files ──
        if path in ("/", "/index.html"):
            self._send_static("index.html")
        elif path.startswith("/static/"):
            self._send_static(path[8:])  # strip /static/
        else:
            self._send_static(path.lstrip("/"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)

            model = payload.get("model", DEFAULT_MODEL)
            user_messages = payload.get("messages", [])

            os.environ["OLLAMA_MODEL"] = model

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                from lib.tools import build_messages as agent_process, match_intent

                # Get the last user message
                last_user_msg = ""
                for m in reversed(user_messages):
                    if m.get("role") == "user":
                        last_user_msg = m["content"]
                        break

                # Before executing tools, send a tool_start event if intent is detected
                tool_icons = {
                    "run_action:gaji": "💰 Mengira gaji...",
                    "run_action:invoice": "📄 Menjana invoice...",
                    "run_action:quotation": "📝 Menjana sebut harga...",
                    "run_action:susun-fail": "📁 Menyusun fail...",
                    "run_action:excel-analisis": "📊 Menganalisis data...",
                    "web_search": "🔍 Mencari maklumat...",
                    "calculate": "🧐 Mengira...",
                }
                intent_matches = match_intent(last_user_msg)
                tool_label = None
                if intent_matches:
                    tname, targs = intent_matches[0]
                    if tname == "run_action":
                        aid = targs.get("action_id", "")
                        tool_label = tool_icons.get(f"run_action:{aid}") or f"⚙️ Menjalankan {aid}..."
                    else:
                        tool_label = tool_icons.get(tname)
                if tool_label:
                    self.wfile.write(f"data: {json.dumps({'tool': tool_label})}\n\n".encode())
                    self.wfile.flush()

                result = agent_process(last_user_msg)
                os.environ.pop("OLLAMA_MODEL", None)

                # If we have a direct answer (tool-generated), send it directly
                if result.get("direct_answer"):
                    self.wfile.write(f"data: {json.dumps({'content': result['direct_answer']})}\n\n".encode())
                    stats = {"done": True, "eval_count": 0, "eval_duration": 0, "total_duration": 0}
                    self.wfile.write(f"data: {json.dumps(stats)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    return

                # Otherwise, stream LLM response
                payload = {
                    "model": model,
                    "messages": result.get("messages", []),
                    "stream": True,
                    "options": {"temperature": 0.3},
                }

                req = urllib.request.Request(
                    f"{OLLAMA_HOST}/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=300) as resp:
                    buffer = b""
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                line_data = json.loads(line)
                                if line_data.get("done"):
                                    stats = {
                                        "done": True,
                                        "eval_count": line_data.get("eval_count", 0),
                                        "eval_duration": line_data.get("eval_duration", 0),
                                        "total_duration": line_data.get("total_duration", 0),
                                    }
                                    self.wfile.write(f"data: {json.dumps(stats)}\n\n".encode())
                                else:
                                    content = line_data.get("message", {}).get("content", "")
                                    if content:
                                        self.wfile.write(f"data: {json.dumps({'content': content})}\n\n".encode())
                            except json.JSONDecodeError:
                                pass
                        self.wfile.flush()
            except urllib.error.HTTPError as e:
                self.wfile.write(f"data: {json.dumps({'error': f'Ollama error: {e.code} {e.reason}'})}\n\n".encode())
            except urllib.error.URLError as e:
                self.wfile.write(f"data: {json.dumps({'error': f'Ollama not reachable: {e.reason}'})}\n\n".encode())
            except Exception as e:
                import traceback
                self.wfile.write(f"data: {json.dumps({'error': str(e)})}\n\n".encode())
                self.wfile.write(f"data: {json.dumps({'error_detail': traceback.format_exc()})}\n\n".encode())
            finally:
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            return

        if path == "/api/run-action":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body)

            action_id = payload.get("action", "")
            params = payload.get("params", {})

            # Load manifest
            manifest_path = KACANGJE_DIR / "actions" / "manifest.json"
            if not manifest_path.exists():
                self._send_json({"success": False, "error": "Action manifest not found"}, 500)
                return

            with open(manifest_path) as f:
                manifest = json.load(f)

            action_def = None
            for a in manifest.get("actions", []):
                if a["id"] == action_id:
                    action_def = a
                    break

            if not action_def:
                self._send_json({"success": False, "error": f"Action '{action_id}' not found"}, 404)
                return

            script_path = KACANGJE_DIR / "actions" / action_def["file"]
            if not script_path.exists():
                self._send_json({"success": False, "error": f"Script {action_def['file']} not found"}, 500)
                return

            try:
                result = subprocess.run(
                    [sys.executable, str(script_path), json.dumps(params)],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    self._send_json({
                        "success": False,
                        "error": f"Action failed: {result.stderr[:500]}"
                    }, 500)
                    return
                output = json.loads(result.stdout)
                self._send_json(output)
            except subprocess.TimeoutExpired:
                self._send_json({"success": False, "error": "Action timed out (30s)"}, 504)
            except json.JSONDecodeError as e:
                self._send_json({"success": False, "error": f"Invalid output: {str(e)}"}, 500)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)
            return

        self._send_json({"error": "not found"}, 404)

    do_PUT = do_POST
    do_DELETE = do_POST


# ── Server Thread ─────────────────────────────────────────────────

def open_browser():
    """Open browser to the web UI after a short delay."""
    import time
    time.sleep(1.5)
    url = f"http://127.0.0.1:{PORT}"
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", url], capture_output=True)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", url], capture_output=True)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────

def main():
    # Check Ollama
    avail, raw_models = ollama_available()
    model_names = [m.get("name", "") for m in raw_models[:3]] if raw_models else []
    # Pick default or first available
    global DEFAULT_MODEL
    if raw_models and DEFAULT_MODEL not in [m.get("name", "") for m in raw_models]:
        DEFAULT_MODEL = raw_models[0].get("name", DEFAULT_MODEL)
    if not avail:
        print("\033[33m⚠\033[0m Ollama tidak reachable. Pastikan 'ollama serve' sedang jalan.", file=sys.stderr)
        print("  Run: ollama serve", file=sys.stderr)
        print("  Atau: brew services start ollama\n", file=sys.stderr)

    server = http.server.HTTPServer((HOST, PORT), KacangjeHandler)
    print(f"\033[36m╔══════════════════════════════════════════════╗\033[0m")
    print(f"\033[36m║   🇲🇾  kacangje SME AI Assistant              ║\033[0m")
    print(f"\033[36m╚══════════════════════════════════════════════╝\033[0m")
    print(f"")
    print(f"  \033[32m✓\033[0m Buka: http://127.0.0.1:{PORT}")
    print(f"  \033[32m✓\033[0m Model: {', '.join(model_names) if model_names else '—'}")
    print(f"  \033[32m✓\033[0m Templates: {len(load_templates())} SME tasks sedia")
    print(f"  \033[90m—\033[0m Tekan Ctrl+C untuk stop")
    print(f"")

    # Open browser automatically
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n\033[33m■\033[0m kacangje web stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
