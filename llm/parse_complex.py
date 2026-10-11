"""Complex finance questions: income changes, several items, loans and mortgages.

Regex grammar first, Gemini fallback second. Both produce the same small
`spec` dict of raw numbers *as written in the text*; code (never the LLM)
turns the spec into cash-flow items and computes loan payments. Every dollar
amount, percentage and loan term in the text must be accounted for by the spec
(and vice versa), otherwise the question is refused rather than guessed.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date

from core.housing import is_home_loan
from core.income import NET_FACTOR
from core.loans import DAYS_PER_MONTH, loan_decision
from core.model import Decision, DecisionDelta

MAX_START_DAY = 730
DAYS_PER_YEAR_MONTHLY = 365 / 12  # an annual salary paid monthly

HINT = ("I couldn't tell how every number fits in. Try one clear sentence, for example: "
        "\"Can I afford a $350k house with 20% down at 7% over 30 years?\" or "
        "\"I got a $500/month raise, can I afford $1,200/month rent?\"")

INCOME_CUES = ("make", "making", "earn", "salary", "raise", "income", "job", "wage", "promotion",
               "bonus", "hired", "offer", "freelance", "gig")
PURCHASE_CUES = ("house", "home", "condo", "mortgage", "loan", "car", "borrow", "financ", "financed",
                 "financing", "lease")
NET_WORDS = ("take-home", "take home", "after tax", "after-tax", "net ", "deposit")
REPLACE_CUES = (" make ", "new job", "got a job", "got the job", "job making", "job paying", "salary", "promotion",
                "hired", "offer", "making", "earning")
ADDITIVE_CUES = ("raise", "bonus", "freelance", "gig", "extra", "additional")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"])}

_TOKEN = re.compile(
    r"(?P<dollar>\$)?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<k>[kK](?![a-zA-Z]))?"
    r"(?P<pct>\s?%|\s?percent\b)?"
    r"(?:\s?-?\s?(?P<unit>years?|yrs?|months?|mos?|days?|weeks?|wks?)\b)?"
    r"(?P<ord>st|nd|rd|th)?(?!\w)")


class ComplexParseError(ValueError):
    """Regex grammar couldn't account for the text; try the LLM fallback."""


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z'$/%-]+", s.lower())


def tokenize(text: str):
    """Numeric tokens with kind: money | pct | term | timing | date."""
    toks = []
    for m in _TOKEN.finditer(text):
        raw = m["num"].replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        if m["k"]:
            val *= 1000
        before = text[:m.start()].lower()
        after = text[m.end():].lower()
        tok = {"value": val, "start": m.start(), "end": m.end(), "dollar": bool(m["dollar"]), "text": m[0]}
        unit = (m["unit"] or "").lower()
        if m["pct"]:
            tok["kind"] = "pct"
        elif m["ord"]:
            tok["kind"] = "date"
        elif unit:
            u = ("year" if unit.startswith(("y",)) else "month" if unit.startswith("mo")
                 else "week" if unit.startswith("w") else "day")
            tok["unit"] = u
            # "in 3 days" delays the start; every other duration is a loan/payment term.
            tok["kind"] = "timing" if re.search(r"\b(in|after|within)\s*$", before) else "term"
            if u in ("day", "week") and tok["kind"] != "timing":
                tok["kind"] = "term"  # unsupported unit; regex_spec refuses it
        elif re.search(r"\b(" + "|".join(MONTHS) + r")\s*$", before) and val <= 31 and not m["dollar"]:
            tok["kind"] = "date"
        else:
            tok["kind"] = "money"
        # unit-less "/mo", "a year" cadences are read from `after` by the caller.
        tok["after"] = after
        tok["before"] = before
        toks.append(tok)
    return toks


_BOUNDARY = re.compile(r"(?<!\d),|,(?!\d)|[;.?!](?!\d)")


def _clause_bounds(text: str, pos: int) -> tuple[int, int]:
    """Clause = text between punctuation; commas inside numbers (1,400) don't count."""
    left = 0
    for m in _BOUNDARY.finditer(text, 0, pos):
        left = m.end()
    m = _BOUNDARY.search(text, pos)
    return left, (m.start() if m else len(text))


def _window(text: str, tok, before_n=5, after_n=4) -> str:
    lo, hi = _clause_bounds(text, tok["start"])
    pre = _words(text[lo:tok["start"]])[-before_n:]
    post = _words(text[tok["end"]:hi])[:after_n]
    return " ".join(pre) + " | " + " ".join(post)


