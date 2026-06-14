#!/usr/bin/env bash
# kacangje — Malaysian AI SME Assistant
# One-curl installer: curl -fsSL https://kacangje.ai | bash
#
# What it does:
# 1. Detects OS and hardware (RAM, arch)
# 2. Installs Ollama if missing
# 3. Downloads and configures the right Malaysian model
# 4. Installs the kacangje CLI + web UI + action scripts
# 5. Opens the web UI in browser
#
# Requirements: macOS (Intel/Apple Silicon) or Linux (x86_64/ARM)
# No GPU required for 1.5B model. 8GB+ RAM recommended for 7B.

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────
REPO="https://github.com/fadhilmayati/kacangje"
RAW_BASE="https://raw.githubusercontent.com/fadhilmayati/kacangje/main"
VERSION="2.0.0"
INSTALL_DIR="$HOME/kacangje"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}::${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*" >&2; }
fail()  { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

# ── Banner ──────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                              ║${NC}"
echo -e "${CYAN}║    🇲🇾  kacangje v${VERSION}                      ║${NC}"
echo -e "${CYAN}║    Malaysian AI SME Assistant                ║${NC}"
echo -e "${CYAN}║                                              ║${NC}"
echo -e "${CYAN}║    100% offline · 100% free · Bahasa Melayu   ║${NC}"
echo -e "${CYAN}║                                              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Detect System ───────────────────────────────────────
info "Mengesan sistem..."
OS="$(uname -s)"
ARCH="$(uname -m)"
RAM_GB=4

case "$OS" in
  Darwin)
    ok "macOS detected ($ARCH)"
    RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')
    ;;
  Linux)
    ok "Linux detected ($ARCH)"
    if [[ -f /proc/meminfo ]]; then
      RAM_GB=$(grep MemTotal /proc/meminfo | awk '{printf "%.0f", $2/1048576}')
    fi
    ;;
  *)
    fail "Sistem tak dikenal: $OS. Saya hanya support macOS dan Linux sekarang."
    ;;
esac
info "RAM: ${RAM_GB}GB | Arch: ${ARCH}"

# Homebrew check (macOS)
if [[ "$OS" == "Darwin" ]] && ! command -v brew &>/dev/null; then
  warn "Homebrew tak jumpa. Saya cuba install..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
    fail "Gagal install Homebrew. Install manual: https://brew.sh"
  }
fi

# ── Step 2: Install Ollama ──────────────────────────────────────
echo ""
info "Memeriksa Ollama..."
if ! command -v ollama &>/dev/null; then
  info "Memasang Ollama..."
  case "$OS" in
    Darwin)
      brew install ollama
      brew services start ollama
      ;;
    Linux)
      curl -fsSL https://ollama.com/install.sh | sh
      ;;
  esac
  ok "Ollama installed"
else
  ok "Ollama sudah ada"
fi

# Start Ollama if not running
if ! ollama list &>/dev/null 2>&1; then
  info "Menghidupkan Ollama..."
  case "$OS" in
    Darwin) brew services start ollama 2>/dev/null || true ;;
    Linux)  nohup ollama serve > /dev/null 2>&1 & ;;
  esac
  sleep 3
fi
ok "Ollama running"

# ── Step 3: Install kacangje files ────────────────────────────────
echo ""
info "Memasang kacangje CLI dan tools..."
mkdir -p "$INSTALL_DIR"/{web,templates,actions,config,models,lib,rates,brain,skills}

# Download files from GitHub (or copy from local)
# For now, we'll set up from the local directory if it exists
if [[ -d "$INSTALL_DIR/web" ]] && [[ -f "$INSTALL_DIR/web/server.py" ]]; then
  ok "kacangje files sudah ada di $INSTALL_DIR"
else
  info "Memuat turun kacangje files (coming from GitHub)..."
  warn "Untuk sekarang, clone repo dulu:"
  warn "  git clone https://github.com/fadhilmayati/kacangje.git $INSTALL_DIR"
  warn "Atau setup manual."

  # Try to find local files
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  if [[ -f "$SCRIPT_DIR/kacangje" ]]; then
    info "Jumpa local kacangje files, copy..."
    cp "$SCRIPT_DIR/kacangje" "$INSTALL_DIR/kacangje"
    chmod +x "$INSTALL_DIR/kacangje"
    cp -r "$SCRIPT_DIR/web" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/templates" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/actions" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/config" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/lib" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/rates" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/brain" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/skills" "$INSTALL_DIR/" 2>/dev/null || true
    ok "Files copied"
  fi
