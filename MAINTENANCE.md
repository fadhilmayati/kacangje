# kacangje — Release & Maintenance Runbook (SRE)

This is the operational playbook for keeping kacangje healthy **after release**: how we
ship, and what the automated daily maintenance agent does. It is the single source of
truth for the scheduled "maintenance loop." If you change the flow, change it here.

> Detailed model-benchmark methodology and business strategy live in the private repo
> (`kacangje-private/`). This file is the public, operational layer only.

---

## 1. What "good" looks like (the flow)

```
        ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
        │   RELEASE   │ ──▶ │   OBSERVE    │ ──▶ │    IMPROVE     │ ──┐
        │ (cut a ver) │     │ (daily loop) │     │ (fix/harden)   │   │
        └─────────────┘     └──────────────┘     └────────────────┘   │
               ▲                                                       │
               └───────────────────── feedback ────────────────────────┘
```

We run a tight **release → observe → improve** loop. Releases are deliberate and
checklisted; observation and improvement are continuous and mostly automated (the daily
agent). Feedback from real SME users feeds the next release.

---

## 2. Release flow (human-initiated)

A release is cut intentionally, not by the agent. Pre-flight checklist:

- [ ] Version bumped in `kacangje`, `Makefile` (`VERSION`), and `install.sh` if pinned.
- [ ] `make check` passes on a clean machine (Ollama + models resolve).
- [ ] `install.sh` smoke-tested end-to-end on a fresh `$HOME` (the non-coder path).
- [ ] `rates/<year>.json` validated against **official sources** (KWSP/PERKESO/LHDN) and
      every rate carries a `source` URL + `effective` date.
- [ ] Each action runs on a sample input (`gaji`, `invoice`, `quotation`, `susun-fail`,
      `excel-analisis`).
- [ ] README + skill list reflect reality.
- [ ] `make dist` builds a clean tarball.
- [ ] Tag `vX.Y.Z`, write a short CHANGELOG entry.

Versioning is **semver**: rates/data refresh = patch; new skill/action = minor; install
or CLI contract change = major.

---

## 3. Daily maintenance loop (the agent)

Runs every morning as a scheduled cloud routine. Each run works the checklist below and
ends by writing a **daily maintenance report** (committed to `maint/reports/YYYY-MM-DD.md`).

### Checklist
1. **Repo health.** Run `make check`; lint bash (`bash -n`) + python (`python3 -m py_compile`)
   across `kacangje`, `actions/`, `lib/`, `web/`. Check for broken README/install links.
   Smoke-test `install.sh` parsing.
2. **Feedback intake.** Scan GitHub issues / PRs / discussions. Triage + label, answer the
   easy ones, and summarize recurring themes into the report. Real SME pain → backlog.
3. **Rates freshness (compliance moat).** Check whether EPF/SOCSO/EIS/PCB/SST/e-Invois
   rates have an official update. If an official change is published, update
   `rates/<year>.json` **with the source URL + effective date**.
4. **Model watch.** Check for newly released capable open models (Hugging Face trending,
   Ollama library, Qwen/Gemma/Llama/Mesolitica drops). If one plausibly fits a hardware
   tier, benchmark it (speed, BM quality, tool-calling) against the current tier pick.
5. **Hardening / improvement.** Pull one item from the backlog (§5) — input validation,
   error handling, test coverage, a small UX fix — and do it.
6. **Report.** Write the day's report: checked / found / committed / PR'd / model news /
   feedback themes / suggested next work.

---

## 4. Safety rules (what the agent may do unattended)

The agent's authority is bounded by a **test gate**. `make check` + lint must pass before
anything lands.

**Auto-commit (small, low-risk) — straight to `main`, only if the test gate is green:**
- Rates refresh **with a verified official source citation**.
- Dependency/version bumps that pass smoke tests.
- Docs, comments, broken-link fixes, typo fixes.
- New tests, defensive input validation, small error-handling hardening (≲ ~50 lines,
  no behavior change to payroll/tax math).
- The daily report file itself.

**Open a PR (do NOT commit) — for anything significant:**
- **Any change to payroll/tax calculation logic** (`actions/gaji.py`, rate *formulas*).
  Numbers people trust are never auto-changed.
