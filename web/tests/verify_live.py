"""Read-only live proxy verification; start the cached API and frontend first."""
import os
import httpx
import numpy as np

base = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
run_id = os.environ["VERIFY_RUN_ID"]
with httpx.Client(base_url=base, timeout=30) as client:
    customers = client.get("/api/backend/customers")
    customers.raise_for_status()
    for customer in customers.json():
        response = client.get(f"/api/backend/model/{customer['customer_id']}")
        response.raise_for_status()
        assert response.json()["customer_id"] == customer["customer_id"]
    result = client.get(f"/api/backend/run/{run_id}").json()
    inputs = client.get(f"/api/backend/run/{run_id}/inputs").json()
    assert len(result["paths"]) == result["n_paths"] == 500
    balances = np.array([path["balances"] for path in result["paths"]])
    assert balances.shape == (500, result["horizon_weeks"] + 1)
    assert np.isfinite(balances).all()
    percentiles = np.percentile(balances[:, 1], [10, 50, 90])
    print("Week 1 reference percentiles:", percentiles.tolist())
    for tid, raw in inputs["evidence"].items():
        response = client.get(f"/api/backend/txn/{tid}")
        response.raise_for_status()
        assert response.json() == raw
        assert response.headers["X-Monetary-Unit"] == inputs["amount_units"]["evidence"][tid]
    for route in ("run/missing", "run/missing/inputs", "model/missing", "txn/missing", "unlisted"):
        assert client.get(f"/api/backend/{route}").status_code == 404
    # Invalid requests cannot create a run or invoke a paid rendering call.
    assert client.post("/api/backend/ask", json={"text": "Can I afford a car?", "customer_id": inputs["model"]["customer_id"]}).status_code == 422
    assert client.post("/api/backend/customers", json={}).status_code == 404
    # Card screenshot routes: native to web/, not proxied through /api/backend.
    # Two separate clean cards (graph alone, stats alone), not the interactive panel.
    chart = client.get(f"/api/chart/{run_id}")
    chart.raise_for_status()
    assert chart.headers["content-type"] == "image/png"
    assert chart.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(chart.content) > 1000
    stats = client.get(f"/api/stats/{run_id}")
    stats.raise_for_status()
    assert stats.headers["content-type"] == "image/png"
    assert stats.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(stats.content) > 1000
    assert client.get("/api/chart/nonexistent-run-id").status_code == 404
    assert client.get("/api/stats/nonexistent-run-id").status_code == 404
    print(f"PASS: {len(customers.json())} profiles, 500 paths, {len(inputs['evidence'])} original evidence records, explicit units, 404 and 422 forwarding, {len(chart.content)}-byte chart PNG, {len(stats.content)}-byte stats PNG.")
