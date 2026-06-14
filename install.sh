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

# Find a source for the program files, in priority order:
#   1. A local checkout (installer sits next to the app files) — copy from there.
#   2. git clone from GitHub.
#   3. Tarball download from GitHub.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
SRC=""
CLEANUP_TMP=""

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/kacangje" && -f "$SCRIPT_DIR/web/server.py" ]]; then
  SRC="$SCRIPT_DIR"
  info "Memasang dari salinan tempatan: $SRC"
else
  TMP="$(mktemp -d)"; CLEANUP_TMP="$TMP"
  if command -v git &>/dev/null && git clone --depth 1 "${REPO}.git" "$TMP/kacangje" >/dev/null 2>&1; then
    SRC="$TMP/kacangje"
    info "Dimuat turun dari GitHub (git)"
  elif curl -fsSL "${REPO}/archive/refs/heads/main.tar.gz" -o "$TMP/k.tgz" 2>/dev/null \
       && tar -xzf "$TMP/k.tgz" -C "$TMP" 2>/dev/null; then
    SRC="$(find "$TMP" -maxdepth 1 -type d -name 'kacangje*' | head -1)"
    info "Dimuat turun dari GitHub (tarball)"
  fi
fi

if [[ -z "$SRC" || ! -f "$SRC/kacangje" ]]; then
  fail "Gagal memuat turun kacangje. Cuba manual: git clone ${REPO}.git $INSTALL_DIR"
fi

# Copy program files. PRESERVE user data: never clobber an existing brain/ (memory,
# profile) or the user's models/.
mkdir -p "$INSTALL_DIR"
cp "$SRC/kacangje" "$INSTALL_DIR/kacangje"
chmod +x "$INSTALL_DIR/kacangje"
for d in web templates actions config lib rates skills; do
  mkdir -p "$INSTALL_DIR/$d"
  cp -R "$SRC/$d/." "$INSTALL_DIR/$d/" 2>/dev/null || true
done
mkdir -p "$INSTALL_DIR/models"
if [[ ! -f "$INSTALL_DIR/brain/profile.json" ]]; then
  mkdir -p "$INSTALL_DIR/brain"
  cp -R "$SRC/brain/." "$INSTALL_DIR/brain/" 2>/dev/null || true
else
  ok "brain/ sedia ada — data anda dikekalkan"
fi
[[ -n "$CLEANUP_TMP" ]] && rm -rf "$CLEANUP_TMP"
ok "kacangje files dipasang ke $INSTALL_DIR"

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

# ── Step 5: Make `kacangje` runnable ────────────────────────────
echo ""
info "Menyediakan arahan 'kacangje'..."

# Best path: symlink into a directory ALREADY on PATH and writable. This makes
# `kacangje` work in the current shell AND new ones, with no `source` needed.
LINKED=""
for d in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
  if [[ -d "$d" && -w "$d" ]]; then
    if ln -sf "$INSTALL_DIR/kacangje" "$d/kacangje" 2>/dev/null; then
      LINKED="$d/kacangje"
      ok "Arahan 'kacangje' dipasang: $LINKED"
      break
    fi
  fi
done

# Fallback / belt-and-suspenders: also add to the shell rc so it survives and
# works even if no writable PATH dir was found.
SHELL_RC=""
case "$(basename "${SHELL:-}")" in
  zsh)  SHELL_RC="$HOME/.zshrc" ;;
  bash) SHELL_RC="$HOME/.bashrc" ;;
  *)    [[ "$OS" == "Darwin" ]] && SHELL_RC="$HOME/.zshrc" || SHELL_RC="$HOME/.bashrc" ;;
esac

if [[ -n "$SHELL_RC" ]] && ! grep -q "kacangje - Malaysian" "$SHELL_RC" 2>/dev/null; then
  {
    echo ""
    echo "# 🇲🇾 kacangje - Malaysian AI SME Assistant"
    echo "export PATH=\"\$PATH:$INSTALL_DIR\""
    echo "export KACANGJE_DIR=\"$INSTALL_DIR\""
  } >> "$SHELL_RC"
  ok "Ditambah ke PATH dalam $(basename "$SHELL_RC")"
fi

# Export for the rest of this installer session.
export PATH="$PATH:$INSTALL_DIR"
export KACANGJE_DIR="$INSTALL_DIR"

# If we couldn't symlink onto an active PATH dir, the user needs a new shell.
if [[ -z "$LINKED" ]]; then
  NEEDS_RELOAD=1
fi

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
echo ""
if [[ "${NEEDS_RELOAD:-0}" == "1" ]]; then
  echo -e "  ${YELLOW}⚠ Buka terminal baru${NC} (atau jalan: ${BLUE}source $SHELL_RC${NC}) supaya arahan 'kacangje' aktif."
  echo ""
fi
