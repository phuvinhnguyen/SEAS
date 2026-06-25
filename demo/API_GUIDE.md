# 🚀 Crypto Trading Simulator - API Guide

Hướng dẫn chi tiết về cách tương tác với API để tạo và kiểm tra các thuật toán trading tự động (live trading).

---

## 📋 Mục Lục

1. [Khởi động Server](#khởi-động-server)
2. [API Endpoints](#api-endpoints)
3. [Ví dụ cơ bản](#ví-dụ-cơ-bản)
4. [Xây dựng Thuật toán Trading](#xây-dựng-thuật-toán-trading)
5. [Demo: Momentum Trading Algorithm](#demo-momentum-trading-algorithm)
6. [Real-time Streaming](#real-time-streaming)

---

## 🎯 Khởi động Server

```bash
cd /home/raven/Vietnam/SEAS/demo
python server.py
```

Output:
```
=========================================================
  🚀 Crypto Trading Simulator
=========================================================
  Dashboard : http://localhost:5000
  API Info  : http://localhost:5000/api/info
  SSE Stream: http://localhost:5000/api/stream
========================================================= 
```

Truy cập dashboard: **http://localhost:5000**

---

## 📡 API Endpoints

### 1. **GET /api/prices** - Lấy giá hiện tại

Lấy giá hiện tại của tất cả các coin.

```bash
curl http://localhost:5000/api/prices
```

Response:
```json
{
  "prices": {
    "bitcoin": 67500.5,
    "ethereum": 3520.2,
    "binancecoin": 580.1,
    "solana": 168.3,
    "ripple": 0.52
  },
  "fetch_ok": true,
  "ts": "2026-06-25T10:30:45.123456+00:00",
  "coins": {
    "bitcoin": {"symbol": "BTC", "id": "bitcoin"},
    ...
  }
}
```

### 2. **GET /api/prices/<coin_id>** - Lấy giá một coin

```bash
curl http://localhost:5000/api/prices/bitcoin
```

### 3. **GET /api/prices/history/<coin_id>** - Lấy lịch sử giá

```bash
curl "http://localhost:5000/api/prices/history/bitcoin?limit=50"
```

Response: Array của 50 tick gần nhất với timestamp

### 4. **GET /api/portfolio** - Xem portfolio hiện tại

```bash
curl http://localhost:5000/api/portfolio
```

Response:
```json
{
  "balance": 9500.0,
  "equity": 10250.5,
  "unrealised_pnl": 250.5,
  "realised_pnl": 0.0,
  "total_pnl": 250.5,
  "positions": [
    {
      "coin_id": "bitcoin",
      "symbol": "BTC",
      "side": "long",
      "qty": 0.0125,
      "entry_price": 67500.0,
      "current_price": 67600.5,
      "raw_pnl": 1.25,
      "close_fee": 0.0256,
      "net_pnl": 0.99,
      "pct": 0.15,
      "open_time": "2026-06-25T10:20:00Z",
      "position_id": 1,
      "notional": 843.75
    }
  ],
  "order_count": 1,
  "ts": "2026-06-25T10:30:45Z"
}
```

### 5. **POST /api/order/open** - Mở Position

Mở position long hoặc short.

```bash
curl -X POST http://localhost:5000/api/order/open \
  -H "Content-Type: application/json" \
  -d '{
    "coin_id": "bitcoin",
    "side": "long",
    "usdt_amount": 500
  }'
```

Hoặc chỉ định số lượng:
```bash
curl -X POST http://localhost:5000/api/order/open \
  -H "Content-Type: application/json" \
  -d '{
    "coin_id": "ethereum",
    "side": "short",
    "qty": 1.5
  }'
```

Response:
```json
{
  "status": "ok",
  "action": "opened",
  "coin_id": "bitcoin",
  "side": "long",
  "qty": 0.0074,
  "entry_price": 67500.0,
  "fee_paid": 0.30,
  "balance_after": 9169.70,
  "order": {
    "id": 1,
    "type": "open",
    "coin_id": "bitcoin",
    "symbol": "BTC",
    "side": "long",
    "qty": 0.0074,
    "price": 67500.0,
    "notional": 500.0,
    "fee": 0.30,
    "ts": "2026-06-25T10:30:00Z"
  }
}
```

### 6. **POST /api/order/close** - Đóng Position

Đóng một position (hoặc một phần).

```bash
# Đóng toàn bộ position
curl -X POST http://localhost:5000/api/order/close \
  -H "Content-Type: application/json" \
  -d '{"coin_id": "bitcoin"}'

# Đóng một phần (0.005 BTC)
curl -X POST http://localhost:5000/api/order/close \
  -H "Content-Type: application/json" \
  -d {
    "coin_id": "bitcoin",
    "qty": 0.005
  }'
```

### 7. **POST /api/order/close_all** - Đóng tất cả Positions

```bash
curl -X POST http://localhost:5000/api/order/close_all
```

### 8. **POST /api/reset** - Reset Simulation

Reset lại trạng thái ban đầu (balance = 10,000 USDT).

```bash
curl -X POST http://localhost:5000/api/reset
```

### 9. **GET /api/stream** - Real-time SSE Stream

Nhận dữ liệu real-time qua Server-Sent Events (cập nhật mỗi giây).

```bash
curl http://localhost:5000/api/stream
```

---

## 💡 Ví dụ cơ bản

### Python: Mở position và kiểm tra PnL

```python
import requests
import json
import time

BASE_URL = "http://localhost:5000"

# 1. Lấy giá hiện tại
resp = requests.get(f"{BASE_URL}/api/prices")
prices = resp.json()["prices"]
print(f"BTC: ${prices['bitcoin']}")

# 2. Mở position long
trade = requests.post(f"{BASE_URL}/api/order/open", json={
    "coin_id": "bitcoin",
    "side": "long",
    "usdt_amount": 1000
}).json()
print(f"Opened: {trade['qty']} BTC at ${trade['entry_price']}")

# 3. Chờ một chút
time.sleep(5)

# 4. Kiểm tra portfolio
portfolio = requests.get(f"{BASE_URL}/api/portfolio").json()
print(f"Balance: ${portfolio['balance']:.2f}")
print(f"Unrealised PnL: ${portfolio['unrealised_pnl']:.2f}")

# 5. Đóng position
close = requests.post(f"{BASE_URL}/api/order/close", json={
    "coin_id": "bitcoin"
}).json()
print(f"Closed: Profit/Loss = ${close['net_pnl']:.2f}")
```

---

## 🤖 Xây dựng Thuật toán Trading

### Template cơ bản:

```python
import requests
import time
from collections import deque

class SimpleAlgorithm:
    def __init__(self, api_url="http://localhost:5000", coin="bitcoin"):
        self.api_url = api_url
        self.coin = coin
        self.price_history = deque(maxlen=20)  # Lưu 20 giá gần nhất
        self.position_open = False
        
    def get_price(self):
        """Lấy giá hiện tại"""
        resp = requests.get(f"{self.api_url}/api/prices/{self.coin}")
        return resp.json()["price"]
    
    def get_portfolio(self):
        """Lấy thông tin portfolio"""
        resp = requests.get(f"{self.api_url}/api/portfolio")
        return resp.json()
    
    def open_position(self, side, amount):
        """Mở position"""
        resp = requests.post(
            f"{self.api_url}/api/order/open",
            json={
                "coin_id": self.coin,
                "side": side,
                "usdt_amount": amount
            }
        )
        return resp.json()
    
    def close_position(self):
        """Đóng position"""
        resp = requests.post(
            f"{self.api_url}/api/order/close",
            json={"coin_id": self.coin}
        )
        return resp.json()
    
    def run_signal(self):
        """
        Override hàm này để triển khai logic trading của bạn
        Return: "BUY", "SELL", hoặc "HOLD"
        """
        raise NotImplementedError("Implement run_signal()")
    
    def execute_trade(self, signal):
        """Thực hiện giao dịch dựa trên signal"""
        portfolio = self.get_portfolio()
        balance = portfolio["balance"]
        
        if signal == "BUY" and not self.position_open and balance > 100:
            self.open_position("long", min(500, balance * 0.8))
            self.position_open = True
            print(f"✅ BUY signal executed")
            
        elif signal == "SELL" and self.position_open:
            self.close_position()
            self.position_open = False
            print(f"✅ SELL signal executed")
    
    def backtest(self, duration_seconds=60):
        """Chạy thuật toán trong khoảng thời gian"""
        start = time.time()
        while time.time() - start < duration_seconds:
            try:
                price = self.get_price()
                self.price_history.append(price)
                
                # Tính signal
                signal = self.run_signal()
                
                # Thực hiện giao dịch
                self.execute_trade(signal)
                
                # In stats
                portfolio = self.get_portfolio()
                print(f"[{time.strftime('%H:%M:%S')}] "
                      f"Price: ${price:.2f} | "
                      f"Balance: ${portfolio['balance']:.2f} | "
                      f"PnL: ${portfolio['total_pnl']:.2f}")
                
                time.sleep(2)  # 2s delay giữa các signal
                
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
```

---

## 🎯 Demo: Momentum Trading Algorithm

Thuật toán này mua khi giá tăng 20 ticks và bán khi giá giảm 10 ticks.

```python
import requests
import time
from collections import deque

class MomentumTrader:
    def __init__(self, api_url="http://localhost:5000", coin="bitcoin"):
        self.api_url = api_url
        self.coin = coin
        self.price_history = deque(maxlen=20)
        self.position_open = False
        self.buy_price = None
        
    def get_price(self):
        resp = requests.get(f"{self.api_url}/api/prices/{self.coin}")
        return resp.json()["price"]
    
    def get_portfolio(self):
        resp = requests.get(f"{self.api_url}/api/portfolio")
        return resp.json()
    
    def open_position(self, side, amount):
        resp = requests.post(
            f"{self.api_url}/api/order/open",
            json={
                "coin_id": self.coin,
                "side": side,
                "usdt_amount": amount
            }
        )
        result = resp.json()
        self.buy_price = result.get("entry_price")
        return result
    
    def close_position(self):
        resp = requests.post(
            f"{self.api_url}/api/order/close",
            json={"coin_id": self.coin}
        )
        return resp.json()
    
    def calculate_signal(self):
        """
        Momentum Strategy:
        - BUY: Nếu giá tăng 0.5% trong 20 tick gần nhất
        - SELL: Nếu position lợi nhuận > 1% hoặc lỗ > -0.5%
        """
        if len(self.price_history) < 5:
            return "HOLD"
        
        current_price = self.price_history[-1]
        avg_price_5 = sum(list(self.price_history)[-5:]) / 5
        
        # Momentum: giá hiện tại so với trung bình 5 tick
        momentum = (current_price - avg_price_5) / avg_price_5 * 100
        
        if not self.position_open:
            # BUY nếu momentum > 0.5%
            if momentum > 0.5:
                return "BUY"
        else:
            # SELL nếu lãi > 1% hoặc lỗ > -0.5%
            if self.buy_price:
                profit_pct = (current_price - self.buy_price) / self.buy_price * 100
                if profit_pct > 1.0 or profit_pct < -0.5:
                    return "SELL"
        
        return "HOLD"
    
    def run(self, duration_seconds=300):
        """Chạy trading bot trong 5 phút"""
        print(f"\n🤖 Momentum Trading Bot Started ({self.coin.upper()})")
        print(f"   Duration: {duration_seconds}s")
        print("="*70)
        
        start = time.time()
        trades = 0
        
        while time.time() - start < duration_seconds:
            try:
                # 1. Lấy giá
                price = self.get_price()
                self.price_history.append(price)
                
                # 2. Tính signal
                signal = self.calculate_signal()
                
                # 3. Thực hiện
                portfolio = self.get_portfolio()
                balance = portfolio["balance"]
                
                if signal == "BUY" and not self.position_open and balance > 200:
                    result = self.open_position("long", min(500, balance * 0.7))
                    self.position_open = True
                    trades += 1
                    print(f"[BUY #{trades}] Price: ${price:.2f} | "
                          f"Balance: ${balance:.2f}")
                
                elif signal == "SELL" and self.position_open:
                    result = self.close_position()
                    pnl = result.get("net_pnl", 0)
                    self.position_open = False
                    trades += 1
                    print(f"[SELL #{trades}] Price: ${price:.2f} | "
                          f"PnL: ${pnl:+.2f} | Balance: ${balance:.2f}")
                
                else:
                    status = "🟢 LONG" if self.position_open else "⚪ FLAT"
                    print(f"[{status}] Price: ${price:.2f} | "
                          f"Signal: {signal} | "
                          f"Balance: ${balance:.2f}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
        
        # Close position nếu còn mở
        if self.position_open:
            self.close_position()
            print("\n[CLOSE] Closed remaining position")
        
        print("="*70)
        print(f"✅ Bot stopped. Trades executed: {trades}")
        final = self.get_portfolio()
        print(f"Final Balance: ${final['balance']:.2f}")
        print(f"Total PnL: ${final['total_pnl']:.2f}")


# Chạy bot
if __name__ == "__main__":
    trader = MomentumTrader(coin="bitcoin")
    trader.run(duration_seconds=300)  # Chạy 5 phút
```

**Chạy:**
```bash
python momentum_trader.py
```

---

## 📊 Real-time Streaming

Nhận dữ liệu real-time mỗi giây:

```python
import requests
import json
import time

def stream_prices():
    """Stream real-time prices qua SSE"""
    url = "http://localhost:5000/api/stream"
    response = requests.get(url, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                prices = data['prices']
                pnl = data['unrealised_pnl']
                
                print(f"BTC: ${prices['bitcoin']:,.2f} | "
                      f"ETH: ${prices['ethereum']:,.2f} | "
                      f"PnL: ${pnl:+.2f}")

# Chạy
stream_prices()
```

---

## 📈 Các Thuật toán Trading Phổ Biến

### 1. **Mean Reversion**
```python
# Mua khi giá dưới trung bình, bán khi trên trung bình
ma_20 = average_of_last_20_prices
if price < ma_20 * 0.99:
    signal = "BUY"
elif price > ma_20 * 1.01:
    signal = "SELL"
```

### 2. **RSI (Relative Strength Index)**
```python
# Mua khi RSI < 30, bán khi RSI > 70
rsi = calculate_rsi(price_history, period=14)
if rsi < 30:
    signal = "BUY"
elif rsi > 70:
    signal = "SELL"
```

### 3. **MACD (Moving Average Convergence Divergence)**
```python
# Mua khi MACD cắt vượt signal line
macd = calculate_macd(price_history)
if macd > signal_line:
    signal = "BUY"
elif macd < signal_line:
    signal = "SELL"
```

### 4. **Pair Trading**
```python
# Trade tương quan giữa 2 coin
ratio = price_btc / price_eth
if ratio > ratio_mean + std:
    signal = "SHORT_BTC_LONG_ETH"
```

---

## 🔧 Troubleshooting

### Error: 429 Too Many Requests
**Giải pháp:** API chỉ cập nhật giá mỗi 10 phút. Đừng call `/api/prices` quá nhanh.

### Error: Insufficient Balance
**Giải pháp:** Reset với `POST /api/reset` để lấy $10,000 USDT mới.

### Position Not Closing
**Giải pháp:** Đảm bảo `coin_id` chính xác. Kiểm tra position đã mở chưa với `GET /api/portfolio`.

---

## 📚 Tham khảo

- **Dashboard:** http://localhost:5000
- **API Info:** http://localhost:5000/api/info
- **Server logs:** Xem terminal chạy `python server.py`

---

**Tạo ngày:** 2026-06-25  
**Version:** 1.0
