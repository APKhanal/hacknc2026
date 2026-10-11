import pytest

from api.cost import parse_habit


def test_coffee_range():
    h = parse_habit("How much would I lose per year if I got a coffee roughly 2-3 times per week  costing about 7 dollars each time")
    assert (h.low_year, h.high_year, h.period) == (7 * 2 * 52, 7 * 3 * 52, "week")


@pytest.mark.parametrize("text,year", [
    ("How much does a $15 a month subscription cost me per year?", 180),
    ("how much would I spend a year on $5 lunch every day", 5 * 365),
    ("how much would I lose per year if I buy a $4 coffee twice a week", 4 * 2 * 52),
])
def test_other_forms(text, year):
    assert parse_habit(text).mid_year == year


@pytest.mark.parametrize("text", ["Can I afford $1400 today?", "how much per year is a coffee", "I spend $5 and $6 a week, how much a year"])
def test_not_habits(text):
    assert parse_habit(text) is None
