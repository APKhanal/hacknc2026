"""Explicitly synthetic Nessie-shaped fixtures for offline development, not live ingest."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from data.cache import CacheRepository, COLLECTIONS, write_snapshot

# test1..test5 -> the 5 demo_snapshots() profiles below, in declaration order.
# Keep this in lockstep with the `profiles` tuple in demo_snapshots() if its
# order or names ever change.
TEST_TRIGGER_CUSTOMERS: dict[str, str] = {
    "test1": "demo_steady",
    "test2": "demo_irregular",
    "test3": "demo_heavy",
    "test4": "demo_cushion",
    "test5": "demo_monthly",
}


def merge_fixture_snapshots(cache: CacheRepository, snapshots: list[dict]) -> None:
    """Add synthetic fixtures to a live, in-memory CacheRepository.

    Additive only: never overwrites a customer_id or transaction that's
    already present, so this can never clobber real ingested data even on
    an id collision. Never touches disk.
    """
    fixtures = CacheRepository.from_snapshots(snapshots)
    for cid, snapshot in fixtures.snapshots.items():
        if cid not in cache.snapshots:
            cache.snapshots[cid] = snapshot
    for tid, record in fixtures.transactions.items():
        cache.transactions.setdefault(tid, record)
        cache.transaction_units.setdefault(tid, fixtures.transaction_units[tid])


def demo_snapshots(as_of: date = date(2026, 10, 9)) -> list[dict]:
    profiles = [
        ("steady", "Alex", 2310.40, 1850, 14, 1450, 142, 210),
        ("irregular", "Blair", 1100, 1700, 14, 1250, 175, 260),
        ("heavy", "Casey", 750, 1550, 14, 1800, 240, 300),
        ("cushion", "Drew", 16000, 2600, 14, 900, 85, 175),
        ("monthly", "Ellis", 900, 3200, 30, 1650, 180, 250),
    ]
    snapshots = []
    for profile, name, balance, paycheck, cadence, rent, insurance, spending in profiles:
        cid = f"demo_{profile}"
        aid = f"account_{cid}"
        bundle = {"account": {"_id": aid, "customer_id": cid, "type": "Checking", "balance": balance}}
        bundle.update({collection: [] for collection in COLLECTIONS})
        merchants = [
            {"_id": f"rent_{cid}", "name": "Rent", "category": ["housing"]},
            {"_id": f"insurance_{cid}", "name": "Geico", "category": ["insurance"]},
            {"_id": f"grocer_{cid}", "name": "Grocer", "category": ["food"]},
        ]
        elapsed = 6
        i = 0
        while elapsed < 365:
            day = as_of - timedelta(days=elapsed)
            bundle["deposits"].append({"_id": f"{cid}_income_{i}", "payee_id": aid,
                                       "transaction_date": day.isoformat(), "amount": paycheck + (i % 3 - 1) * 90,
                                       "description": "Payroll", "status": "completed"})
            elapsed += [11, 17, 14, 20][i % 4] if profile == "irregular" else cadence
            i += 1
        for merchant, amount, offset in ((merchants[0], rent, 10), (merchants[1], insurance, 18)):
            for i, elapsed in enumerate(range(offset, 365, 30)):
                bundle["purchases"].append({"_id": f"{cid}_{merchant['_id']}_{i}", "payer_id": aid,
                                            "merchant_id": merchant["_id"], "purchase_date": (as_of - timedelta(days=elapsed)).isoformat(),
                                            "amount": amount, "status": "completed"})
        for i, elapsed in enumerate(range(2, 365, 7)):
            bundle["purchases"].append({"_id": f"{cid}_spend_{i}", "payer_id": aid,
                                        "merchant_id": merchants[2]["_id"],
                                        "purchase_date": (as_of - timedelta(days=elapsed)).isoformat(),
                                        "amount": float(Decimal(spending) * Decimal([".45", "1.4", ".9", "1.25"][i % 4])), "status": "completed"})
        snapshots.append({"schema_version": 1, "source": "generated_fixture",
                          "as_of": as_of.isoformat(), "customer": {"_id": cid, "first_name": name,
                          "last_name": "(synthetic fixture)"}, "accounts": [bundle], "merchants": merchants})
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/demo"))
    args = parser.parse_args()
    for snapshot in demo_snapshots():
        print(write_snapshot(args.cache_dir, snapshot))


if __name__ == "__main__":
    main()
