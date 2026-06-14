# Menyumbang ke kacangje · Contributing

Terima kasih! 🥜 kacangje untuk SME Malaysia, dan **sumbangan paling berharga datang dari
orang yang tahu selok-belok tempatan** — terutamanya akauntan, juruaudit, dan tauke SME.
You don't need to be a programmer to help.

> English below each section. Bahasa Melayu dahulu sebab itu audiens kami.

---

## Cara bagi maklum balas (tak perlu coding) · Give feedback (no code)

- 💬 **Forum (GitHub Discussions)** — soalan, idea, "ada bug ke?", kongsi skill. Mula di sini.
  → tab **Discussions** di repo. Kategori: *Pengumuman · Idea · Tanya/Tolong · Show & tell ·
  Kadar & pematuhan (rates) · Loghat/BM*.
- 🐞 **Bug** — guna **Issues → Bug report**. Bagi langkah, RAM laptop, model yang diguna.
- 💡 **Idea / feature** — buka **Discussions → Idea** (bukan Issue) supaya orang boleh undi.

---

## Jenis sumbangan paling berguna · Highest-leverage contributions

You rarely need to touch core code. The flywheel is **skills, actions, and rate packs**:

### 1. Skills (`skills/*.md`) — paling senang
A skill is a markdown file with frontmatter. Copy an existing one in `skills/`, change the
prompt, open a PR. Examples wanted: surat-surat rasmi, emel industri tertentu, format minit.

### 2. Actions (`actions/*.py`) — deterministik
Python scripts for SME tasks (gaji, invois, sebut harga...). New ones welcome — keep them
**stdlib-only**, self-contained, and register them in `actions/manifest.json`.

### 3. Rate / compliance packs (`rates/<year>.json`) — **paling kritikal**
Kadar EPF/SOCSO/EIS/PCB/SST/e-Invois. **WAJIB sertakan sumber rasmi.** Setiap kadar mesti
ada `source` (URL KWSP/PERKESO/LHDN) dan `effective` (tarikh kuat kuasa). PR tanpa sumber
rasmi **tidak akan di-merge** — ini lapisan kepercayaan produk.

---

## Aliran PR · PR workflow

1. Fork → branch (`skill/emel-klinik`, `fix/gaji-ot`, `rates/2027-epf`).
2. Pastikan ia lulus **test gate**: `make check`, `bash -n kacangje`, dan
   `python3 -m py_compile` untuk fail Python yang disentuh. CI akan jalankan ini automatik.
3. Isi templat PR (apa, kenapa, sumber kalau kadar).
4. Tunggu review. Lihat **siapa review apa** di bawah.

### Siapa boleh merge apa · Merge policy
- ✅ **Auto-lane (CI + maintainer/bot review):** dokumentasi, pembetulan typo, skill baru
  yang self-contained, templat — boleh di-merge laju lepas CI hijau.
- 🔍 **Review wajib oleh maintainer manusia:** apa-apa yang sentuh **kira gaji/cukai**
  (`actions/gaji.py`, formula kadar), perubahan kadar (semak sumber!), action baru, atau
  perubahan teras. Nombor yang orang percaya tak di-merge tanpa mata manusia.
- 🤖 Maintenance bot kami boleh review, label, jalankan ujian, dan cadang — **tapi tak merge
  PR sensitif sendiri.** Lihat `MAINTENANCE.md` §4 & §7.

---

## Peraturan asas · Ground rules
- Stdlib-only di mana boleh (janji "jalan atas potato" — no npm, minimal deps).
- Jangan ubah `LICENSE`. Jangan masukkan rahsia/secret. Jangan ubah kadar tanpa sumber.
- Hormat: lihat [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Lesen sumbangan: Apache-2.0, sama macam projek. Kacang je — terima kasih sebab tolong! 🇲🇾