def _cadence(after: str) -> str | None:
    a = re.sub(r"^\s*(dollars?|bucks?|usd)\b", "", after)[:30]
    if re.search(r"^\s*(/|per |a |each |every )?\s*(hour|hr)\b|/hr|an hour", a):
        raise ComplexParseError("hourly")
    if re.search(r"biweekly|bi-weekly|every two weeks|every other week|every 2 weeks", a):
        return "biweekly"
    if re.search(r"^\s*(/|per |a |each |every )\s*(mo\b|month)|^\s*(/mo|monthly)|\bmonthly\b", a):
        return "monthly"
    if re.search(r"^\s*(/|per |a |each |every )\s*(wk|week)|^\s*weekly|\bweekly\b", a):
        return "weekly"
    if re.search(r"^\s*(/|per |a |each |every )\s*(yr|year)|^\s*(annually|yearly)|\bannual", a):
        return "annual"
    return None


def _cue_distance(pre: list[str], post: list[str], cues, before_n: int = 4, after_n: int = 3) -> int | None:
    """Words between the amount and the nearest cue word (None if no cue is in range)."""
    dists = [i + 1 for i, w in enumerate(reversed(pre[-before_n:])) if _has([w], cues)]
    dists += [i + 1 for i, w in enumerate(post[:after_n]) if _has([w], cues)]
    return min(dists) if dists else None


def _has(words, cues) -> bool:
    if isinstance(words, str):
        words = _words(words)
    return any(w.startswith(c) for w in words for c in cues)


def _month_start(text: str, today: date) -> int | None:
    low = text.lower()
    for name, num in MONTHS.items():
        m = re.search(r"\b" + name + r"\b(?!\s+(i|we|you|someone)\b)(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?", low)
        if name == "may" and m and not re.search(r"\b(in|on|by|for|until|since)\s+may\b|\bmay\s+\d", low):
            continue
        if m:
            day = int(m.group(2)) if m.group(2) else 1
            year = today.year + (1 if (num, day) < (today.month, today.day) else 0)
            try:
                return (date(year, num, day) - today).days
            except ValueError:
                return None
    return None


def _start_day(clause: str, today: date, toks_in_clause) -> int | None:
    for t in toks_in_clause:
        if t["kind"] == "timing":
            n = int(t["value"])
            return n * {"day": 1, "week": 7, "month": 30, "year": 365}[t["unit"]]
    low = clause.lower()
    ms = _month_start(clause, today)
    if ms is not None:
        return ms
    if "tomorrow" in low:
        return 1
    if "next week" in low:
        return 7
    if "next month" in low:
        nm = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
        return (nm - today).days
    if "next year" in low:
        return (date(today.year + 1, 1, 1) - today).days
    if re.search(r"\b(today|now|right away|immediately)\b", low):
        return 0
    return None


