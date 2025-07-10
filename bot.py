from flask import Flask, request
import os
import threading
import traceback
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests

app = Flask(__name__)

# 读取环境变量
BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")  # 群组或用户的 ID

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print("❌ 发送消息失败：", response.text)
    except Exception as e:
        print("❌ 发送消息出错：", str(e))

def send_photo(chat_id, image_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": chat_id, "caption": caption}
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                print(f"✅ 图表已发送：{image_path}")
            else:
                print(f"❌ 图表发送失败：{response.text}")
    except Exception as e:
        print("❌ 上传图片失败：", str(e))

def run_all():
    stocks = ["5255.KL", "0209.KL"]
    os.makedirs("charts", exist_ok=True)

    for stock in stocks:
        print(f"📈 正在抓取：{stock}")
        df = yf.download(stock, period="5d", interval="1d")
        if df.empty:
            print(f"⚠️ {stock} 无数据")
            continue

        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()

        latest = df.iloc[-1]
        try:
            open_price = float(latest["Open"])
            close_price = float(latest["Close"])
        except:
            open_price = close_price = 0.0

        change = close_price - open_price
        pct = (change / open_price * 100) if open_price else 0.0

        if change > 0:
            trend_icon = "📈 上涨"
        elif change < 0:
            trend_icon = "📉 下跌"
        else:
            trend_icon = "➖ 无涨跌"

        caption = f"""📊 {stock} 报告
开盘：RM {open_price:.3f}
收盘：RM {close_price:.3f}
涨跌：{trend_icon} {change:.3f}（{pct:.2f}%）
"""

        # 生成图表
        hist = yf.download(stock, period="60d", interval="1d")
        hist["MA5"] = hist["Close"].rolling(5).mean()
        hist["MA20"] = hist["Close"].rolling(20).mean()

        plt.figure(figsize=(12, 6))
        plt.plot(hist["Close"], label="收盘", color="black")
        plt.plot(hist["MA5"], label="MA5", color="blue")
        plt.plot(hist["MA20"], label="MA20", color="red")
        plt.title(f"{stock} 近60日走势")
        plt.xlabel("日期")
        plt.ylabel("价格 (RM)")
        plt.grid(True)
        plt.legend()
        chart_path = f"charts/{stock}.png"
        plt.savefig(chart_path)
        plt.close()

        send_photo(CHAT_ID, chart_path, caption)

# ===== Flask 路由 =====

@app.route("/")
def home():
    return "✅ MyStock Bot 正在运行"

@app.route("/run")
def manual_run():
    threading.Thread(target=run_all).start()
    return "📈 股票分析任务开始执行！"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 收到 Telegram 消息：", data)

        message = data.get("message") or data.get("edited_message")
        if not message:
            return "No message found"

        text = message.get("text", "").lower()
        chat_id = message["chat"]["id"]

        if "stock" in text or "报告" in text:
            send_message(chat_id, "📊 正在生成股票报告...")
            threading.Thread(target=run_all).start()
        else:
            send_message(chat_id, f"🤖 你说的是：{text}")

        return "OK"
    except Exception as e:
        print("❌ Webhook 处理出错：", str(e))
        traceback.print_exc()
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
