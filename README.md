# 🥜 kacangje

**Pembantu AI offline untuk SME Malaysia. Satu install, terus guna. Kacang je.**

> *"Kacang je"* — slang Malaysia: **senang sangat**. Itulah matlamat kami: AI untuk
> kerja pejabat SME yang **satu install away** — tak perlu jadi programmer, tak perlu
> internet, tak perlu bayar bil API.

100% offline · 100% percuma · Bahasa Melayu · jalan atas laptop biasa

---

## Kenapa kacangje?

- 🔒 **Privasi penuh** — data gaji, pelanggan, invois anda **tak keluar dari laptop**.
- 🇲🇾 **Faham Malaysia** — EPF, SOCSO, EIS, PCB, SST, e-Invois LHDN, Bahasa Melayu & loghat.
- 💸 **Tiada bil API** — guna model tempatan (Mesolitica) melalui Ollama.
- ⚡ **Kacang je** — `kacangje web` dan terus guna.

Bina di atas model GRPO Malaysia oleh [Mesolitica](https://huggingface.co/mesolitica).

---

## Install (satu arahan)

```bash
curl -fsSL https://raw.githubusercontent.com/fadhilmayati/kacangje/main/install.sh | bash
```

Atau manual:

```bash
git clone https://github.com/fadhilmayati/kacangje.git
cd kacangje
make install
```

Installer akan: pasang [Ollama](https://ollama.com), muat turun model Malaysia ikut
RAM laptop anda, dan pasang `kacangje` ke PATH.

---

## Guna

```bash
kacangje web          # Buka web UI di browser (cara paling senang)
kacangje prompt       # Mod interaktif — taip apa-apa, AI tolong buat
kacangje skills       # Senarai skill (tulis surat, emel pelanggan, minit mesyuarat)
kacangje action gaji --workers 5 --gaji_pokok 2000
kacangje templates    # Browse template tugas SME
kacangje sme          # Dashboard / status
kacangje help
```

### Dalam mod `prompt` — slash commands

```
/help        tunjuk bantuan
/skills      senarai skill (taip /<nama-skill> untuk guna)
/actions     senarai action (gaji, invois, sebut harga, susun-fail)
/cari ...    carian web (maklumat terkini)
/ingat ...   simpan fakta ke "brain"
/model       tunjuk / tukar model
/keluar      keluar
```

Taip teks biasa untuk berbual — tools (kira gaji, invois, kalkulator) **auto-trigger**.

---

## Apa yang kacangje boleh buat

| Tugas | Contoh |
|-------|--------|
| 💰 **Kira gaji** | EPF/SOCSO/EIS/PCB, OT, ramai pekerja — kadar dari `rates/` yang boleh dikemas kini |
| 📄 **Invois** | HTML siap print, SST automatik |
| 📝 **Sebut harga** | Quotation profesional, tempoh sah |
| 📁 **Susun fail** | Ikut tarikh / jenis / saiz |
| 📊 **Analisis CSV** | Ringkasan, profit, top-N |
| ✍️ **Skills** | Surat rasmi, emel pelanggan, minit mesyuarat (BM) |
| 🔍 **Carian web** | Maklumat terkini bila perlu |

---

## Senibina (untuk yang nak tahu)

`kacangje` ikut prinsip ini: **model kecil = lapisan bahasa; kod Python + `rates/`
= lapisan ketepatan; `brain/` = grounding tempatan.** Nombor gaji/cukai dikira oleh
kod (bukan diteka oleh model), jadi anda boleh percaya hasilnya.

```
kacangje (CLI) → router niat (lib/tools.py) → action / skill / brain → jawapan
```

- `actions/` — skrip tugas SME (gaji, invois, sebut harga, susun-fail, excel)
- `lib/` — router niat, skills, REPL, web search, brain recall
- `rates/<tahun>.json` — kadar berkanun (EPF/SOCSO/EIS/SST/e-invois) + sumber
- `brain/` — pengetahuan tempatan + memori + profil syarikat
- `skills/` — skill berasaskan prompt (`*.md` dengan frontmatter)
- `web/` — UI web (Python stdlib, tiada npm)

---

## Penafian

Pengiraan gaji, cukai, dan caruman adalah **anggaran**. Sahkan dengan KWSP, PERKESO,
dan LHDN sebelum pemfailan rasmi. Lihat sumber dalam `rates/`.

## Lesen

[Apache-2.0](LICENSE) — percuma untuk SME, percuma untuk diubah suai.
