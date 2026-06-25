"""
Crypto Trading Simulator - Backend Server
==========================================
Simulates a real trading platform using live prices from CoinGecko.
Provides REST API for trading operations and SSE for real-time data.

API Endpoints:
  GET  /api/prices                   - Current prices (all coins)
  GET  /api/prices/<coin_id>         - Price for specific coin
  GET  /api/prices/history/<coin_id> - Recent price history (last 100 ticks)
  GET  /api/portfolio                - Current portfolio & positions
  GET  /api/pnl                      - Current PnL breakdown
  GET  /api/orders                   - Order history
  POST /api/order/open               - Open a position
  POST /api/order/close              - Close a position
  POST /api/order/close_all          - Close all positions
  GET  /api/stream                   - SSE stream for real-time prices
  GET  /                             - Web dashboard
"""

import threading
import time
import json
import random
import math
from datetime import datetime, timezone
from collections import deque
from flask import Flask, jsonify, request, Response, send_from_directory
import requests

app = Flask(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
COINS = {
    "bitcoin":  {"symbol": "BTC", "id": "bitcoin"},
    "ethereum": {"symbol": "ETH", "id": "ethereum"},
    "binancecoin": {"symbol": "BNB", "id": "binancecoin"},
    "solana":   {"symbol": "SOL", "id": "solana"},
    "ripple":   {"symbol": "XRP", "id": "ripple"},
}

TAKER_FEE = 0.0006   # 0.06% per trade (entry + exit)
MAKER_FEE = 0.0002   # 0.02%
INITIAL_BALANCE = 10_000.0  # USDT

PRICE_HISTORY_SIZE = 200   # keep last 200 ticks per coin
PRICE_FETCH_INTERVAL = 600  # seconds between CoinGecko fetches (10 minutes to avoid rate limit)
TICK_INTERVAL = 1.0        # UI tick every second (interpolate between fetches)

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
state = {
    "balance": INITIAL_BALANCE,
    "positions": {},      # coin_id -> {side, qty, entry_price, open_time, id}
    "orders": [],         # completed orders
    "prices": {},         # coin_id -> float
    "price_history": {c: deque(maxlen=PRICE_HISTORY_SIZE) for c in COINS},
    "last_fetch": 0,
    "fetch_ok": False,
    "next_order_id": 1,
    "algo_running": False,
}
state_lock = threading.Lock()

# ─────────────────────────────────────────────
# PRICE ENGINE
# ─────────────────────────────────────────────
def fetch_coingecko():
    """Fetch live prices from CoinGecko (free tier)."""
    coin_ids = ",".join(COINS.keys())
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={coin_ids}&vs_currencies=usd"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        prices = {}
        for coin_id in COINS:
            if coin_id in data and "usd" in data[coin_id]:
                prices[coin_id] = float(data[coin_id]["usd"])
        return prices
    except Exception as e:
        print(f"[CoinGecko] Fetch error: {e}")
        return {}


def price_loop():
    """Background thread: fetches real prices every 10 min, simulates micro-movement between fetches."""
    # Seed with simulated prices if CoinGecko unreachable
    seed_prices = {
        "bitcoin": 67_500.0,
        "ethereum": 3_520.0,
        "binancecoin": 580.0,
        "solana": 168.0,
        "ripple": 0.52,
    }

    last_real = {}
    last_fetch_time = 0

    while True:
        now = time.time()
        
        # Only fetch from CoinGecko every 10 minutes to avoid rate limiting
        if now - last_fetch_time >= PRICE_FETCH_INTERVAL:
            prices = fetch_coingecko()
            
            with state_lock:
                if prices:
                    last_real = prices.copy()
                    state["fetch_ok"] = True
                    print(f"[CoinGecko] Prices updated: {list(prices.keys())}")
                else:
                    state["fetch_ok"] = False
                    if last_real:
                        print(f"[CoinGecko] Fetch failed, using cached prices")
                    prices = last_real.copy() if last_real else seed_prices.copy()
                    
            last_fetch_time = now
        else:
            # Between fetches, simulate realistic micro-movement around last known prices
            with state_lock:
                prices = {}
                base = last_real if last_real else seed_prices
                for c, p in base.items():
                    drift = random.gauss(0, 0.0002)  # Realistic micro-volatility
                    prices[c] = round(p * (1 + drift), 6)

        with state_lock:
            ts = datetime.now(timezone.utc).isoformat()
            for coin_id, price in prices.items():
                state["prices"][coin_id] = price
                state["price_history"][coin_id].append({
                    "t": ts,
                    "p": price,
                    "ts": now,
                })
            state["last_fetch"] = now

        time.sleep(TICK_INTERVAL)  # Update UI every second, but fetch CoinGecko every 10 min


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def calc_pnl():
    """Calculate unrealised PnL for all open positions."""
    result = []
    total_unrealised = 0.0
    with state_lock:
        for coin_id, pos in state["positions"].items():
            price = state["prices"].get(coin_id, pos["entry_price"])
            side  = pos["side"]   # "long" | "short"
            qty   = pos["qty"]
            ep    = pos["entry_price"]

            if side == "long":
                raw_pnl = (price - ep) * qty
            else:
                raw_pnl = (ep - price) * qty

            # Tax = fee on current mark value (close leg)
            close_fee = price * qty * TAKER_FEE
            net_pnl   = raw_pnl - close_fee

            pct = (net_pnl / (ep * qty)) * 100 if ep * qty else 0

            entry = {
                "coin_id": coin_id,
                "symbol": COINS[coin_id]["symbol"],
                "side": side,
                "qty": qty,
                "entry_price": ep,
                "current_price": price,
                "raw_pnl": round(raw_pnl, 4),
                "close_fee": round(close_fee, 4),
                "net_pnl": round(net_pnl, 4),
                "pct": round(pct, 4),
                "open_time": pos["open_time"],
                "position_id": pos["id"],
                "notional": round(ep * qty, 4),
            }
            result.append(entry)
            total_unrealised += net_pnl

    return result, round(total_unrealised, 4)


def calc_total_realised():
    with state_lock:
        return round(sum(o.get("net_pnl", 0) for o in state["orders"] if o.get("type") == "close"), 4)


def _next_order_id():
    oid = state["next_order_id"]
    state["next_order_id"] += 1
    return oid


# ─────────────────────────────────────────────
# CORS HELPER
# ─────────────────────────────────────────────
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.after_request
def add_cors(resp):
    return cors(resp)


@app.route("/api/<path:p>", methods=["OPTIONS"])
def options_handler(p):
    return cors(jsonify({}))


# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@app.route("/api/prices")
def api_prices():
    with state_lock:
        return jsonify({
            "prices": state["prices"].copy(),
            "fetch_ok": state["fetch_ok"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "coins": COINS,
        })


@app.route("/api/prices/<coin_id>")
def api_price_single(coin_id):
    if coin_id not in COINS:
        return jsonify({"error": "unknown coin"}), 404
    with state_lock:
        price = state["prices"].get(coin_id)
    return jsonify({"coin_id": coin_id, "symbol": COINS[coin_id]["symbol"], "price": price,
                    "ts": datetime.now(timezone.utc).isoformat()})


@app.route("/api/prices/history/<coin_id>")
def api_price_history(coin_id):
    if coin_id not in COINS:
        return jsonify({"error": "unknown coin"}), 404
    limit = min(int(request.args.get("limit", 100)), PRICE_HISTORY_SIZE)
    with state_lock:
        hist = list(state["price_history"][coin_id])[-limit:]
    return jsonify({"coin_id": coin_id, "symbol": COINS[coin_id]["symbol"], "history": hist})


@app.route("/api/portfolio")
def api_portfolio():
    positions, unrealised = calc_pnl()
    realised = calc_total_realised()
    with state_lock:
        balance = state["balance"]
        orders  = list(state["orders"])

    # Compute equity = cash balance + notional value of positions (marked to market)
    equity = balance
    for p in positions:
        if p["side"] == "long":
            equity += p["current_price"] * p["qty"]
        else:
            equity += p["entry_price"] * p["qty"]  # margin locked

    return jsonify({
        "balance": round(balance, 4),
        "equity": round(equity, 4),
        "unrealised_pnl": unrealised,
        "realised_pnl": realised,
        "total_pnl": round(unrealised + realised, 4),
        "positions": positions,
        "order_count": len(orders),
        "ts": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/pnl")
def api_pnl():
    positions, unrealised = calc_pnl()
    realised = calc_total_realised()
    with state_lock:
        orders = [o for o in state["orders"] if o.get("type") == "close"]

    return jsonify({
        "unrealised": unrealised,
        "realised": realised,
        "total": round(unrealised + realised, 4),
        "positions": positions,
        "closed_trades": orders[-50:],  # last 50
        "taker_fee_rate": TAKER_FEE,
        "maker_fee_rate": MAKER_FEE,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/orders")
def api_orders():
    with state_lock:
        orders = list(state["orders"])
    return jsonify({"orders": orders[-100:], "total": len(orders)})


@app.route("/api/order/open", methods=["POST"])
def api_order_open():
    """
    Open a new position.
    Body JSON:
      coin_id: str
      side: "long" | "short"
      usdt_amount: float   (how much USDT to spend)
      qty: float           (alternative: exact coin qty)
    """
    data = request.get_json(force=True) or {}
    coin_id = data.get("coin_id", "").lower()

    if coin_id not in COINS:
        return jsonify({"error": f"Unknown coin '{coin_id}'. Available: {list(COINS.keys())}"}), 400

    side = data.get("side", "long").lower()
    if side not in ("long", "short"):
        return jsonify({"error": "side must be 'long' or 'short'"}), 400

    with state_lock:
        price = state["prices"].get(coin_id)
        if not price:
            return jsonify({"error": "Price not available yet, try again shortly"}), 503

        # Determine quantity
        if "qty" in data and float(data["qty"]) > 0:
            qty = float(data["qty"])
            usdt_cost = qty * price
        elif "usdt_amount" in data and float(data["usdt_amount"]) > 0:
            usdt_cost = float(data["usdt_amount"])
            qty = usdt_cost / price
        else:
            return jsonify({"error": "Provide either 'usdt_amount' or 'qty'"}), 400

        if qty <= 0:
            return jsonify({"error": "qty must be positive"}), 400

        entry_fee = usdt_cost * TAKER_FEE
        total_cost = usdt_cost + entry_fee

        if total_cost > state["balance"]:
            return jsonify({"error": f"Insufficient balance. Need {total_cost:.2f} USDT, have {state['balance']:.2f}"}), 400

        # If already have position in same coin, merge (simple average)
        if coin_id in state["positions"] and state["positions"][coin_id]["side"] == side:
            existing = state["positions"][coin_id]
            old_notional = existing["entry_price"] * existing["qty"]
            new_notional = price * qty
            combined_qty = existing["qty"] + qty
            avg_price = (old_notional + new_notional) / combined_qty
            existing["qty"] = combined_qty
            existing["entry_price"] = avg_price
            action = "increased"
        elif coin_id in state["positions"] and state["positions"][coin_id]["side"] != side:
            return jsonify({"error": f"Already have a {state['positions'][coin_id]['side']} position in {coin_id}. Close it first."}), 400
        else:
            oid = _next_order_id()
            state["positions"][coin_id] = {
                "id": oid,
                "side": side,
                "qty": qty,
                "entry_price": price,
                "open_time": datetime.now(timezone.utc).isoformat(),
                "coin_id": coin_id,
            }
            action = "opened"

        state["balance"] -= total_cost

        order_record = {
            "id": _next_order_id(),
            "type": "open",
            "coin_id": coin_id,
            "symbol": COINS[coin_id]["symbol"],
            "side": side,
            "qty": round(qty, 8),
            "price": price,
            "notional": round(usdt_cost, 4),
            "fee": round(entry_fee, 4),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        state["orders"].append(order_record)

    return jsonify({
        "status": "ok",
        "action": action,
        "coin_id": coin_id,
        "side": side,
        "qty": round(qty, 8),
        "entry_price": price,
        "fee_paid": round(entry_fee, 4),
        "balance_after": round(state["balance"], 4),
        "order": order_record,
    })


@app.route("/api/order/close", methods=["POST"])
def api_order_close():
    """
    Close an open position.
    Body JSON:
      coin_id: str
      qty: float  (optional, defaults to full position)
    """
    data = request.get_json(force=True) or {}
    coin_id = data.get("coin_id", "").lower()

    if coin_id not in COINS:
        return jsonify({"error": f"Unknown coin: {coin_id}"}), 400

    with state_lock:
        if coin_id not in state["positions"]:
            return jsonify({"error": f"No open position for {coin_id}"}), 400

        pos   = state["positions"][coin_id]
        price = state["prices"].get(coin_id, pos["entry_price"])
        side  = pos["side"]
        ep    = pos["entry_price"]

        close_qty = float(data.get("qty", pos["qty"]))
        if close_qty <= 0 or close_qty > pos["qty"]:
            close_qty = pos["qty"]

        notional = price * close_qty

        if side == "long":
            raw_pnl = (price - ep) * close_qty
        else:
            raw_pnl = (ep - price) * close_qty

        entry_fee_portion = ep * close_qty * TAKER_FEE
        close_fee         = price * close_qty * TAKER_FEE
        total_fee         = entry_fee_portion + close_fee
        net_pnl           = raw_pnl - close_fee   # entry fee already paid at open

        returned = notional if side == "long" else (ep * close_qty)
        state["balance"] += returned + net_pnl - (0 if side == "long" else 0)

        # Simpler: return cash = original margin + net_pnl
        # On long: you sell at price, get back notional (price*qty), fee deducted
        state["balance"] = round(state["balance"], 8)

        if close_qty >= pos["qty"]:
            del state["positions"][coin_id]
            close_type = "full"
        else:
            pos["qty"] -= close_qty
            close_type = "partial"

        order_record = {
            "id": _next_order_id(),
            "type": "close",
            "close_type": close_type,
            "coin_id": coin_id,
            "symbol": COINS[coin_id]["symbol"],
            "side": side,
            "qty": round(close_qty, 8),
            "entry_price": ep,
            "close_price": price,
            "notional": round(notional, 4),
            "raw_pnl": round(raw_pnl, 4),
            "close_fee": round(close_fee, 4),
            "net_pnl": round(net_pnl, 4),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        state["orders"].append(order_record)

    return jsonify({
        "status": "ok",
        "coin_id": coin_id,
        "close_type": close_type,
        "close_price": price,
        "qty_closed": round(close_qty, 8),
        "raw_pnl": round(raw_pnl, 4),
        "close_fee": round(close_fee, 4),
        "net_pnl": round(net_pnl, 4),
        "balance_after": round(state["balance"], 4),
        "order": order_record,
    })


@app.route("/api/order/close_all", methods=["POST"])
def api_close_all():
    """Close all open positions at once."""
    results = []
    with state_lock:
        coins_to_close = list(state["positions"].keys())

    for coin_id in coins_to_close:
        resp = app.test_client().post(
            "/api/order/close",
            json={"coin_id": coin_id},
        )
        results.append(json.loads(resp.data))

    return jsonify({"status": "ok", "closed": results})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset simulation to initial state."""
    with state_lock:
        state["balance"] = INITIAL_BALANCE
        state["positions"].clear()
        state["orders"].clear()
        state["next_order_id"] = 1
    return jsonify({"status": "ok", "balance": INITIAL_BALANCE})


@app.route("/api/stream")
def api_stream():
    """
    Server-Sent Events stream.
    Emits price + portfolio snapshot every second.
    """
    def generate():
        while True:
            with state_lock:
                prices = state["prices"].copy()
                fetch_ok = state["fetch_ok"]

            positions, unrealised = calc_pnl()
            realised = calc_total_realised()
            with state_lock:
                balance = state["balance"]

            payload = {
                "prices": prices,
                "fetch_ok": fetch_ok,
                "balance": round(balance, 4),
                "unrealised_pnl": unrealised,
                "realised_pnl": realised,
                "total_pnl": round(unrealised + realised, 4),
                "positions": positions,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(TICK_INTERVAL)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/info")
def api_info():
    return jsonify({
        "name": "Crypto Trading Simulator",
        "version": "1.0",
        "coins": COINS,
        "fees": {"taker": TAKER_FEE, "maker": MAKER_FEE},
        "initial_balance": INITIAL_BALANCE,
        "endpoints": {
            "GET  /api/prices": "All current prices",
            "GET  /api/prices/<id>": "Single coin price",
            "GET  /api/prices/history/<id>": "Price history (last 200 ticks)",
            "GET  /api/portfolio": "Portfolio snapshot",
            "GET  /api/pnl": "PnL breakdown",
            "GET  /api/orders": "Order history",
            "POST /api/order/open": "Open position {coin_id, side, usdt_amount|qty}",
            "POST /api/order/close": "Close position {coin_id, qty?}",
            "POST /api/order/close_all": "Close all positions",
            "POST /api/reset": "Reset simulation",
            "GET  /api/stream": "SSE real-time stream",
        }
    })


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
if __name__ == "__main__":
    price_thread = threading.Thread(target=price_loop, daemon=True)
    price_thread.start()
    print("\n" + "="*55)
    print("  🚀 Crypto Trading Simulator")
    print("="*55)
    print(f"  Dashboard : http://localhost:5000")
    print(f"  API Info  : http://localhost:5000/api/info")
    print(f"  SSE Stream: http://localhost:5000/api/stream")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)