- **Model tier default changes.** When a new model **wins** its tier benchmark, the agent
  opens a PR updating the tier default in `install.sh` + `RESULTS` with the bench numbers.
  Tiers move on review, not silently.
- New actions/skills, architecture changes, anything user-facing or > ~50 lines.

**Never:**
- Touch `LICENSE`, delete user data/`brain/` contents, or commit secrets.
- Change a rate **without** an official source URL + effective date.
- Force-push, rewrite history, or merge its own PRs.

Branch convention: PRs land on `maint/<topic>-YYYY-MM-DD`. Reports land on `main`.

---

## 5. Improvement backlog (the agent pulls from here)

Keep this list fed; the agent does one item/day. Current seed (from strategy):
- [ ] Make model selection first-class + hardware-tiered in `install.sh` (S/M/L tiers).
- [ ] `rates/2027.json` pipeline + in-product "rates freshness" check.
- [ ] Payslip PDF export from `gaji` (a clear Pro feature).
- [ ] MyInvois skill: generate compliant fields, validate TIN.
- [ ] Input validation + error messages across actions (hardening).
- [ ] Test coverage for `gaji` rate math against known-good fixtures.
- [ ] GUI installer (.dmg/.exe) bundling Ollama + model.

---

## 6. Model-watch criteria (summary)

A new model is a candidate if it (a) fits a hardware tier's RAM budget at Q4, (b) speaks
usable BM, (c) does reliable tool/JSON calling. It **wins** a tier only if it beats the
current pick on the blend of tok/s, BM quality, and tool-calling accuracy at equal or
lower RAM. Full methodology + the live leaderboard: `kacangje-private/BENCHMARK_PLAN.md`
and `RESULTS.md`. Current tier picks: see `install.sh`.

---

## 7. Community & contribution flow (open-source)

kacangje is public and open to contributors. The community surface and the review/merge
policy below are part of the daily loop's feedback step.

### Surfaces
- **GitHub Discussions = the forum.** Categories: *Announcements · Ideas · Q&A (Tanya/Tolong)
  · Show & tell · Rates & compliance · Loghat/BM*. Ideas/feature requests go here (votable),
  **not** Issues. Bilingual BM/English.
- **Issues = bugs only** (template at `.github/ISSUE_TEMPLATE/`). Blank issues disabled;
  config routes questions/ideas to Discussions and security to a private advisory.
- **PRs** use `.github/PULL_REQUEST_TEMPLATE.md`. `.github/CODEOWNERS` auto-requests the
  human maintainer on trust-critical paths.
- **Discord** is a Phase-1 add when Discussions volume justifies it — not day one.
- The highest-leverage contributions are **skills, actions, and rate packs** — the
  `oh-my-kacangje` flywheel. `CONTRIBUTING.md` makes each a ~10-minute job.

### The test gate (CI)
`.github/workflows/ci.yml` runs on every PR (using `pull_request`, so forked code never
sees secrets): bash/python syntax lint, **rates JSON must carry `source` + `effective`**,
and `make check`. A PR is not mergeable until CI is green.

### Who may merge what (external PRs)
- ✅ **Auto-lane** — docs, typo fixes, self-contained new `skills/*.md`, templates: the
  agent/bot may approve + merge **after CI is green** and CODEOWNERS is satisfied.
- 🔍 **Human-merge required** — anything touching payroll/tax math (`actions/gaji.py`,
  rate *formulas*), **any rate change** (verify the official source!), new actions, install/
  CLI contract, or core. CODEOWNERS forces a maintainer review on these paths.
- 🤖 **The agent's authority on contributor PRs:** triage, label, thank, run the test gate,
  review, request changes, and *recommend*. It may merge **only** the auto-lane above. It
  **never** merges trust-critical PRs and **never** merges its own PRs. Rate PRs without a
  verified official source are blocked, not merged.

### Daily loop additions (feeds §3 step 2)
Each run the agent also: triages new Discussions + Issues + PRs; answers easy questions;
labels and routes (idea→Discussions, bug→Issue); reviews open contributor PRs against the
gate + this policy; merges only the auto-lane; and summarizes community health (new
contributors, recurring asks, stale PRs) in the report.
