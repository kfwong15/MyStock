import os
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
from flask import Flask, request
import threading

# === Telegram Bot 配置 ===
TG_BOT_TOKEN = "7976682927:AAHVwjcfg4fzP9Wu6wv0ue2LdPSzrmE6oE0"
TG_CHAT_ID = "-1002721174982"

# === Flask 初始化 ===
app = Flask(__name__)

# === 发送图片到 Telegram 群组 ===
def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        files = {"photo": photo}
        data = {"chat_id": TG_CHAT_ID, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送：{photo_path}")
        else:
            print(f"❌ 发送失败：{response.text}")

# === 给用户回复文字消息 ===
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(url, data=data)
    print(f"📤 回复消息状态码：{response.status_code}")

# === 股票分析任务 ===
def generate_stock_report(stock_code):
    print(f"📥 正在抓取 {stock_code} 的数据...")
    df = yf.download(stock_code, period="30d", interval="1d", auto_adjust=False)
    if df.empty:
        print(f"⚠️ 无法获取 {stock_code} 的数据")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()

    os.makedirs("charts", exist_ok=True)
    image_path = f"charts/{stock_code.replace('.KL','')}.png"

    plt.figure(figsize=(10, 5))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{stock_code} - 30日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(image_path)
    plt.close()

    try:
        latest = df.iloc[-1]
        open_price = float(latest["Open"])
        close_price = float(latest["Close"])
        change = close_price - open_price
        pct = (change / open_price) * 100 if open_price != 0 else 0
    except Exception as e:
        print(f"❌ 数据处理出错: {e}")
        return

    trend = "📈 上涨" if change > 0 else "📉 下跌" if change < 0 else "➖ 持平"
    caption = (
        f"📊 股票：{stock_code}\n"
        f"开市：RM {open_price:.2f}\n"
        f"收市：RM {close_price:.2f}\n"
        f"涨跌：{trend} RM {change:.2f}（{pct:.2f}%）"
    )

    send_telegram_photo(image_path, caption)

def run_all_stocks():
    stock_list = ["5255.KL", "0209.KL"]
    for stock in stock_list:
        generate_stock_report(stock)

# === 首页 ===
@app.route("/")
def index():
    return "✅ MyStock Bot 正在运行"

# === 手动运行任务 ===
@app.route("/run")
def run_job():
    threading.Thread(target=run_all_stocks).start()
    return "📊 股票分析任务已启动"

# ✅ Telegram Webhook 路由（自动回复）
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 收到 Telegram 消息：", data)

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            reply = f"✅ 你发送了：{text}"
            send_message(chat_id, reply)

        return "OK"
    except Exception as e:
        print("❌ Webhook 处理出错：", e)
        return "Internal Server Error", 500

# === 启动服务器 ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
