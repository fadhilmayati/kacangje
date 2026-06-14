# kacangje — Malaysian AI SME Assistant
# Makefile for development and deployment

VERSION := 2.0.0
INSTALL_DIR := $(HOME)/kacangje

.PHONY: help install web serve check clean uninstall dist install-script

help:
	@echo "🇲🇾  kacangje $(VERSION)"
	@echo ""
	@echo "  Targets:"
	@echo "    make install      Full install (same as curl | bash)"
	@echo "    make web          Start web UI (port 8080)"
	@echo "    make serve        Same as web"
	@echo "    make check        Verify Ollama and models"
	@echo "    make update       Pull latest from GitHub"
	@echo "    make dist         Create distribution tarball"
	@echo "    make uninstall    Remove kacangje"
	@echo ""

install:
	@echo ":: Memasang kacangje..."
	@mkdir -p $(INSTALL_DIR)/{web,templates,actions,config,models,lib,rates,brain,skills}
	@cp kacangje $(INSTALL_DIR)/kacangje
	@chmod +x $(INSTALL_DIR)/kacangje
	@cp -r web/* $(INSTALL_DIR)/web/
	@cp -r templates/* $(INSTALL_DIR)/templates/
	@cp -r actions/* $(INSTALL_DIR)/actions/
	@cp -r config/* $(INSTALL_DIR)/config/
	@cp -r lib/* $(INSTALL_DIR)/lib/
	@cp -r rates/* $(INSTALL_DIR)/rates/
	@cp -r brain/* $(INSTALL_DIR)/brain/
	@cp -r skills/* $(INSTALL_DIR)/skills/
	@echo "✓ Installed to $(INSTALL_DIR)"
	@echo "✓ Run: kacangje web"

web serve:
	@echo ":: Starting kacangje web UI..."
	@KACANGJE_DIR=$(INSTALL_DIR) python3 $(INSTALL_DIR)/web/server.py

check:
	@echo ":: Checking setup..."
	@if command -v ollama >/dev/null 2>&1; then \
		echo "✓ Ollama installed"; \
		if ollama list >/dev/null 2>&1; then \
			echo "✓ Ollama running"; \
			ollama list; \
		else \
			echo "⚠ Ollama not running"; \
		fi; \
	else \
		echo "✗ Ollama not installed"; \
	fi
	@echo ""
	@echo "Actions available:"
	@for f in $(INSTALL_DIR)/actions/*.py; do \
		echo "  → $$(basename $$f .py)"; \
	done

update:
	@echo ":: Checking for updates..."
	@if [ -d .git ]; then \
		git pull origin main; \
		echo "✓ Updated"; \
	else \
		echo "⚠ Not a git repo. Clone instead:"; \
		echo "  git clone https://github.com/fadhilmayati/kacangje.git"; \
	fi

dist:
	@echo ":: Creating distribution..."
	@tar czf /tmp/kacangje-$(VERSION).tar.gz \
		kacangje install.sh Makefile \
		web/server.py web/index.html \
		templates/sme-tasks.json \
		actions/*.py actions/manifest.json \
		lib/*.py \
		rates/*.json \
		brain/README.md brain/profile.json brain/memory.jsonl brain/knowledge/*.md \
		skills/*.md \
		config/kacangje.conf
	@echo "✓ Created: /tmp/kacangje-$(VERSION).tar.gz"

uninstall:
	@echo ":: Uninstalling kacangje..."
	@rm -f $(INSTALL_DIR)/kacangje
	@rm -rf $(INSTALL_DIR)/web
	@rm -rf $(INSTALL_DIR)/templates
	@rm -rf $(INSTALL_DIR)/actions
	@rm -rf $(INSTALL_DIR)/config
	@echo "✓ kacangje removed from $(INSTALL_DIR)"
	@echo "To remove models from Ollama:"
	@echo "  ollama rm malaysian-7b-dialect"
	@echo "  ollama rm malaysian-1.5b-reasoning"
