import os
import threading
import traceback
import requests
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, request

app = Flask(__name__)

# === 环境变量 ===
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID", "-1002721174982")

print("✅ BOT_TOKEN 已加载:", bool(BOT_TOKEN))
print("✅ CHAT_ID:", CHAT_ID)

# === 发送消息 ===
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(url, json=payload)
        print("📨 send_message 返回:", resp.text)
    except Exception as e:
        print("❌ send_message 出错:", e)

# === 发送图片 ===
def send_photo(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        data = {"chat_id": chat_id, "caption": caption}
        files = {"photo": photo}
        try:
            resp = requests.post(url, data=data, files=files)
            print("📸 send_photo 返回:", resp.text)
        except Exception as e:
            print("❌ send_photo 出错:", e)

# === 图表生成任务 ===
def generate_stock_report():
    print("📈 开始生成股票报告")
    my_stocks = ["5255.KL", "0209.KL"]
    os.makedirs("charts", exist_ok=True)

    for stock in my_stocks:
        print(f"📥 获取 {stock} 数据中...")
        df = yf.download(stock, period="5d", interval="1d", auto_adjust=False)

        if df.empty:
            print(f"⚠️ 无法获取 {stock} 数据")
            continue

        print("📊 原始数据：", df.tail())

        df["MA5"] = df["Close"].rolling(window=5).mean()
        df["MA20"] = df["Close"].rolling(window=20).mean()

        latest = df.iloc[[-1]]
        try:
            open_price = float(latest["Open"].iloc[0])
            close_price = float(latest["Close"].iloc[0])
        except:
            open_price = close_price = 0.0

        change = close_price - open_price
        pct = (change / open_price) * 100 if open_price else 0.0

        if change > 0:
            trend = "📈 上涨"
        elif change < 0:
            trend = "📉 下跌"
        else:
            trend = "➖ 无变化"

        caption = (
            f"📊 {stock} 股票走势\n"
            f"开市价：RM {open_price:.3f}\n"
            f"收市价：RM {close_price:.3f}\n"
            f"涨跌：{trend} RM {change:.3f}（{pct:.2f}%）"
        )

        # 中文乱码修复
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        hist = yf.download(stock, period="60d", interval="1d", auto_adjust=False)
        hist["MA5"] = hist["Close"].rolling(window=5).mean()
        hist["MA20"] = hist["Close"].rolling(window=20).mean()

        plt.figure(figsize=(12, 6))
        plt.plot(hist["Close"], label="收盘价", color="black")
        plt.plot(hist["MA5"], label="MA5", color="blue")
        plt.plot(hist["MA20"], label="MA20", color="red")
        plt.title(f"{stock} - 近60日走势图")
        plt.xlabel("日期")
        plt.ylabel("价格 (RM)")
        plt.legend()
        plt.grid(True)

        chart_path = f"charts/{stock.replace('.KL', '')}.png"
        plt.savefig(chart_path)
        plt.close()

        print(f"✅ 图表已保存: {chart_path}")
        send_photo(CHAT_ID, chart_path, caption)

# === /run 手动触发 ===
@app.route("/run")
def run():
    try:
        send_message(CHAT_ID, "📈 股票分析任务开始执行！")
        threading.Thread(target=generate_stock_report).start()
        return "OK"
    except Exception as e:
        print("❌ /run 出错:", str(e))
        traceback.print_exc()
        return "ERROR", 500

# === /webhook 接收指令 ===
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 收到 Telegram 消息：", data)

        message = data.get("message") or data.get("edited_message")
        if not message:
            return "No message"

        text = message.get("text", "").lower()
        chat_id = message["chat"]["id"]
        print("💬 用户发来：", text)

        if "报告" in text or "stock" in text:
            send_message(chat_id, "📊 正在生成股票报告...")
            threading.Thread(target=generate_stock_report).start()
        else:
            send_message(chat_id, "🤖 你说的是：" + text)

        return "OK"
    except Exception as e:
        print("❌ webhook 错误：", str(e))
        traceback.print_exc()
        return "Error", 500

# === 首页展示 ===
@app.route("/")
def index():
    return "✅ MyStock Bot 正常运行中！"
