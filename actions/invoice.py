#!/usr/bin/env python3
"""
invoice — Generate simple invoice template as HTML (printable)
Usage: python3 invoice.py '{"client": "Kedai Ali Sdn Bhd", "items": [["Servis A", 2, 100], ["Servis B", 1, 250]]}'
Output: JSON with HTML invoice + summary
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path(__file__).resolve().parent.parent)))
RATES_DIR = KACANGJE_DIR / "rates"


def default_sst():
    """Read the default invoice SST rate from rates/, fall back to 8%."""
    try:
        files = sorted(RATES_DIR.glob("[0-9][0-9][0-9][0-9].json"))
        if files:
            with open(files[-1]) as f:
                return float(json.load(f).get("sst", {}).get("common_invoice_default_pct", 8))
    except Exception:
        pass
    return 8.0


def generate(data):
    client = data.get("client", "Pelanggan")
    company = data.get("company", "Syarikat Anda Sdn Bhd")
    company_addr = data.get("company_addr", "")
    invoice_no = data.get("invoice_no", f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    items = data.get("items", [])
    tax_rate = float(data.get("tax_rate", default_sst()))  # SST from rates/
    discount = float(data.get("discount", 0))

    if not items:
        return {"success": False, "error": "Tiada item dalam invoice."}
    if not (0 <= tax_rate <= 100):
        return {"success": False, "error": f"Kadar cukai mesti antara 0 dan 100 (bukan {tax_rate}%)."}
    if discount < 0:
        return {"success": False, "error": "Diskaun tidak boleh negatif."}

    rows = []
    subtotal = 0
    for i, item in enumerate(items):
        desc = item[0] if len(item) > 0 else "Item"
        qty = float(item[1]) if len(item) > 1 else 1
        price = float(item[2]) if len(item) > 2 else 0
        if qty < 0 or price < 0:
            return {"success": False, "error": f"Kuantiti dan harga tidak boleh negatif (item {i+1}: qty={qty}, harga={price})."}
        total = qty * price
        subtotal += total
        rows.append({"description": desc, "qty": qty, "price": price, "total": round(total, 2)})

    tax_amount = subtotal * tax_rate / 100
    total_with_tax = subtotal + tax_amount
    grand_total = total_with_tax - discount

    # Generate HTML
    now = datetime.now().strftime("%d/%m/%Y")
    items_html = ""
    for r in rows:
        items_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{r['description']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">{r['qty']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;">RM {r['price']:,.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:right;">RM {r['total']:,.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ms">
<head><meta charset="UTF-8"><title>Invoice {invoice_no}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #f8fafc; text-align: left; padding: 8px 12px; border-bottom: 2px solid #e2e8f0; }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;margin-bottom:40px;">
    <div>
        <h1 style="margin:0;font-size:24px;color:#1e293b;">INVOIS</h1>
        <p style="color:#64748b;margin:4px 0;">No: {invoice_no}</p>
        <p style="color:#64748b;margin:4px 0;">Tarikh: {now}</p>
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
    <p style="margin:4px 0;">SST ({tax_rate}%): RM {tax_amount:,.2f}</p>"""
    if discount > 0:
        html += f'<p style="margin:4px 0;">Diskaun: -RM {discount:,.2f}</p>'
    html += f"""
    <p style="margin:8px 0;font-size:18px;font-weight:bold;">Jumlah: RM {grand_total:,.2f}</p>
</div>

<p style="margin-top:40px;color:#64748b;font-size:12px;text-align:center;">Terima kasih atas urusan anda.</p>
</body>
</html>"""

    return {
        "success": True,
        "summary": f"Invoice {invoice_no} untuk {client}: RM {grand_total:,.2f} (termasuk SST {tax_rate}%)",
        "html": html,
        "invoice_no": invoice_no,
        "client": client,
        "total": round(grand_total, 2),
        "items": len(items),
    }


if __name__ == "__main__":
    data = json.loads(sys.stdin.read() if not sys.argv[1:] else sys.argv[1])
    result = generate(data)
    print(json.dumps(result, indent=2))
