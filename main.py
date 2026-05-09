#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OKX Testnet Lab - No-passphrase observability rig.
Corre sin credenciales, genera artifacts siempre, nunca se cuelga.
"""
import os
import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

# ------------------------------------------------------------------
# 0. SEÑAL DE VIDA INMEDIATA
# ------------------------------------------------------------------
print("▶ SCRIPT STARTED", flush=True)

# ------------------------------------------------------------------
# 1. CARGA DE CONFIGURACIÓN
# ------------------------------------------------------------------
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
    print(f"✅ Config: {CONFIG['symbol']} | loops={CONFIG['max_iterations']}", flush=True)
except Exception as e:
    print(f"❌ FATAL: {e}", flush=True)
    sys.exit(1)

ARTIFACTS_DIR = Path(CONFIG.get("artifacts_dir", "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 2. CONTENEDORES DE DATOS
# ------------------------------------------------------------------
latency_records = []
market_records = []
fill_records = []
error_records = []

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

# ------------------------------------------------------------------
# 3. VERIFICACIÓN DE ENTORNO (sin forzar passphrase)
# ------------------------------------------------------------------
print("▶ Verificando variables de entorno...", flush=True)
env_status = {}
for var in ["OKX_API_KEY", "OKX_SECRET", "OKX_PASSPHRASE"]:
    present = bool(os.getenv(var))
    env_status[var] = present
    if not present:
        print(f"   ⚠️ {var} no definida (se intentará sin ella)", flush=True)
    else:
        print(f"   ✅ {var} presente", flush=True)

# ------------------------------------------------------------------
# 4. CLIENTE OKX (máxima tolerancia)
# ------------------------------------------------------------------
exchange = None
if env_status["OKX_API_KEY"] and env_status["OKX_SECRET"]:
    try:
        exchange = ccxt.okx({
            "apiKey": os.getenv("OKX_API_KEY"),
            "secret": os.getenv("OKX_SECRET"),
            "password": os.getenv("OKX_PASSPHRASE", ""),   # passphrase vacío si falta
            "enableRateLimit": True,
            "timeout": 15000,
            "options": {"defaultType": "swap"}
        })
        exchange.set_sandbox_mode(True)
        exchange.load_markets()  # verificación real de conectividad
        print("✅ OKX Testnet conectado correctamente", flush=True)
    except Exception as e:
        print(f"❌ Error al conectar con OKX: {e}", flush=True)
        exchange = None
else:
    print("⛔ Sin credenciales completas, trabajando en modo simulación total", flush=True)

# ------------------------------------------------------------------
# 5. LOOP PRINCIPAL
# ------------------------------------------------------------------
print(f"\n▶ ENTERING LOOP ({CONFIG['max_iterations']} iteraciones)", flush=True)

# Precio simulado de referencia para caídas
sim_last = 60000.0

for i in range(1, CONFIG["max_iterations"] + 1):
    ts = utc_now()
    print(f"\n━━━ LOOP {i}/{CONFIG['max_iterations']} ━━━", flush=True)

    # --------------------------------------------------------------
    # 5.1 Obtención de mercado (real si exchange funciona)
    # --------------------------------------------------------------
    bid = ask = last = None
    latency_ms = 0.0

    if exchange is not None:
        try:
            t0 = time.monotonic()
            ticker = exchange.fetch_ticker(CONFIG["symbol"])
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")
            print(f"   🔹 REST latency: {latency_ms} ms", flush=True)
            if latency_ms > CONFIG["latency_warning_ms"]:
                print(f"   ⚠️ Latencia alta (> {CONFIG['latency_warning_ms']} ms)", flush=True)
        except Exception as e:
            err = f"Fetch falló: {e}"
            print(f"   ❌ {err}", flush=True)
            error_records.append({"timestamp": ts, "loop": i, "error": err})
    else:
        print("   ℹ️ Sin conexión real, usando simulación de mercado", flush=True)

    # Si no hay datos reales, generamos simulados con variación
    if None in (bid, ask, last):
        sim_last += random.uniform(-100, 100)
        sim_last = max(1000, sim_last)  # evitar precios negativos
        spread_frac = random.uniform(0.0001, 0.0005)
        bid = round(sim_last * (1 - spread_frac / 2), 2)
        ask = round(sim_last * (1 + spread_frac / 2), 2)
        last = sim_last
        latency_ms = 0.0  # latencia simulada
        print(f"   🧪 SIMULADO bid={bid:.2f} ask={ask:.2f} last={last:.2f}", flush=True)

    # Guardar registro de mercado
    spread_pct = ((ask - bid) / last) * 100 if last != 0 else 0.0
    market_records.append({
        "timestamp": ts,
        "loop": i,
        "bid": bid,
        "ask": ask,
        "last": last,
        "spread_pct": round(spread_pct, 6),
        "latency_ms": latency_ms
    })
    latency_records.append({
        "timestamp": ts,
        "loop": i,
        "latency_ms": latency_ms
    })

    # --------------------------------------------------------------
    # 5.2 Orden simulada
    # --------------------------------------------------------------
    side = random.choice(["buy", "sell"])
    if side == "buy":
        expected = ask
        fill_price = ask * (1 + random.uniform(0, CONFIG["slippage_bps"] / 10000))
    else:
        expected = bid
        fill_price = bid * (1 - random.uniform(0, CONFIG["slippage_bps"] / 10000))

    fill_latency = random.uniform(45, 250)
    slip_pct = ((fill_price - expected) / expected) * 100

    fill_records.append({
        "timestamp": ts,
        "loop": i,
        "side": side,
        "expected_price": expected,
        "fill_price": round(fill_price, 2),
        "slippage_pct": round(slip_pct, 4),
        "fill_latency_ms": round(fill_latency, 2)
    })

    print(f"   🧪 FILL SIM: {side.upper()} @ {fill_price:.2f} (exp {expected:.2f}) "
          f"| slip {slip_pct:.4f}% | fill lat {fill_latency:.1f}ms", flush=True)

    # Control de tiempo del loop
    time.sleep(CONFIG["loop_seconds"])

# ------------------------------------------------------------------
# 6. ESCRITURA OBLIGATORIA DE ARTIFACTS
# ------------------------------------------------------------------
print("\n▶ Generando artifacts...", flush=True)

pd.DataFrame(latency_records).to_csv(ARTIFACTS_DIR / "latency.csv", index=False)
pd.DataFrame(market_records).to_csv(ARTIFACTS_DIR / "market.csv", index=False)
pd.DataFrame(fill_records).to_csv(ARTIFACTS_DIR / "fills.csv", index=False)
if error_records:
    pd.DataFrame(error_records).to_csv(ARTIFACTS_DIR / "errors.csv", index=False)

summary = {
    "run_timestamp": utc_now(),
    "status": "completed" if not error_records else "completed_with_errors",
    "total_loops": CONFIG["max_iterations"],
    "market_data_points": len(market_records),
    "simulated_fills": len(fill_records),
    "error_count": len(error_records),
    "exchange_connected": exchange is not None
}
with open(ARTIFACTS_DIR / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("=" * 55)
print("✅ LAB COMPLETE - Artifacts persistidos")
print("=" * 55, flush=True)
