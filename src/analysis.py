import csv
import io
import re
import statistics
from collections import defaultdict
from datetime import datetime

DATE_COLUMNS = ["Date", "Posting Date", "Transaction Date", "Posted Date"]
DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"]

CATEGORY_RULES = {
    "Groceries": ["KROGER", "WALMART", "WHOLE FOODS", "TRADER JOE", "ALDI", "SAFEWAY", "PUBLIX", "COSTCO"],
    "Dining": ["STARBUCKS", "MCDONALD", "CHIPOTLE", "DOORDASH", "UBER EATS", "GRUBHUB", "PIZZA", "CAFE", "RESTAURANT"],
    "Gas": ["SHELL", "CHEVRON", "EXXON", "BP ", "MOBIL", "SUNOCO", "SPEEDWAY"],
    "Shopping": ["AMAZON", "TARGET", "BEST BUY", "EBAY", "ETSY", "IKEA"],
    "Bills": ["COMCAST", "XFINITY", "VERIZON", "AT&T", "T-MOBILE", "ELECTRIC", "WATER", "INSURANCE", "RENT"],
    "Subscriptions": ["NETFLIX", "SPOTIFY", "HULU", "DISNEY", "APPLE.COM", "YOUTUBE", "GYM", "PLANET FITNESS"],
    "Transport": ["UBER", "LYFT", "PARKING", "TRANSIT"],
}


def parse(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    headers = [h.strip() for h in reader.fieldnames or []]
    reader.fieldnames = headers

    date_col = next((c for c in DATE_COLUMNS if c in headers), None)
    if not date_col or "Description" not in headers:
        raise ValueError("Could not find Date and Description columns")
    if "Amount" in headers:
        bank_format = "amount"
    elif "Debit" in headers and "Credit" in headers:
        bank_format = "debit-credit"
    else:
        raise ValueError("Could not find Amount, or Debit and Credit, columns")

    rows = []
    for raw in reader:
        if not raw.get(date_col):
            continue
        if bank_format == "amount":
            amount = money(raw["Amount"])
        else:
            amount = money(raw["Credit"]) - money(raw["Debit"])
        rows.append({
            "date": parse_date(raw[date_col]),
            "description": raw["Description"].strip(),
            "amount": amount,
        })
    if not rows:
        raise ValueError("No transactions found")
    return rows, bank_format


def money(text):
    text = (text or "").replace("$", "").replace(",", "").strip()
    return round(float(text), 2) if text else 0.0


def parse_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {text}")


def merchant(description):
    name = re.sub(r"\S*\d\S*", "", description.upper())
    return " ".join(name.split()) or description.upper()


def category(description):
    text = description.upper()
    for name, keywords in CATEGORY_RULES.items():
        if any(k in text for k in keywords):
            return name
    return "Other"


def by_category(rows):
    totals = defaultdict(float)
    for r in rows:
        if r["amount"] < 0:
            totals[category(r["description"])] += -r["amount"]
    return dict(sorted(((k, round(v, 2)) for k, v in totals.items()), key=lambda kv: -kv[1]))


def recurring(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["amount"] < 0:
            groups[merchant(r["description"])].append(r)

    found = []
    for name, charges in groups.items():
        months = {(r["date"].year, r["date"].month) for r in charges}
        amounts = [-r["amount"] for r in charges]
        typical = statistics.median(amounts)
        if len(months) >= 2 and all(abs(a - typical) <= typical * 0.10 for a in amounts):
            found.append({"merchant": name, "amount": round(typical, 2), "months": len(months)})
    return sorted(found, key=lambda f: -f["amount"])


def double_charges(rows):
    spending = sorted((r for r in rows if r["amount"] < 0), key=lambda r: r["date"])
    found = []
    for i, a in enumerate(spending):
        for b in spending[i + 1:]:
            if (b["date"] - a["date"]).days > 2:
                break
            if b["amount"] == a["amount"] and merchant(b["description"]) == merchant(a["description"]):
                found.append({"merchant": merchant(a["description"]), "amount": -a["amount"],
                              "dates": [a["date"].isoformat(), b["date"].isoformat()]})
    return found


def totals(rows):
    spending = [r for r in rows if r["amount"] < 0]
    biggest = min(spending, key=lambda r: r["amount"], default=None)
    return {
        "money_in": round(sum(r["amount"] for r in rows if r["amount"] > 0), 2),
        "money_out": round(-sum(r["amount"] for r in spending), 2),
        "biggest": {"description": biggest["description"], "amount": -biggest["amount"]} if biggest else None,
    }


def analyze(csv_text):
    rows, bank_format = parse(csv_text)
    return {
        "rows": len(rows),
        "format": bank_format,
        "start": min(r["date"] for r in rows).isoformat(),
        "end": max(r["date"] for r in rows).isoformat(),
        "categories": by_category(rows),
        "recurring": recurring(rows),
        "double_charges": double_charges(rows),
        "totals": totals(rows),
    }
