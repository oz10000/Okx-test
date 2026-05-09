import os
import json
import time
import random
from pathlib import Path
from datetime import datetime

import ccxt
import pandas as pd

# ============================================================
# STARTUP DEBUG (CRÍTICO EN GITHUB ACTIONS)
# ============================================================

print("SCRIPT STARTED")

# ============================================================
# CONFIG
# ============================================================

with open("config.json", "r") as f:
    CONFIG = json.load(f)

ARTIFACTS = Path(CONFIG["artifacts_dir"])
ARTIFACTS.mkdir(exist_ok=True)

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# OKX EXCHANGE (ROBUSTO)
# ============================================================

print("INIT OKX")

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "enableRateLimit": True,
    "timeout": 15000,   # 🔴 CLAVE PARA EVITAR FREEZE
    "options": {
        "defaultType": "swap"
    }
})

exchange.set_sandbox_mode(True)

symbol = CONFIG["symbol"]

# ============================================================
# DATA STORAGE
# ============================================================

latency_rows = []
market_rows = []
fill_rows = []
error_rows = []

# ============================================================
# MAIN LOOP
# ============================================================

print("ENTER LOOP")

for i in range(CONFIG["max_iterations"]):

    print(f"LOOP {i+1}/{CONFIG['max_iterations']}")

    loop_start = time.time()

    # ========================================================
    # FETCH MARKET (SAFE)
    # ========================================================

    try:
        t0 = time.time()

        ticker = exchange.fetch_ticker(symbol)

        latency_ms = round((time.time() - t0) * 1000, 2)

        bid = ticker["bid"]
        ask = ticker["ask"]
        last = ticker["last"]

        spread = round(((ask - bid) / last) * 100, 6)

        latency_rows.append({
            "time": now(),
            "latency_ms": latency_ms
        })

        market_rows.append({
            "time": now(),
            "bid": bid,
            "ask": ask,
            "last": last,
            "spread_pct": spread
        })

    except Exception as e:

        print("FETCH ERROR:", str(e))

        error_rows.append({
            "time": now(),
            "error": str(e)
        })

        time.sleep(CONFIG["loop_seconds"])
        continue

    # ========================================================
    # SIMULATED ORDER EXECUTION
    # ========================================================

    side = random.choice(["buy", "sell"])

    slip = random.uniform(0, CONFIG["slippage_bps"] / 10000)

    if side == "buy":
        fill = ask * (1 + slip)
        expected = ask
    else:
        fill = bid * (1 - slip)
        expected = bid

    fill_latency = random.uniform(50, 300)

    fill_rows.append({
        "time": now(),
        "side": side,
        "expected": expected,
        "fill": fill,
        "slippage_pct": slip * 100,
        "fill_latency_ms": fill_latency
    })

    # ========================================================
    # TELEMETRY
    # ========================================================

    print(f"LATENCY MS : {latency_ms}")
    print(f"BID        : {bid}")
    print(f"ASK        : {ask}")
    print(f"SPREAD     : {spread}")
    print(f"SIDE       : {side}")
    print(f"FILL       : {round(fill, 2)}")

    if latency_ms > CONFIG["latency_warning_ms"]:
        print("WARNING: HIGH LATENCY")

    loop_time = round((time.time() - loop_start) * 1000, 2)
    print(f"LOOP TIME  : {loop_time} ms")
    print("-" * 50)

    time.sleep(CONFIG["loop_seconds"])

# ============================================================
# ARTIFACTS (SIEMPRE SE GENERAN)
# ============================================================

pd.DataFrame(latency_rows).to_csv(ARTIFACTS / "latency.csv", index=False)
pd.DataFrame(market_rows).to_csv(ARTIFACTS / "market.csv", index=False)
pd.DataFrame(fill_rows).to_csv(ARTIFACTS / "fills.csv", index=False)
pd.DataFrame(error_rows).to_csv(ARTIFACTS / "errors.csv", index=False)

summary = {
    "time": now(),
    "status": "completed",
    "loops": CONFIG["max_iterations"],
    "errors": len(error_rows)
}

import json
with open(ARTIFACTS / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ============================================================
# FINAL OUTPUT
# ============================================================

print("=" * 60)
print("LAB COMPLETE")
print("=" * 60)
print("ARTIFACTS GENERATED")
print("STATUS: SUCCESS")
print("=" * 60)
