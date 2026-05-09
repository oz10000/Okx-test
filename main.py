import os
import json
import time
import random
from pathlib import Path
from datetime import datetime

import ccxt
import pandas as pd

# ============================================================
# CONFIG
# ============================================================

with open("config.json", "r") as f:
    CONFIG = json.load(f)

ARTIFACTS = Path(CONFIG["artifacts_dir"])
ARTIFACTS.mkdir(exist_ok=True)

# ============================================================
# HELPERS
# ============================================================

def utc_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def print_header():
    print("=" * 70)
    print("OKX TESTNET GITHUB LAB")
    print("=" * 70)
    print(f"UTC START : {utc_now()}")
    print(f"SYMBOL    : {CONFIG['symbol']}")
    print(f"TESTNET   : {CONFIG['testnet']}")
    print("=" * 70)
    print()


# ============================================================
# OKX CONNECTION
# ============================================================

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})

exchange.set_sandbox_mode(True)

symbol = CONFIG["symbol"]

# ============================================================
# STORAGE
# ============================================================

latency_rows = []
market_rows = []
fill_rows = []
system_rows = []

# ============================================================
# MAIN LOOP
# ============================================================

print_header()

for iteration in range(CONFIG["max_iterations"]):

    print(f"LOOP {iteration + 1}/{CONFIG['max_iterations']}")

    loop_start = time.time()

    # ========================================================
    # FETCH MARKET DATA
    # ========================================================

    rest_t0 = time.time()

    try:
        ticker = exchange.fetch_ticker(symbol)

        rest_latency_ms = round(
            (time.time() - rest_t0) * 1000,
            2
        )

        bid = ticker["bid"]
        ask = ticker["ask"]
        last = ticker["last"]

        spread_pct = round(
            ((ask - bid) / last) * 100,
            6
        )

        market_rows.append({
            "timestamp": utc_now(),
            "bid": bid,
            "ask": ask,
            "last": last,
            "spread_pct": spread_pct
        })

        latency_rows.append({
            "timestamp": utc_now(),
            "rest_latency_ms": rest_latency_ms
        })

    except Exception as e:

        print(f"MARKET ERROR: {e}")

        system_rows.append({
            "timestamp": utc_now(),
            "type": "market_error",
            "message": str(e)
        })

        time.sleep(CONFIG["loop_seconds"])
        continue

    # ========================================================
    # SIMULATED ORDER EXECUTION
    # ========================================================

    side = random.choice(["buy", "sell"])

    simulated_slippage = random.uniform(
        0,
        CONFIG["slippage_bps"] / 10000
    )

    if side == "buy":
        simulated_fill_price = ask * (1 + simulated_slippage)
        expected_price = ask
    else:
        simulated_fill_price = bid * (1 - simulated_slippage)
        expected_price = bid

    simulated_fill_latency_ms = round(
        random.uniform(50, 300),
        2
    )

    fill_rows.append({
        "timestamp": utc_now(),
        "side": side,
        "expected_price": expected_price,
        "fill_price": simulated_fill_price,
        "slippage_pct": simulated_slippage * 100,
        "fill_latency_ms": simulated_fill_latency_ms
    })

    # ========================================================
    # SYSTEM METRICS
    # ========================================================

    loop_runtime_ms = round(
        (time.time() - loop_start) * 1000,
        2
    )

    system_rows.append({
        "timestamp": utc_now(),
        "type": "loop",
        "loop_runtime_ms": loop_runtime_ms
    })

    # ========================================================
    # ASCII TELEMETRY
    # ========================================================

    print("-" * 70)
    print(f"UTC                 : {utc_now()}")
    print(f"REST LATENCY        : {rest_latency_ms} ms")
    print(f"BID                 : {bid}")
    print(f"ASK                 : {ask}")
    print(f"LAST                : {last}")
    print(f"SPREAD              : {spread_pct}%")
    print(f"SIDE                : {side.upper()}")
    print(f"EXPECTED PRICE      : {round(expected_price, 2)}")
    print(f"SIMULATED FILL      : {round(simulated_fill_price, 2)}")
    print(f"SIM SLIPPAGE        : {round(simulated_slippage * 100, 5)}%")
    print(f"FILL LATENCY        : {simulated_fill_latency_ms} ms")
    print(f"LOOP RUNTIME        : {loop_runtime_ms} ms")

    if rest_latency_ms > CONFIG["latency_warning_ms"]:
        print("WARNING             : HIGH LATENCY")

    print("-" * 70)
    print()

    time.sleep(CONFIG["loop_seconds"])

# ============================================================
# SAVE ARTIFACTS
# ============================================================

pd.DataFrame(latency_rows).to_csv(
    ARTIFACTS / "latency.csv",
    index=False
)

pd.DataFrame(market_rows).to_csv(
    ARTIFACTS / "market.csv",
    index=False
)

pd.DataFrame(fill_rows).to_csv(
    ARTIFACTS / "fills.csv",
    index=False
)

pd.DataFrame(system_rows).to_csv(
    ARTIFACTS / "system.csv",
    index=False
)

# ============================================================
# SUMMARY
# ============================================================

avg_rest_latency = round(
    pd.DataFrame(latency_rows)["rest_latency_ms"].mean(),
    2
)

avg_fill_latency = round(
    pd.DataFrame(fill_rows)["fill_latency_ms"].mean(),
    2
)

summary = {
    "timestamp": utc_now(),
    "exchange": "okx",
    "testnet": True,
    "symbol": symbol,
    "iterations": CONFIG["max_iterations"],
    "avg_rest_latency_ms": avg_rest_latency,
    "avg_fill_latency_ms": avg_fill_latency,
    "workflow_status": "success",
    "artifact_status": "generated"
}

with open(ARTIFACTS / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ============================================================
# FINAL OUTPUT
# ============================================================

print()
print("=" * 70)
print("LAB COMPLETE")
print("=" * 70)
print(f"AVG REST LATENCY : {avg_rest_latency} ms")
print(f"AVG FILL LATENCY : {avg_fill_latency} ms")
print("ARTIFACTS        : GENERATED")
print("WORKFLOW STATUS  : SUCCESS")
print("=" * 70)
