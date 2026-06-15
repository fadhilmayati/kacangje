#!/usr/bin/env python3
"""
quotation — Generate a printable quotation (sebut harga) as HTML.
One of the most common SME documents — sent before an invoice to win a job.
Usage: python3 quotation.py '{"client": "Kedai Ali", "items": [["Servis A", 2, 100]], "valid_days": 30}'
Output: JSON with HTML quotation + summary
"""
import json, sys, os
from pathlib import Path
from datetime import datetime, timedelta

KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path(__file__).resolve().parent.parent)))
RATES_DIR = KACANGJE_DIR / "rates"
PROFILE_FILE = KACANGJE_DIR / "brain" / "profile.json"


def _load_profile():
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _default_sst():
    try:
        files = sorted(RATES_DIR.glob("[0-9][0-9][0-9][0-9].json"))
        if files:
            with open(files[-1]) as f:
                return float(json.load(f).get("sst", {}).get("common_invoice_default_pct", 8))
    except Exception:
        pass
    return 8.0


def generate(data):
    profile = _load_profile()
    client = data.get("client", "Pelanggan")
    company = data.get("company") or profile.get("company_name") or "Syarikat Anda Sdn Bhd"
    company_addr = data.get("company_addr") or profile.get("address", "")
    quote_no = data.get("quote_no", f"SH-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    items = data.get("items", [])
    tax_rate = float(data.get("tax_rate", _default_sst()))
    discount = float(data.get("discount", 0))
    valid_days = int(data.get("valid_days", 30))
    notes = data.get("notes", "")

    if not items:
        return {"success": False, "error": "Tiada item dalam sebut harga."}
    if not (0 <= tax_rate <= 100):
        return {"success": False, "error": f"Kadar cukai mesti antara 0 dan 100 (bukan {tax_rate}%)."}
    if discount < 0:
        return {"success": False, "error": "Diskaun tidak boleh negatif."}

    rows = []
    subtotal = 0.0
    for i, item in enumerate(items):
        desc = item[0] if len(item) > 0 else "Item"
        qty = float(item[1]) if len(item) > 1 else 1
        price = float(item[2]) if len(item) > 2 else 0
        if qty < 0 or price < 0:
            return {"success": False, "error": f"Kuantiti dan harga tidak boleh negatif (item {i+1}: qty={qty}, harga={price})."}
        line_total = qty * price
        subtotal += line_total
        rows.append({"description": desc, "qty": qty, "price": price, "total": round(line_total, 2)})

    tax_amount = subtotal * tax_rate / 100
    grand_total = subtotal + tax_amount - discount

    now = datetime.now()
    valid_until = (now + timedelta(days=valid_days)).strftime("%d/%m/%Y")

    items_html = ""
    for r in rows:
        items_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{r['description']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">{r['qty']:g}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;">RM {r['price']:,.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;">RM {r['total']:,.2f}</td>
        </tr>"""

    notes_html = f'<p style="color:#64748b;margin-top:24px;">{notes}</p>' if notes else ""
    discount_html = f'<p style="margin:4px 0;">Diskaun: -RM {discount:,.2f}</p>' if discount > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="ms">
<head><meta charset="UTF-8"><title>Sebut Harga {quote_no}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #f8fafc; text-align: left; padding: 8px 12px; border-bottom: 2px solid #e2e8f0; }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;margin-bottom:40px;">
    <div>
        <h1 style="margin:0;font-size:24px;color:#1e293b;">SEBUT HARGA</h1>
        <p style="color:#64748b;margin:4px 0;">No: {quote_no}</p>
        <p style="color:#64748b;margin:4px 0;">Tarikh: {now.strftime('%d/%m/%Y')}</p>
        <p style="color:#64748b;margin:4px 0;">Sah sehingga: {valid_until}</p>
    </div>
    <div style="text-align:right;">
        <strong>{company}</strong>
        <p style="color:#64748b;margin:4px 0;">{company_addr}</p>
    </div>
</div>

<div style="margin-bottom:24px;">
    <strong>Kepada:</strong><br>
    {client}
</div>

<table>
    <tr><th>Perkara</th><th style="text-align:center;">Kuantiti</th><th style="text-align:right;">Harga</th><th style="text-align:right;">Jumlah</th></tr>
    {items_html}
</table>

<div style="margin-top:20px;text-align:right;">
    <p style="margin:4px 0;">Subjumlah: <strong>RM {subtotal:,.2f}</strong></p>
    <p style="margin:4px 0;">SST ({tax_rate:g}%): RM {tax_amount:,.2f}</p>
    {discount_html}
    <p style="margin:8px 0;font-size:18px;font-weight:bold;">Jumlah: RM {grand_total:,.2f}</p>
</div>
{notes_html}
<p style="margin-top:40px;color:#64748b;font-size:12px;text-align:center;">Sebut harga ini sah selama {valid_days} hari. Terima kasih.</p>
</body>
</html>"""

    return {
        "success": True,
        "summary": f"Sebut harga {quote_no} untuk {client}: RM {grand_total:,.2f} (sah {valid_days} hari, hingga {valid_until})",
        "html": html,
        "quote_no": quote_no,
        "client": client,
        "total": round(grand_total, 2),
        "valid_until": valid_until,
        "items": len(items),
    }


if __name__ == "__main__":
    data = json.loads(sys.stdin.read() if not sys.argv[1:] else sys.argv[1])
    result = generate(data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
