#!/usr/bin/env python3
"""Check if transaction IDs resolve via GET /txn/{txn_id}.

This is the one-shot script recommended in Blocker 3.
Run against a list of transaction IDs from a real model to verify evidence resolution.

Usage:
    python llm/scripts/check_evidence.py <txn_id> [<txn_id> ...]

    Or pipe from a file:
    cat evidence_ids.txt | python llm/scripts/check_evidence.py

Example output:
    checking 50 evidence IDs...
    ✓ txn_001
    ✓ txn_002
    ✗ txn_999 (404)

    Results: 48/50 resolved, 2 failed
"""

import sys
import requests
from typing import List, Tuple
from urllib.parse import urljoin


# Base URL for transaction resolver (configure as needed)
BASE_URL = "http://localhost:8000"  # TODO: Set actual endpoint
TXN_ENDPOINT = "/txn/{txn_id}"
TIMEOUT = 2.0  # Short timeout as per spec


def check_transaction_exists(txn_id: str, base_url: str = BASE_URL) -> Tuple[bool, str]:
    """
    Check if a transaction exists via GET /txn/{txn_id}.

    Returns (exists, status_description)
    """
    url = urljoin(base_url, TXN_ENDPOINT.format(txn_id=txn_id))

    try:
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            return True, "200"
        elif response.status_code == 404:
            return False, "404"
        else:
            return False, f"{response.status_code}"

    except requests.Timeout:
        return False, "timeout"
    except requests.ConnectionError:
        return False, "connection error"
    except Exception as e:
        return False, f"error: {e}"


def main():
    """Check evidence IDs from stdin or command-line args."""

    # Collect evidence IDs from args and stdin
    txn_ids = []

    # From command-line arguments
    for arg in sys.argv[1:]:
        txn_ids.append(arg.strip())

    # From stdin (if available)
    if not sys.stdin.isatty():
        for line in sys.stdin:
            txn_id = line.strip()
            if txn_id:
                txn_ids.append(txn_id)

    if not txn_ids:
        print("Usage: python llm/scripts/check_evidence.py <txn_id> [<txn_id> ...]")
        print("       Or: cat evidence_ids.txt | python llm/scripts/check_evidence.py")
        sys.exit(1)

    print(f"checking {len(txn_ids)} evidence IDs...")

    results = []
    failed = []

    for txn_id in txn_ids:
        exists, status = check_transaction_exists(txn_id)

        symbol = "✓" if exists else "✗"
        status_str = f" ({status})" if status != "200" else ""
        print(f"{symbol} {txn_id}{status_str}")

        results.append((txn_id, exists))
        if not exists:
            failed.append((txn_id, status))

    # Summary
    success_count = sum(1 for _, exists in results if exists)
    print()
    print(f"Results: {success_count}/{len(txn_ids)} resolved, {len(failed)} failed")

    if failed:
        print("\nFailed transactions:")
        for txn_id, status in failed:
            print(f"  {txn_id}: {status}")
        print("\n⚠️  Recommend fixing evidence resolution before the hard gate.")
        return 1
    else:
        print("\n✓ All evidence IDs resolved. You're ready to go.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
