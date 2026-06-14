#!/usr/bin/env python3
"""
excel-analisis — Analyze Excel CSV data
Usage: python3 excel-analisis.py '{"file": "/path/to/data.csv", "analysis": "summary"}'
analysis: summary, profit, trend, top
"""
import json, sys, csv, os
from pathlib import Path
from collections import Counter

def analyze(data):
    filepath = data.get("file", "")
    analysis = data.get("analysis", "summary")
    column = data.get("column", "")
    top_n = int(data.get("top_n", 5))

    if not filepath or not os.path.exists(filepath):
        return {"success": False, "error": f"Fail '{filepath}' tak jumpa. Guna path penuh."}

    # Read CSV
    rows = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            rows.append(row)

    if not rows:
        return {"success": True, "summary": "Fail kosong.", "rows": 0}

    result = {
        "success": True,
        "file": filepath,
        "rows": len(rows),
        "columns": headers,
        "analysis": analysis,
    }

    if analysis == "summary":
        result["summary"] = f"{len(rows)} baris data, {len(headers)} kolom: {', '.join(headers)}"

    elif analysis == "profit" and column:
        # Find numeric column for profit analysis
        values = []
        for r in rows:
            try:
                v = float(r.get(column, 0))
                values.append(v)
            except (ValueError, TypeError):
                pass
        if values:
            result["summary"] = f"Analisis '{column}': Avg=RM{sum(values)/len(values):,.2f}, Max=RM{max(values):,.2f}, Min=RM{min(values):,.2f}, Total=RM{sum(values):,.2f}"
            result["stats"] = {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "avg": round(sum(values)/len(values), 2),
                "total": round(sum(values), 2),
                "count": len(values),
            }
        else:
            result["summary"] = f"Kolom '{column}' tiada data numerik."
            result["stats"] = {}

    elif analysis == "trend":
        # Return first and last values for trend detection
        result["summary"] = f"{len(rows)} titik data. Kolom: {', '.join(headers[:5])}{'...' if len(headers)>5 else ''}"
        result["preview"] = rows[:3]

    elif analysis == "top" and column:
        # Group by column, count frequency
        counter = Counter()
        for r in rows:
            val = r.get(column, "N/A")
            if val:
                counter[val] += 1
        top = counter.most_common(top_n)
        result["summary"] = f"Top {top_n} dalam '{column}': {' | '.join(f'{v}({c})' for v,c in top)}"
        result["top"] = [{"value": v, "count": c} for v, c in top]
    else:
        result["summary"] = f"{len(rows)} baris data. Hantar dengan 'analysis': 'profit' atau 'top' untuk analisis lanjut."

    return result


if __name__ == "__main__":
    data = json.loads(sys.stdin.read() if not sys.argv[1:] else sys.argv[1])
    result = analyze(data)
    print(json.dumps(result, indent=2))