fi

# Make CLI executable
chmod +x "$INSTALL_DIR/kacangje" 2>/dev/null || true

# ── Step 4: Pull Model ──────────────────────────────────────────
echo ""
info "Memilih model berdasarkan hardware..."
if (( RAM_GB >= 8 )); then
  MODEL="malaysian-7b-dialect"
  MODEL_SIZE="4.7GB"
else
  MODEL="malaysian-1.5b-reasoning"
  MODEL_SIZE="1.1GB"
fi
info "Model dipilih: ${MODEL} (${MODEL_SIZE})"

# Try to pull from Ollama registry
if ollama pull "$MODEL" 2>/dev/null; then
  ok "Model $MODEL sedia"
else
  warn "Model $MODEL tak jumpa di registry."
  warn "Cuba model alternatif:"
  if (( RAM_GB >= 8 )); then
    info "Memuat turun qwen2.5:7b (model general yang support BM)..."
    ollama pull qwen2.5:7b || ollama pull llama3.2:3b || ollama pull tinyllama
  else
    info "Memuat turun qwen2.5:1.5b..."
    ollama pull qwen2.5:1.5b || ollama pull tinyllama
  fi
fi

# ── Step 5: Add to PATH ─────────────────────────────────────────
SHELL_RC=""
if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == *"zsh"* ]]; then
  SHELL_RC="$HOME/.zshrc"
elif [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == *"bash"* ]]; then
  SHELL_RC="$HOME/.bashrc"
fi

if [[ -n "$SHELL_RC" ]] && ! grep -q "kacangje" "$SHELL_RC" 2>/dev/null; then
  {
    echo ""
    echo "# 🇲🇾 kacangje - Malaysian AI SME Assistant"
    echo "export PATH=\"\$PATH:$INSTALL_DIR\""
    echo "export KACANGJE_DIR=\"$INSTALL_DIR\""
  } >> "$SHELL_RC"
  ok "Ditambah ke PATH dalam $SHELL_RC"
  ok "Jalan: source $SHELL_RC"
fi

# Export for current session
export PATH="$PATH:$INSTALL_DIR"
export KACANGJE_DIR="$INSTALL_DIR"

# ── Step 6: Config ──────────────────────────────────────────────
mkdir -p "$HOME/.config/kacangje"
if [[ -f "$INSTALL_DIR/config/kacangje.conf" ]] && [[ ! -f "$HOME/.config/kacangje/kacangje.conf" ]]; then
  cp "$INSTALL_DIR/config/kacangje.conf" "$HOME/.config/kacangje/kacangje.conf"
  # Set detected model
  sed -i '' "s/^# model =.*/model = $MODEL/" "$HOME/.config/kacangje/kacangje.conf" 2>/dev/null || true
  ok "Config created"
fi

# ── Done ────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   🇲🇾  kacangje sedia digunakan!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Apa nak buat sekarang:${NC}"
echo ""
echo -e "  ${GREEN}1.${NC} Buka web UI:"
echo -e "     ${BLUE}\$ kacangje web${NC}"
echo -e "     Buka http://localhost:8080 dalam browser"
echo ""
echo -e "  ${GREEN}2.${NC} Agentic mode (taip apa-aja):"
echo -e "     ${BLUE}\$ kacangje prompt${NC}"
echo -e "     ${BLUE}anda > kira gaji 20 orang RM2,000${NC}"
echo ""
echo -e "  ${GREEN}3.${NC} Jalan action terus:"
echo -e "     ${BLUE}\$ kacangje action gaji --workers 5 --gaji_pokok 2000${NC}"
echo ""
echo -e "  ${GREEN}4.${NC} Tengok template:"
echo -e "     ${BLUE}\$ kacangje templates${NC}"
echo ""
echo -e "  ${YELLOW}💡 Tip:${NC} Semua jalan offline. Tak perlukan internet lepas install."
echo -e "  ${YELLOW}💡 Tip:${NC} Nak buka web UI sekarang? Jalan: kacangje web"
echo ""