def regex_spec(text: str, today: date) -> dict:
    """Build the raw-number spec from the text, or raise ComplexParseError."""
    toks = tokenize(text)
    if not toks:
        raise ComplexParseError("no numbers")
    low = text.lower()
    spec: dict = {"income": [], "expenses": [], "loans": []}

    pcts = [t for t in toks if t["kind"] == "pct"]
    terms = [t for t in toks if t["kind"] == "term"]
    money = [t for t in toks if t["kind"] == "money"]
    for t in terms:
        if t["unit"] in ("week", "day"):
            raise ComplexParseError("unsupported term unit")
    down_pct = [t for t in pcts if re.match(r"\s*(down|as a down|for the down|downpayment)", t["after"])
                or re.search(r"(down ?payment( of| is| was)?|put down)\s*$", t["before"])]
    rates = [t for t in pcts if t not in down_pct]
    if any(not 0 <= t["value"] <= 60 for t in rates):
        raise ComplexParseError("rate out of range")

    down_money, payments, purchase, expenses, incomes = [], [], [], [], []
    for t in money:
        w = _window(text, t)
        pre, post = (x.split() for x in w.split(" | "))
        lo, hi = _clause_bounds(text, t["start"])
        clause = text[lo:hi]
        cad = _cadence(t["after"])
        if "down" in post[:2] or re.search(r"down( ?payment)?( of| is| was)?$", " ".join(pre[-3:])):
            down_money.append(t)
            continue
        if "payment" in post[:3] and not _has(post[:3], ("down",)):
            payments.append((t, w, clause, cad or "monthly"))
            continue
        # The nearest cue wins: "a $400/month raise and want a $28k car" puts "raise" beside $400, "car" beside $28k.
        d_inc = _cue_distance(pre, post, INCOME_CUES)
        d_buy = _cue_distance(pre, post, PURCHASE_CUES)
        if d_inc is not None and (d_buy is None or d_inc < d_buy):
            incomes.append((t, w, clause, cad))
        elif d_buy is not None and not _has(post[:2], ("rent", "insurance", "lease")):
            purchase.append((t, w, clause, cad))
        else:
            expenses.append((t, w, clause, cad))

    # Global fallback start for purchases/expenses with no timing in their own clause.
    global_start = _start_day(text, today, [t for t in toks if t["kind"] == "timing"])

    def start_for(clause, default):
        s = _start_day(clause, today, [t for t in toks if t["kind"] == "timing"
                                       and clause.lower().find(t["text"].lower().strip()) != -1])
        return default if s is None else max(0, min(MAX_START_DAY, s))

    for t, w, clause, cad in incomes:
        if cad is None:
            if t["value"] >= 20000:
                cad = "annual"
            else:
                raise ComplexParseError("income without period")
        cl = clause.lower()
        replaces = not _has(cl, ADDITIVE_CUES) and any(c in " " + cl + " " for c in REPLACE_CUES)
        spec["income"].append({"amount": t["value"], "period": cad, "replaces": replaces,
                               "net": any(n in low for n in NET_WORDS), "start_day": start_for(clause, 0)})

    loans = [{"tok": t, "clause": clause, "cad": cad, "down": [], "down_pct": [], "rate": [], "term": [], "payment": []}
             for t, w, clause, cad in sorted(purchase, key=lambda x: x[0]["start"])]

    def owner(tok):
        """Attributes belong to the nearest purchase mentioned before them (else the first one)."""
        before = [i for i, ln in enumerate(loans) if ln["tok"]["start"] <= tok["start"]]
        return loans[before[-1] if before else 0]

    if loans:
        for t in down_money:
            owner(t)["down"].append(t)
        for t in down_pct:
            owner(t)["down_pct"].append(t)
        for t in rates:
            owner(t)["rate"].append(t)
        for t in terms:
            owner(t)["term"].append(t)
        for t, w, clause, cad in payments:
            owner(t)["payment"].append(t)
    else:
        if down_money or down_pct or rates:
            raise ComplexParseError("rate/down payment without a loan amount")
        expenses += [(t, w, clause, cad) for t, w, clause, cad in payments]
        if len(terms) > 1:
            raise ComplexParseError("several terms without loans")

    for t, w, clause, cad in expenses:
        months = None
        if terms and cad and terms[0]["unit"] in ("month", "year"):
            months = round(terms[0]["value"] * (12 if terms[0]["unit"] == "year" else 1))
        if cad is None and re.search(r"\b(rent|subscription|premium|insurance)\b", w):
            cad = "monthly"
        spec["expenses"].append({"amount": t["value"], "cadence": cad or "once", "months": months,
                                 "start_day": start_for(clause, global_start or 0),
                                 "label": clause.strip()[:50]})
    if not loans and terms and not any(e["months"] for e in spec["expenses"]):
        raise ComplexParseError("stray term")

    for ln in loans:
        t = ln["tok"]
        if any(len(ln[k]) > 1 for k in ("down", "down_pct", "rate", "term", "payment")) or (ln["down"] and ln["down_pct"]):
            raise ComplexParseError("a loan has two rates, terms, payments or down payments")
        term = ln["term"][0] if ln["term"] else None
        years = None if term is None else (term["value"] / 12 if term["unit"] == "month" else term["value"])
        loan = {"price": t["value"], "down": ln["down"][0]["value"] if ln["down"] else None,
                "down_pct": ln["down_pct"][0]["value"] if ln["down_pct"] else None,
                "rate_pct": ln["rate"][0]["value"] if ln["rate"] else None, "years": years,
                "payment": ln["payment"][0]["value"] if ln["payment"] else None,
                "start_day": start_for(ln["clause"], global_start or 0), "label": ln["clause"].strip()[:50]}
        plain = all(loan[k] is None for k in ("down", "down_pct", "rate_pct", "years", "payment"))
        if plain:  # a cash purchase of a house/car/etc.
            spec["expenses"].append({"amount": t["value"], "cadence": ln["cad"] or "once", "months": None,
                                     "start_day": loan["start_day"], "label": loan["label"]})
        elif years is None or (loan["rate_pct"] is None) == (loan["payment"] is None):
            raise ComplexParseError("a loan needs a term and either a rate or a monthly payment")
        else:
            spec["loans"].append(loan)

    check_coverage(text, spec)
    return spec


