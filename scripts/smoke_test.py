"""End-to-end smoke test of a running deployment (container, docker compose or Render).

    python scripts/smoke_test.py http://localhost:10000                 # through the edge proxy
    python scripts/smoke_test.py http://127.0.0.1:8001 --realtime http://127.0.0.1:8002

It checks the three microservices from the outside, the way the frontend uses them:
REST (gateway) → gRPC (engine) and WebSocket (realtime) → gRPC streams (engine). Exits 1 on failure.
"""
import argparse
import asyncio
import json
import sys
import time

import httpx
import websockets


def check(condition: bool, message: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        sys.exit(1)


def wait_for(url: str, limit_s: float) -> None:
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    check(False, f"{url}/health answered within {limit_s:.0f} s")


def rest(api: str, model_wait_s: float) -> tuple[int, int]:
    print("REST · gateway")
    deadline = time.monotonic() + model_wait_s
    while True:  # right after a deploy the engine may still be starting and the hub reconnecting
        services = httpx.get(f"{api}/health/services", timeout=10).json()
        ready = services["engine"]["available"] and services["realtime"].get("alerts_upstream") == "connected"
        if ready or time.monotonic() > deadline:
            break
        time.sleep(2)
    engine = services["engine"]
    check(engine["available"], f"engine reachable over gRPC (latency {engine['latency_ms']} ms)")
    check(services["realtime"].get("alerts_upstream") == "connected",
          f"realtime hub reachable and subscribed to the engine ({services['realtime'].get('connections')} sockets)")
    summary = httpx.get(f"{api}/api/v1/dashboard/summary", timeout=30).json()
    check(len(summary["risks"]) >= 1,
          f"dashboard summary for {summary['municipality']}, week {summary['reference_week']}")
    municipality, disease = summary["municipality_id"], summary["risks"][0]["disease_id"]

    deadline = time.monotonic() + model_wait_s
    while True:
        r = httpx.get(f"{api}/api/v1/engine/forecast", params={"municipality_id": municipality,
                                                               "disease_id": disease}, timeout=30)
        if r.status_code == 200 or time.monotonic() > deadline:
            break
        time.sleep(5)  # the engine may still be training on its first start
    check(r.status_code == 200, f"engine forecast (unary RPC) in {r.json().get('duration_ms')} ms")
    return municipality, disease


async def realtime(ws_url: str, municipality: int, disease: int) -> None:
    print("WebSocket · realtime")
    async with websockets.connect(f"{ws_url}/ws", open_timeout=15) as ws:
        async def next_of(kind: str) -> dict:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if msg["type"] == kind:
                    return msg

        welcome = await next_of("welcome")
        check(welcome["protocol"] == 1, f"welcome as {welcome['client_id']}")
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        snapshot = await next_of("alerts.snapshot")
        check(snapshot["upstream"] == "connected", f"{len(snapshot['alerts'])} active alerts from the engine stream")
        await ws.send(json.dumps({"type": "simulate", "scenario": {"id": "smoke", "municipality_id": municipality,
                                                                    "disease_id": disease, "rain_change_pct": 50}}))
        result = (await next_of("simulation.result"))["result"]
        check(result["error"] is None, f"bidirectional simulation in {result['duration_ms']} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("api", help="base URL of the gateway (or of the edge proxy)")
    parser.add_argument("--realtime", help="base URL of the realtime hub (default: same as api)")
    parser.add_argument("--wait", type=float, default=180, help="seconds to wait for the service and the models")
    args = parser.parse_args()
    api = args.api.rstrip("/")
    hub = (args.realtime or api).rstrip("/")
    wait_for(api, args.wait)
    municipality, disease = rest(api, args.wait)
    asyncio.run(realtime(hub.replace("http", "ws", 1), municipality, disease))
    if not args.realtime:  # through the edge: the hub's internal endpoint must not be public
        r = httpx.post(f"{api}/internal/events", json={}, timeout=10)
        check(r.status_code == 404, "internal endpoints are not exposed by the edge proxy")
    print("All checks passed")


if __name__ == "__main__":
    main()
