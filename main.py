#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OKX Testnet Lab - Observability rig for paper trading infrastructure.
Always generates artifacts, never fails silently, logs in real time.
"""
import os
import sys
import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

# ---------------------------------------------------------------------------
# 0. ULTRA-EARLY SIGN OF LIFE
# ---------------------------------------------------------------------------
print("▶ SCRIPT STARTED", flush=True)

# ---------------------------------------------------------------------------
# 1. CONFIG LOADING
# ---------------------------------------------------------------------------
CONFIG_PATH = Path("config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = json.load(f)
    print(f"✅ Config loaded: {CONFIG['symbol']} | loops={CONFIG['max_iterations']}", flush=True)
except Exception as e:
    print(f"❌ FATAL: Cannot load config: {e}", flush=True)
    sys.exit(1)

ARTIFACTS_DIR = Path(CONFIG.get("artifacts_dir", "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 2. GLOBAL DATA CONTAINERS (filled during run)
# ---------------------------------------------------------------------------
latency_records = []
market_records = []
fill_records = []
error_records = []

def utc_now():
    """ISO 8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

# ---------------------------------------------------------------------------
# 3. OKX TESTNET EXCHANGE INITIALIZATION
# ---------------------------------------------------------------------------
print("▶ Initializing OKX Testnet client...", flush=True)

# Verificación temprana de variables de entorno
required_env = ["OKX_API_KEY", "OKX_SECRET", "OKX_PASSPHRASE"]
missing_env = [v for v in required_env if not os.getenv(v)]
if missing_env:
    err_msg = f"❌ Missing environment variables: {', '.join(missing_env)}"
    print(err_msg, flush=True)
    error_records.append({"timestamp": utc_now(), "error": err_msg})
    # Continuamos para generar artifacts con el fallo capturado
else:
    print("✅ Credentials present in environment", flush=True)

try:
    exchange = ccxt.okx({
        "apiKey": os.getenv("OKX_API_KEY"),
        "secret": os.getenv("OKX_SECRET"),
        "password": os.getenv("OKX_PASSPHRASE"),
        "enableRateLimit": True,
        "timeout": 15000,                     # 15s timeout para evitar cuelgues
        "options": {
            "defaultType": "swap"
        }
    })
    exchange.set_sandbox_mode(True)           # Testnet obligatorio
    print("✅ Exchange object created, sandbox mode ON", flush=True)
except Exception as e:
    err_msg = f"❌ Exchange init failed: {e}"
    print(err_msg, flush=True)
    error_records.append({"timestamp": utc_now(), "error": err_msg})
    # No hacemos exit, continuamos para escribir artifacts

symbol = CONFIG["symbol"]
order_size = CONFIG["order_size_usdt"]
slippage_bps = CONFIG["slippage_bps"]
latency_warn_ms = CONFIG["latency_warning_ms"]

# ---------------------------------------------------------------------------
# 4. MAIN LOOP
# ---------------------------------------------------------------------------
print(f"▶ ENTERING LOOP ({CONFIG['max_iterations']} iterations, sleep {CONFIG['loop_seconds']}s)", flush=True)

valid_exchange = "exchange" in locals()  # True si se creó sin excepción

