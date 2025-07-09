import os
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
from flask import Flask, request, jsonify

# ========== 环境变量 ==========
TG_BOT_TOKEN     = os.getenv("TG_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CHART_DIR        = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# ========== Flask App ==========
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": True})

    msg = data["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]

    if text.startswith("/stock"):
        parts = text.split()
        if len(parts) != 2:
            send_to_telegram("⚠️ 用法：/stock 股票代码，例如 /stock 5255.KL", chat_id)
        else:
            symbol = parts[1].upper()
            result, chart_path = generate_stock_report(symbol)
            send_to_telegram(result, chat_id, chart_path)
    else:
        send_to_telegram("🤖 指令无效，请输入 /stock 股票代码", chat_id)

    return jsonify({"ok": True})

# ========== 工具函数 ==========
def fetch_data(symbol):
    df = yf.download(symbol, period="3mo", interval="1d", auto_adjust=True)
    df.dropna(inplace=True)
    return df

def compute_indicators(df):
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    delta      = df["Close"].diff()
    gain       = delta.where(delta > 0, 0.0)
    loss       = -delta.where(delta < 0, 0.0)
    avg_gain   = gain.rolling(14).mean()
    avg_loss   = loss.rolling(14).mean()
    rs         = avg_gain / avg_loss
    df["RSI"]  = 100 - (100 / (1 + rs))
    ema12      = df["Close"].ewm(span=12).mean()
    ema26      = df["Close"].ewm(span=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9).mean()
    return df

def draw_chart(symbol, df):
    plt.figure(figsize=(10,5))
    df["Close"].tail(60).plot(label="收盘价", color="black")
    df["MA5"].tail(60).plot(label="MA5", linestyle="--", color="blue")
    df["MA20"].tail(60).plot(label="MA20", linestyle="--", color="red")
    plt.title(f"{symbol} 近60日走势")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    path = f"{CHART_DIR}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path)
    plt.close()
    return path

def ask_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key 未设置"
    try:
        res = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role":"system", "content":"你是马来西亚股票分析师，回复简洁中文。"},
                    {"role":"user",   "content": prompt}
                ]
            },
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ DeepSeek API 错误：{e}"

def send_to_telegram(text, chat_id, img_path=None):
    if img_path and os.path.exists(img_path):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        with open(img_path, "rb") as pic:
            files = {"photo": pic}
            data = {"chat_id": chat_id, "caption": text}
            requests.post(url, data=data, files=files)
    else:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text})

def generate_stock_report(symbol):
    df = fetch_data(symbol)
    if df.empty:
        return f"⚠️ 找不到 {symbol} 的数据。", None

    df = compute_indicators(df)
    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    open_p  = float(today["Open"])
    close_p = float(today["Close"])
    diff    = close_p - open_p
    pct     = (diff / open_p) * 100 if open_p != 0 else 0
    trend   = "📈 上涨" if diff > 0 else "📉 下跌" if diff < 0 else "➖ 无涨跌"

    macd_val    = float(today["MACD"])
    signal_val  = float(today["MACD_SIGNAL"])
    rsi_val     = float(today["RSI"])

    signals = []
    if macd_val > signal_val and float(yesterday["MACD"]) <= float(yesterday["MACD_SIGNAL"]):
        signals.append("🟢 MACD 金叉，或有上升动能。")
    elif macd_val < signal_val and float(yesterday["MACD"]) >= float(yesterday["MACD_SIGNAL"]):
        signals.append("🔴 MACD 死叉，或面临下跌。")
    if rsi_val > 70:
        signals.append("🔴 RSI 超买")
    elif rsi_val < 30:
        signals.append("🟢 RSI 超卖")

    prompt = (
        f"{symbol} 今日开盘 RM{open_p:.2f}，收盘 RM{close_p:.2f}，"
        f"涨幅 {pct:.2f}%；MA5 {today['MA5']:.2f}，MA20 {today['MA20']:.2f}；"
        f"RSI {rsi_val:.2f}，MACD {macd_val:.2f}，Signal {signal_val:.2f}。"
    )
    ai_comment = ask_deepseek(prompt)

    msg = (
        f"📊 {symbol} 股票简报\n"
        f"开盘价：RM {open_p:.3f}\n"
        f"收盘价：RM {close_p:.3f}\n"
        f"涨跌：{trend} RM {abs(diff):.3f}（{pct:.2f}%）\n"
        + ("\n".join(signals) if signals else "") +
        f"\n\n🤖 DeepSeek 分析：\n{ai_comment}"
    )

    chart = draw_chart(symbol, df)
    return msg, chart

# ========== 本地测试模式（选填） ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
