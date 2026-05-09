import os
import json
import time
import random
from pathlib import Path
from datetime import datetime

import ccxt
import pandas as pd

ARTIFACTS = Path("artifacts")
ARTIFACTS.mkdir(exist_ok=True)

with open("config.json", "r") as f:
    CONFIG = json.load(f)


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "password": os.getenv("OKX_PASSPHRASE"),
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})

exchange.set_sandbox_mode(True)

symbol = CONFIG["symbol"]

latency_rows = []
fill_rows = []
market_rows = []


print("=" * 60)
print("OKX TESTNET LAB")
print("=" * 60)
print(f"START UTC: {now()}")
print(f"SYMBOL: {symbol}")
print()


for i in range(CONFIG["max_iterations"]):
    print(f"LOOP {i + 1}/{CONFIG['max_iterations']}")

    # -----------------------------
    # REST LATENCY
    # -----------------------------
    t0 = time.time()

    ticker = exchange.fetch_ticker(symbol)

    latency_ms = round((time.time() - t0) * 1000, 2)

    bid = ticker["bid"]
    ask = ticker["ask"]
    last = ticker["last"]

    spread_pct = round(((ask - bid) / last) * 100, 5)

    latency_rows.append({
        "timestamp": now(),
        "latency_ms": latency_ms
    })

    market_rows.append({
        "timestamp": now(),
        "bid": bid,
        "ask": ask,
        "last": last,
        "spread_pct": spread_pct
    })

    # -----------------------------
    # SIMULATED ORDER
    # -----------------------------
    simulated_side = random.choice(["buy", "sell"])

    simulated_slippage = random.uniform(
        0,
        CONFIG["slippage_bps"] / 10000
    )

    if simulated_side == "buy":
        simulated_fill = ask * (1 + simulated_slippage)
    else:
        simulated_fill = bid * (1 - simulated_slippage)

    simulated_fill_latency = round(random.uniform(50, 300), 2)

    fill_rows.append({
        "timestamp": now(),
        "side": simulated_side,
        "expected_price": ask if simulated_side == "buy" else bid,
        "fill_price": simulated_fill,
        "slippage_pct": simulated_slippage * 100,
        "fill_latency_ms": simulated_fill_latency
    })

    # -----------------------------
    # ASCII TELEMETRY
    # -----------------------------
    print("-" * 60)
    print(f"UTC                : {now()}")
    print(f"REST LATENCY       : {latency_ms} ms")
    print(f"BID                : {bid}")
    print(f"ASK                : {ask}")
    print(f"LAST               : {last}")
    print(f"SPREAD             : {spread_pct}%")
    print(f"SIM SIDE           : {simulated_side.upper()}")
    print(f"SIM FILL           : {round(simulated_fill, 2)}")
    print(f"SIM FILL LATENCY   : {simulated_fill_latency} ms")

    if latency_ms > CONFIG["latency_warning_ms"]:
        print("WARNING             : HIGH LATENCY")

    print("-" * 60)
    print()

    time.sleep(CONFIG["loop_seconds"])


# -------------------------------------------------
# SAVE CSV ARTIFACTS
# -------------------------------------------------

pd.DataFrame(latency_rows).to_csv(
    ARTIFACTS / "latency.csv",
    index=False
)

pd.DataFrame(fill_rows).to_csv(
    ARTIFACTS / "fills.csv",
    index=False
)

pd.DataFrame(market_rows).to_csv(
    ARTIFACTS / "market.csv",
    index=False
)


# -------------------------------------------------
# SUMMARY
# -------------------------------------------------

avg_latency = round(
    pd.DataFrame(latency_rows)["latency_ms"].mean(),
    2
)

avg_fill_latency = round(
    pd.DataFrame(fill_rows)["fill_latency_ms"].mean(),
    2
)

summary = {
    "timestamp": now(),
    "symbol": symbol,
    "iterations": CONFIG["max_iterations"],
    "avg_rest_latency_ms": avg_latency,
    "avg_fill_latency_ms": avg_fill_latency,
    "artifact_status": "generated",
    "workflow_status": "success"
}

with open(ARTIFACTS / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)


print()
print("=" * 60)
print("LAB COMPLETE")
print("=" * 60)
print(f"AVG REST LATENCY : {avg_latency} ms")
print(f"AVG FILL LATENCY : {avg_fill_latency} ms")
print("ARTIFACTS        : GENERATED")
print("WORKFLOW STATUS  : SUCCESS")
print("=" * 60)