for i in range(1, CONFIG["max_iterations"] + 1):
    loop_start_time = time.monotonic()
    timestamp = utc_now()
    
    print(f"\n━━━━━━ LOOP {i}/{CONFIG['max_iterations']} ━━━━━━", flush=True)
    
    # --- 4.1 Fetch market data (safe) ---
    bid = ask = last = None
    latency_ms = None
    
    if valid_exchange:
        try:
            t0 = time.monotonic()
            ticker = exchange.fetch_ticker(symbol)
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")
            
            print(f"   🔹 REST latency: {latency_ms} ms", flush=True)
            
            if latency_ms > latency_warn_ms:
                print(f"   ⚠️ WARNING: High latency ({latency_ms} ms > {latency_warn_ms})", flush=True)
                
            # Store market data
            if None not in (bid, ask, last):
                spread_pct = ((ask - bid) / last) * 100 if last != 0 else 0.0
                market_records.append({
                    "timestamp": timestamp,
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "spread_pct": round(spread_pct, 6)
                })
                print(f"   📊 BID:{bid:.2f}  ASK:{ask:.2f}  LAST:{last:.2f}  SPREAD:{spread_pct:.4f}%", flush=True)
            else:
                print("   ⚠️ Incomplete ticker data", flush=True)
                
        except Exception as e:
            err_msg = f"Fetch ticker error: {e}"
            print(f"   ❌ {err_msg}", flush=True)
            error_records.append({"timestamp": timestamp, "error": err_msg})
    else:
        print("   ⛔ Exchange unavailable, skipping market fetch", flush=True)
    
    # Store latency record even if fetch failed (we can still record 0 or None)
    latency_records.append({
        "timestamp": timestamp,
        "latency_ms": latency_ms if latency_ms is not None else 0.0,
        "loop": i
    })
    
    # --- 4.2 Simulated order execution ---
    if None not in (bid, ask):
        side = random.choice(["buy", "sell"])
        if side == "buy":
            expected_price = ask
            fill_price = ask * (1 + random.uniform(0, slippage_bps / 10000))   # slippage against us
        else:  # sell
            expected_price = bid
            fill_price = bid * (1 - random.uniform(0, slippage_bps / 10000))
        
        fill_latency = random.uniform(45, 250)   # simulated internal processing ms
        fill_slippage_pct = ((fill_price - expected_price) / expected_price) * 100
        
        fill_records.append({
            "timestamp": timestamp,
            "loop": i,
            "side": side,
            "expected_price": expected_price,
            "fill_price": round(fill_price, 2),
            "slippage_pct": round(fill_slippage_pct, 4),
            "fill_latency_ms": round(fill_latency, 2)
        })
        
        print(f"   🧪 SIM FILL: {side.upper()} @ {fill_price:.2f} (exp {expected_price:.2f}) | "
              f"slip {fill_slippage_pct:.4f}% | fill lat {fill_latency:.1f}ms", flush=True)
    else:
        print("   ⏭️ Skipping fill sim (no bid/ask)", flush=True)
    
    # --- 4.3 Loop timing control ---
    loop_duration = time.monotonic() - loop_start_time
    sleep_time = max(0, CONFIG["loop_seconds"] - loop_duration)
    print(f"   ⏱️ Loop wall time: {loop_duration*1000:.0f} ms, sleeping {sleep_time:.1f}s", flush=True)
    time.sleep(sleep_time)

# ---------------------------------------------------------------------------
# 5. ARTIFACT GENERATION (MANDATORY, always executed)
# ---------------------------------------------------------------------------
print("\n▶ Writing artifacts...", flush=True)

# 5.1 latency.csv
pd.DataFrame(latency_records).to_csv(ARTIFACTS_DIR / "latency.csv", index=False)

# 5.2 market.csv
pd.DataFrame(market_records).to_csv(ARTIFACTS_DIR / "market.csv", index=False)

# 5.3 fills.csv
pd.DataFrame(fill_records).to_csv(ARTIFACTS_DIR / "fills.csv", index=False)

# 5.4 summary.json
summary = {
    "run_timestamp": utc_now(),
    "status": "completed" if not error_records else "completed_with_errors",
    "total_loops": CONFIG["max_iterations"],
    "market_data_points": len(market_records),
    "simulated_fills": len(fill_records),
    "error_count": len(error_records)
}
with open(ARTIFACTS_DIR / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# 5.5 Optional: errors log as CSV for debugging
if error_records:
    pd.DataFrame(error_records).to_csv(ARTIFACTS_DIR / "errors.csv", index=False)

print("=" * 55)
print("✅ LAB COMPLETE - Artifacts persistidos")
print(f"   📁 {ARTIFACTS_DIR.resolve()}")
print("=" * 55, flush=True)
