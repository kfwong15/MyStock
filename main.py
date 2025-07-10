from flask import Flask, request
import os
import requests
import threading
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import traceback

app = Flask(__name__)

# === 基本配置 ===
BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID", "-1002721174982")  # 群组 ID

# === 创建图表目录 ===
os.makedirs("charts", exist_ok=True)

# === 发送消息 ===
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=data)

# === 发送图片 ===
def send_photo(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        data = {"chat_id": chat_id, "caption": caption}
        files = {"photo": photo}
        requests.post(url, data=data, files=files)

# === 股票图表和简报逻辑 ===
def generate_stock_report():
    stocks = ["5255.KL", "0209.KL"]
    for stock in stocks:
        try:
            df = yf.download(stock, period="5d", interval="1d")
            if df.empty:
                send_message(CHAT_ID, f"⚠️ 无法获取 {stock} 数据")
                continue

            df["MA5"] = df["Close"].rolling(5).mean()
            df["MA20"] = df["Close"].rolling(20).mean()
            latest = df.iloc[-1]
            open_price = float(latest["Open"])
            close_price = float(latest["Close"])
            change = close_price - open_price
            pct = (change / open_price) * 100 if open_price != 0 else 0.0

            if change > 0:
                trend = "📈 上涨"
            elif change < 0:
                trend = "📉 下跌"
            else:
                trend = "➖ 无涨跌"

            # 生成图表
            hist = yf.download(stock, period="60d", interval="1d")
            hist["MA5"] = hist["Close"].rolling(5).mean()
            hist["MA20"] = hist["Close"].rolling(20).mean()
            plt.figure(figsize=(12, 6))
            plt.plot(hist["Close"], label="收盘价", color="black")
            plt.plot(hist["MA5"], label="5日均线", color="blue")
            plt.plot(hist["MA20"], label="20日均线", color="red")
            plt.title(f"{stock} - 60日走势图")
            plt.xlabel("日期")
            plt.ylabel("价格")
            plt.legend()
            plt.grid(True)
            chart_path = f"charts/{stock.replace('.KL', '')}.png"
            plt.savefig(chart_path)
            plt.close()

            caption = (
                f"📊 {stock} 股票走势\n"
                f"开市：RM {open_price:.3f}\n"
                f"收市：RM {close_price:.3f}\n"
                f"涨跌：{trend} RM {change:.3f}（{pct:.2f}%）"
            )
            send_photo(CHAT_ID, chart_path, caption)
        except Exception as e:
            send_message(CHAT_ID, f"❌ 生成 {stock} 图表失败：{str(e)}")
            traceback.print_exc()

# === Web 接口 ===
@app.route("/", methods=["GET"])
def home():
    return "✅ MyStock Bot 正常运行"

@app.route("/run", methods=["GET"])
def manual_run():
    threading.Thread(target=generate_stock_report).start()
    return "📊 正在生成股票报告..."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 收到消息：", data)
        msg = data.get("message") or data.get("edited_message")
        if not msg:
            return "No message"

        text = msg.get("text", "").lower()
        chat_id = msg["chat"]["id"]

        if "报告" in text or "stock" in text:
            send_message(chat_id, "📊 正在生成股票报告，请稍候...")
            threading.Thread(target=generate_stock_report).start()
        else:
            send_message(chat_id, f"🤖 你说的是：{text}")

        return "OK"
    except Exception as e:
        print("❌ Webhook 出错：", str(e))
        traceback.print_exc()
        return "ERROR", 500

# === 启动应用 ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
