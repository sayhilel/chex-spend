from html import escape

STYLE = """
body { font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #222; }
table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }
td, th { text-align: left; padding: .4rem; border-bottom: 1px solid #ddd; }
td.num { text-align: right; }
.note { color: #666; font-size: .9rem; }
"""


def usd(amount):
    return f"${amount:,.2f}"


def table(headers, rows):
    head = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>" if headers else ""
    body = "".join(
        "<tr>" + "".join(f'<td class="num">{c}</td>' if c.startswith("$") else f"<td>{c}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table>{head}{body}</table>"


def render(report):
    t = report["totals"]
    biggest = t["biggest"]
    categories = [(escape(k), usd(v)) for k, v in report["categories"].items()]
    recurring = [(escape(r["merchant"]), usd(r["amount"]), str(r["months"])) for r in report["recurring"]]
    doubles = [(escape(d["merchant"]), usd(d["amount"]), " and ".join(d["dates"])) for d in report["double_charges"]]

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Spending Checkup</title><style>{STYLE}</style></head><body>
<h1>Your Spending Checkup</h1>
<p class="note">{report["rows"]} transactions from {report["start"]} to {report["end"]}.
This report and your file are deleted automatically after 7 days.</p>

<h2>Totals</h2>
{table(None, [
    ("Money in", usd(t["money_in"])),
    ("Money out", usd(t["money_out"])),
    ("Biggest purchase", f'{escape(biggest["description"])} ({usd(biggest["amount"])})' if biggest else "None"),
])}

<h2>Spending by category</h2>
{table(["Category", "Spent"], categories)}

<h2>Recurring charges</h2>
{table(["Merchant", "About", "Months seen"], recurring) if recurring else "<p>None found.</p>"}

<h2>Possible double charges</h2>
{table(["Merchant", "Amount", "Dates"], doubles) if doubles else "<p>None found.</p>"}

<p><a href="/">Check another file</a></p>
</body></html>"""