def spec_numbers(spec: dict) -> Counter:
    """Numbers the spec accounts for, in the same units tokenize() reads from text."""
    c: Counter = Counter()
    for i in spec.get("income", []):
        c[("money", float(i["amount"]))] += 1
    for e in spec.get("expenses", []):
        c[("money", float(e["amount"]))] += 1
        if e.get("months"):
            c[("term", float(e["months"]))] += 1
    for loan in spec.get("loans", []):
        c[("money", float(loan["price"]))] += 1
        if loan.get("down"):
            c[("money", float(loan["down"]))] += 1
        if loan.get("payment"):
            c[("money", float(loan["payment"]))] += 1
        if loan.get("down_pct") is not None:
            c[("pct", float(loan["down_pct"]))] += 1
        if loan.get("rate_pct") is not None:
            c[("pct", float(loan["rate_pct"]))] += 1
        if loan.get("years") is not None:
            c[("term", round(float(loan["years"]) * 12, 4))] += 1
    return c


def text_numbers(text: str) -> Counter:
    c: Counter = Counter()
    for t in tokenize(text):
        if t["kind"] == "money":
            c[("money", t["value"])] += 1
        elif t["kind"] == "pct":
            c[("pct", t["value"])] += 1
        elif t["kind"] == "term":
            c[("term", round(t["value"] * (12 if t["unit"] == "year" else 1), 4))] += 1
    return c


def check_coverage(text: str, spec: dict) -> None:
    want, got = text_numbers(text), spec_numbers(spec)
    # an expense with `months` shares its term token with nothing else; compare as multisets
    if want != got:
        raise ComplexParseError(f"unaccounted numbers: text={dict(want)} spec={dict(got)}")


# --------------------------------------------------------------------------- #
# spec -> Decision (all math here, deterministic)
# --------------------------------------------------------------------------- #

_PERIOD_DAYS = {"weekly": 7, "biweekly": 14, "monthly": DAYS_PER_MONTH, "annual": 365}


def _clamp_start(v) -> int:
    try:
        return max(0, min(MAX_START_DAY, int(v)))
    except (TypeError, ValueError):
        return 0


def build_decision(spec: dict, text: str, confidence: float = 0.85) -> Decision:
    items: list[DecisionDelta] = []
    terms: dict = {"assumptions": []}
    replace_income = []

    for inc in spec.get("income", []):
        amount, period = float(inc["amount"]), inc["period"]
        if amount <= 0 or period not in ("annual", "monthly", "weekly", "biweekly"):
            raise ValueError("bad income")
        net_factor = 1.0 if inc.get("net") else NET_FACTOR
        # An annual salary is paid monthly; everything else keeps its own cadence.
        if period in ("annual", "monthly"):  # a "month" of pay is 1/12 of a year, so $500/month shows as $500
            per_pay = (amount / 12 if period == "annual" else amount) * net_factor
            cadence = DAYS_PER_YEAR_MONTHLY
        else:
            per_pay, cadence = amount * net_factor, float(_PERIOD_DAYS[period])
        item = DecisionDelta(kind="recurring", amount=round(per_pay, 2), start_day=_clamp_start(inc.get("start_day")),
                             cadence_days=cadence, label="New income" if inc.get("replaces") else "Extra income",
                             raw_text=text, confidence=confidence, direction="inflow")
        if inc.get("replaces"):
            replace_income.append({"index": len(items), "annual": round(per_pay * 365 / cadence, 2)})
        items.append(item)
        if net_factor != 1.0 and "income_tax_assumed" not in terms["assumptions"]:
            terms["assumptions"].append("income_tax_assumed")
            terms["net_factor"] = net_factor

    for e in spec.get("expenses", []):
        amount, cad = float(e["amount"]), e.get("cadence") or "once"
        if amount <= 0:
            raise ValueError("bad expense")
        start = _clamp_start(e.get("start_day"))
        if cad == "once":
            items.append(DecisionDelta(kind="one_time", amount=amount, start_day=start, label=e.get("label", ""),
                                       raw_text=text, confidence=confidence))
        else:
            months = e.get("months")
            end = start + int(months) * DAYS_PER_MONTH if months else None
            items.append(DecisionDelta(kind="recurring", amount=amount, start_day=start,
                                       cadence_days=_PERIOD_DAYS[cad], end_day=end, label=e.get("label", ""),
                                       raw_text=text, confidence=confidence))

    loan_terms = []
    for loan in spec.get("loans", []):
        price = float(loan["price"])
        down = float(loan["down"]) if loan.get("down") else (
            price * float(loan["down_pct"]) / 100 if loan.get("down_pct") is not None else 0.0)
        if price <= 0 or down < 0 or down >= price:
            raise ValueError("bad loan")
        stated = float(loan["payment"]) if loan.get("payment") else None
        rate = None if stated else float(loan["rate_pct"])
        # A home loan's money goes to the seller; any other loan puts cash in the user's account.
        is_home = is_home_loan({"label": loan.get("label", ""), "years": loan["years"]})
        sub = loan_decision(price - down, None if rate is None else rate / 100, float(loan["years"]),
                            payment=stated, down_payment=round(down, 2), start_day=_clamp_start(loan.get("start_day")),
                            label=loan.get("label") or "Loan", raw_text=text, confidence=confidence,
                            proceeds_to_user=not is_home)
        offset = len(items)
        items.extend(sub.items)
        loan_terms.append({**sub.terms, "price": price, "rate_pct": rate,
                           "item_indexes": list(range(offset, len(items))), "label": loan.get("label") or "Loan", "start_day": _clamp_start(loan.get("start_day"))})
    if loan_terms:
        terms["loans"] = loan_terms
    if replace_income:
        terms["replace_income"] = replace_income
    if not items:
        raise ValueError("nothing to decide")
    if len(items) > 8:
        raise ValueError("too many items")
    return Decision(items=tuple(items), label=text[:50], raw_text=text, confidence=confidence, terms=terms)


