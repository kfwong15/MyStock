from flask import Flask, request
import os, requests, yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import io

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})

def send_photo(chat_id, image_bytes, caption=""):
    files = {"photo": ("chart.png", image_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    requests.post(f"{TELEGRAM_API}/sendPhoto", files=files, data=data)

def analyze_stock(symbol):
    df = yf.download(symbol, period="60d", interval="1d", auto_adjust=True)
    if df.empty: return None, "⚠️ 找不到股票数据"

    # 技术指标
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    df["EMA12"] = df["Close"].ewm(span=12).mean()
    df["EMA26"] = df["Close"].ewm(span=26).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]

    latest = df.iloc[-1]
    text = (
        f"📊 {symbol} 股票分析\n"
        f"收盘价：RM {latest['Close']:.3f}\n"
        f"MA5：{latest['MA5']:.3f} | MA20：{latest['MA20']:.3f}\n"
        f"RSI：{latest['RSI']:.2f} | MACD：{latest['MACD']:.3f}\n"
    )

    # AI 解读
    ai_msg = ask_deepseek(f"{symbol} 收盘价为 RM {latest['Close']:.2f}，RSI 为 {latest['RSI']:.2f}，MACD 为 {latest['MACD']:.2f}。请用中文简要分析股票短期趋势。")
    text += "\n🤖 DeepSeek 分析：\n" + ai_msg

    # 画图
    buf = io.BytesIO()
    plt.figure(figsize=(10, 5))
    plt.plot(df["Close"], label="Close", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{symbol} 近60日走势")
    plt.legend()
    plt.grid(True)
    plt.savefig(buf, format="png")
    buf.seek(0)

    return buf, text

def ask_deepseek(prompt):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return "❌ DeepSeek 失败"
    except Exception as e:
        return f"❌ DeepSeek 错误：{e}"

@app.route("/")
def home():
    return "✅ Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.startswith("/start"):
            send_message(chat_id, "👋 欢迎使用股票机器人！\n发送 /stock 代码，如 /stock 0209.KL")
        elif text.startswith("/stock"):
            parts = text.split()
            if len(parts) != 2:
                send_message(chat_id, "⚠️ 用法错误：请输入 /stock 股票代码")
            else:
                symbol = parts[1].strip()
                buf, msg = analyze_stock(symbol)
                if buf:
                    send_photo(chat_id, buf, caption=msg)
                else:
                    send_message(chat_id, msg)
        else:
            send_message(chat_id, "🤖 无效指令，请使用 /stock 代码")
    return "OK"

if __name__ == "__main__":
    app.run(debug=True)
