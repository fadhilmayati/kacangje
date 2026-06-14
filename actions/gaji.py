#!/usr/bin/env python3
"""
kira-gaji — Calculate monthly payroll for SME
Usage: python3 gaji.py '{"workers": 20, "gaji_pokok": 2000, "ot_hours": 10, "ot_rate": 1.5}'
Output: JSON with breakdown

Statutory rates are loaded from rates/<year>.json so they can be updated
without touching code. Numbers are estimates — verify with KWSP/PERKESO/LHDN.
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

KACANGJE_DIR = Path(os.environ.get("KACANGJE_DIR", str(Path(__file__).resolve().parent.parent)))
RATES_DIR = KACANGJE_DIR / "rates"


def load_rates(year=None):
    """Load the rates file for a year, falling back to the latest available."""
    year = year or datetime.now().year
    candidate = RATES_DIR / f"{year}.json"
    if not candidate.exists():
        # fall back to the most recent rates file we have
        files = sorted(RATES_DIR.glob("[0-9][0-9][0-9][0-9].json"))
        if not files:
            return None
        candidate = files[-1]
    try:
        with open(candidate) as f:
            return json.load(f)
    except Exception:
        return None


def calculate(data):
    workers = max(1, int(data.get("workers", 1)))
    gaji_pokok = max(0.0, float(data.get("gaji_pokok", 1500)))
    ot_hours = float(data.get("ot_hours", 0))
    ot_rate = float(data.get("ot_rate", 1.5))
    elaun = float(data.get("elaun", 0))  # allowances
    potongan_lain = float(data.get("potongan_lain", 0))  # other deductions

    rates = load_rates()
    if not rates:
        return {"success": False, "error": "Fail kadar (rates/) tak jumpa. Tak boleh kira gaji tanpa kadar rasmi."}

    epf = rates["epf"]
    socso_r = rates["socso"]
    eis_r = rates["eis"]
    pcb_r = rates.get("pcb", {})

    # OT calculation (hourly = monthly / 26 / 8)
    hourly_rate = gaji_pokok / 26 / 8
    ot_pay = ot_hours * hourly_rate * ot_rate

    gaji_kasar = gaji_pokok + ot_pay + elaun

    # EPF — employee fixed; employer rate depends on wage threshold
    epf_employee = gaji_kasar * epf["employee_rate_pct"] / 100
    if gaji_kasar <= epf["wage_threshold"]:
        epf_employer_rate = epf["employer_rate_pct_below_5000"]
    else:
        epf_employer_rate = epf["employer_rate_pct_above_5000"]
    epf_employer = gaji_kasar * epf_employer_rate / 100

    # SOCSO — % of wages capped at the wage ceiling
    socso_wage = min(gaji_kasar, socso_r["wage_ceiling"])
    socso = round(socso_wage * socso_r["employee_rate_pct"] / 100, 2)

    # EIS — % of wages capped at the wage ceiling
    eis_wage = min(gaji_kasar, eis_r["wage_ceiling"])
    eis = round(eis_wage * eis_r["employee_rate_pct"] / 100, 2)

    # PCB — rough estimate only (real PCB depends on reliefs/dependants)
    pcb_threshold = pcb_r.get("estimate_threshold", 3000)
    pcb_pct = pcb_r.get("rough_estimate_pct", 3.0)
    pcb = round(gaji_kasar * pcb_pct / 100, 2) if gaji_kasar > pcb_threshold else 0

    total_potongan = epf_employee + socso + eis + pcb + potongan_lain
    gaji_bersih = gaji_kasar - total_potongan

    per_worker = {
        "gaji_pokok": round(gaji_pokok, 2),
        "ot_pay": round(ot_pay, 2),
        "elaun": round(elaun, 2),
        "gaji_kasar": round(gaji_kasar, 2),
        "epf_employee": round(epf_employee, 2),
        "epf_employer": round(epf_employer, 2),
        "socso": socso,
        "eis": eis,
        "pcb": pcb,
        "potongan_lain": round(potongan_lain, 2),
        "total_potongan": round(total_potongan, 2),
        "gaji_bersih": round(gaji_bersih, 2),
    }

    total = {k: round(v * workers, 2) for k, v in per_worker.items()}
    total["workers"] = workers
    total["per_worker"] = per_worker

    # Trust layer: show which rates/sources were used
    min_wage = rates.get("minimum_wage", {}).get("monthly")
    warnings = []
    if min_wage and gaji_pokok < min_wage:
        warnings.append(
            f"Gaji pokok RM{gaji_pokok:,.2f} di bawah gaji minimum RM{min_wage:,.2f} (berkuat kuasa {rates['minimum_wage'].get('effective_from')})."
        )

    return {
        "success": True,
        "summary": f"Gaji untuk {workers} pekerja: RM{gaji_bersih:,.2f} seorang (bersih). Jumlah: RM{total['gaji_bersih']:,.2f}",
        "per_worker": per_worker,
        "total": total,
        "rates_used": {
            "year": rates.get("year"),
            "epf_employee_pct": epf["employee_rate_pct"],
            "epf_employer_pct": epf_employer_rate,
            "socso_pct": socso_r["employee_rate_pct"],
            "socso_ceiling": socso_r["wage_ceiling"],
            "eis_pct": eis_r["employee_rate_pct"],
            "eis_ceiling": eis_r["wage_ceiling"],
        },
        "warnings": warnings,
        "disclaimer": rates.get("disclaimer", ""),
    }


if __name__ == "__main__":
    data = json.loads(sys.stdin.read() if not sys.argv[1:] else sys.argv[1])
    result = calculate(data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