# --------------------------------------------------------------------------- #
# LLM fallback: extracts raw numbers only; same coverage check applies.
# --------------------------------------------------------------------------- #

_LLM_PROMPT = """Extract the finance question below into JSON. Use ONLY numbers that appear in the message, exactly
as written (convert 90k -> 90000, "5 years" -> years: 5). Never compute payments or totals.

{{
  "income": [{{"amount": number, "period": "annual|monthly|weekly|biweekly", "replaces": true if it replaces the
               current paycheck (new job / salary), false if extra (raise, bonus, side income), "net": true only if
               the text says take-home/after tax, "start_day": integer days from today}}],
  "expenses": [{{"amount": number, "cadence": "once|weekly|biweekly|monthly|annual", "months": integer or null,
                 "start_day": integer days from today, "label": "short"}}],
  "loans": [{{"price": number, "down": number or null, "down_pct": number or null,
              "rate_pct": number or null, "payment": monthly payment if the text states one instead of a rate, else null,
              "years": number, "start_day": integer, "label": "short"}}]
}}
Today is {today}. Every dollar amount, percentage and loan length in the message must appear in exactly one field.
If the message is not a finance question return {{"income": [], "expenses": [], "loans": []}}.

Message: {text}"""


def llm_spec(text: str, today: date) -> dict:
    if not os.getenv("GEMINI_API_KEY"):
        raise ComplexParseError("no LLM available")
    from llm.gemini import generate_text
    raw = json.loads(generate_text(_LLM_PROMPT.format(today=today.isoformat(), text=text),
                                   max_output_tokens=600, json_mode=True))
    spec = {k: [x for x in raw.get(k, []) if isinstance(x, dict)] for k in ("income", "expenses", "loans")}
    check_coverage(text, spec)  # hallucinated or dropped numbers are rejected here
    return spec


def parse_complex(text: str, today: date, *, use_llm: bool = True) -> Decision:
    """Regex grammar, then LLM fallback. Raises ComplexParseError if neither can account for every number."""
    errors: list[str] = []
    try:
        return build_decision(regex_spec(text, today), text, 0.85)
    except (ComplexParseError, ValueError, KeyError) as exc:
        errors.append(str(exc))
    if use_llm:
        try:
            return build_decision(llm_spec(text, today), text, 0.7)
        except Exception as exc:  # network, JSON, coverage, validation
            errors.append(str(exc))
    raise ComplexParseError(HINT)


def needs_complex(text: str) -> bool:
    """Route to the complex parser unless this is the plain single-expense shape."""
    toks = tokenize(text)
    low = text.lower()
    flagged = (_has(_words(low), INCOME_CUES + ("interest", "apr", "down", "mortgage", "loan", "financ", "borrow"))
               or any(t["kind"] in ("pct", "term", "timing") for t in toks))
    money = [t for t in toks if t["kind"] == "money"]
    others = [t for t in toks if t["kind"] not in ("money", "date")]
    return flagged or len(money) != 1 or bool(others)
