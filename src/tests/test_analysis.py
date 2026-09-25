from pathlib import Path

import pytest

from analysis import analyze, category, merchant
from report import render

SAMPLES = Path(__file__).parents[2] / "samples"


def sample(name):
    return analyze((SAMPLES / name).read_text())


@pytest.mark.parametrize("name, rows, fmt", [
    ("chase.csv", 18, "amount"),
    ("bofa.csv", 11, "amount"),
    ("capitalone.csv", 8, "debit-credit"),
])
def test_reads_each_bank_format(name, rows, fmt):
    report = sample(name)
    assert report["rows"] == rows
    assert report["format"] == fmt


def test_merchant_ignores_store_numbers():
    assert merchant("KROGER #512") == merchant("KROGER #513") == "KROGER"
    assert merchant("SHELL OIL 88213") == "SHELL OIL"


def test_category_rules():
    assert category("KROGER #512") == "Groceries"
    assert category("SHELL OIL 88213") == "Gas"
    assert category("UBER EATS") == "Dining"
    assert category("SOMETHING ELSE") == "Other"


def test_recurring_charges():
    merchants = {r["merchant"] for r in sample("chase.csv")["recurring"]}
    assert {"NETFLIX.COM", "PLANET FITNESS"} <= merchants
    assert "KROGER" not in merchants  # amounts vary more than 10%


def test_double_charges():
    doubles = sample("chase.csv")["double_charges"]
    assert doubles == [{"merchant": "KROGER", "amount": 84.20, "dates": ["2026-09-03", "2026-09-03"]}]
    assert [d["merchant"] for d in sample("capitalone.csv")["double_charges"]] == ["BEST BUY"]


def test_totals():
    totals = sample("chase.csv")["totals"]
    assert totals["money_in"] == 9600.00
    assert totals["biggest"] == {"description": "KROGER #512", "amount": 92.17}


def test_debit_credit_signs():
    report = sample("capitalone.csv")
    assert report["totals"]["money_in"] == 500.00
    assert report["categories"]["Groceries"] == 101.98


def test_rejects_non_bank_csv():
    with pytest.raises(ValueError):
        analyze("name,age\nbob,4\n")


def test_render_escapes_descriptions():
    report = analyze("Date,Description,Amount\n09/01/2026,<script>x</script>,-5.00\n")
    assert "<script>x" not in render(report)
