# brain/ — kacangje's local knowledge

This folder is kacangje's "brain" — local, offline grounding so the small model
gives correct, Malaysia-specific answers instead of guessing.

```
brain/
├── profile.json        # the SME's own identity (company name, SSM, address, bank)
├── memory.jsonl        # append-only short facts the assistant remembers
└── knowledge/          # static reference notes, keyword-retrieved into prompts
    ├── statutory.md    # EPF / SOCSO / EIS / PCB summary
    ├── einvoice.md     # LHDN MyInvois rules
    ├── sst.md          # SST rates
    └── cuti-umum.md    # public holidays
```

How it's used: when a user asks something, `lib/tools.py:recall()` keyword-matches
the query against `knowledge/*.md` and `memory.jsonl`, and injects the most
relevant snippets into the model's context. Deterministic numbers (payroll, tax)
still come from `rates/` and the action scripts — the brain is for *grounding
language*, not for doing math.

Keep notes short and factual. Update `rates/<year>.json` for anything numeric
that changes yearly; keep prose context here.
