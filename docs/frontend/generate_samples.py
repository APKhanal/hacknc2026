"""Regenerate offline design samples using the real fitter and simulator.

Run from the repo root: python -m docs.frontend.generate_samples
Requires numpy. Reads existing synthetic cache; performs no network requests.
"""
import json
from pathlib import Path

from core.model import DecisionDelta
from core.run import run
from data.cache import CacheRepository
from data.fit import fit

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).parent / "prototype" / "samples"
PROFILES = {
    "alex": ("39b2bdb2-e13c-4734-8522-1e2d43df6d1f", "Alex", "Steady income"),
    "drew": ("4ba43709-2dbc-483e-8ca4-cf1959052b71", "Drew", "Savings cushion"),
}
QUESTIONS = {
    "flight": DecisionDelta("one_time", 1400, 0, label="One-time expense", raw_text="Can I afford $1,400 today?"),
    "gym": DecisionDelta("recurring", 65, 0, 30, label="Monthly membership", raw_text="Can I afford $65/month starting today?"),
}


def main():
    cache = CacheRepository(ROOT / "data" / "cache" / "seeded")
    DEST.mkdir(parents=True, exist_ok=True)
    for key, (customer_id, name, description) in PROFILES.items():
        model = fit(cache.snapshot(customer_id))
        for scenario, delta in QUESTIONS.items():
            result = run(model, delta)
            record = {
                "profile": {"name": name, "description": description},
                "result": result.to_dict(),
                "inputs": {
                    "model": model.to_dict(), "delta": delta.to_dict(),
                    "evidence": {tid: cache.transaction(tid) for tid in model.evidence_index},
                    "amount_units": {"model": "usd", "delta": "usd", "evidence": {
                        tid: cache.transaction_unit(tid) for tid in model.evidence_index
                    }},
                },
            }
            (DEST / f"{key}-{scenario}.json").write_text(json.dumps(record, separators=(",", ":"), allow_nan=False))
            print(f"{key}-{scenario}: {result.n_paths} paths, breach rate {result.delta_breach_rate}")


if __name__ == "__main__":
    main()
