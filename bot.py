import os
import threading
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
from flask import Flask, request

# Flask App 初始化
app = Flask(__name__)

# 从环境变量读取 Token 和 Chat ID（Render / GitHub Actions 使用更安全）
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# ========================== Telegram 发图 ==========================
def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": TG_CHAT_ID, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送：{photo_path}")
        else:
            print(f"❌ 图片发送失败：{response.text}")

# ========================== Telegram 文字回复 ==========================
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

# ========================== 股票图表生成与分析 ==========================
def generate_stock_report(stock_code):
    print(f"📊 抓取 {stock_code} 的数据...")
    df = yf.download(stock_code, period="5d", interval="1d", auto_adjust=False)
    if df.empty:
        print(f"⚠️ 无数据：{stock_code}")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    latest = df.iloc[[-1]]

    try:
        open_price = float(latest["Open"].iloc[0])
        close_price = float(latest["Close"].iloc[0])
    except:
        open_price = close_price = 0.0

    change = close_price - open_price
    pct_change = (change / open_price) * 100 if open_price != 0 else 0

    if change > 0:
        trend_icon = "📈 上涨"
        reason = "市场乐观或利好消息。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "市场回调或情绪偏空。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "股价稳定，无波动。"

    # MA判断
    if len(df) >= 2:
        yesterday = df.iloc[[-2]]
        yesterday_MA5 = float(yesterday["MA5"].iloc[0]) if pd.notna(yesterday["MA5"].iloc[0]) else 0
        yesterday_MA20 = float(yesterday["MA20"].iloc[0]) if pd.notna(yesterday["MA20"].iloc[0]) else 0
    else:
        yesterday_MA5 = yesterday_MA20 = 0

    today_MA5 = float(latest["MA5"].iloc[0]) if pd.notna(latest["MA5"].iloc[0]) else 0
    today_MA20 = float(latest["MA20"].iloc[0]) if pd.notna(latest["MA20"].iloc[0]) else 0

    trend_advice = ""
    if close_price > today_MA20:
        trend_advice = "⚠️ 明日关注：股价已上穿 MA20，有动能。"
    elif today_MA5 > today_MA20 and yesterday_MA5 < yesterday_MA20:
        trend_advice = "⚠️ 金叉信号：MA5 上穿 MA20。"
    elif today_MA5 < today_MA20 and yesterday_MA5 > yesterday_MA20:
        trend_advice = "⚠️ 死叉信号：MA5 下穿 MA20。"

    # 新闻
    try:
        ticker = yf.Ticker(stock_code)
        news_items = ticker.news[:3]
        if news_items:
            news_text = "\n📰 新闻："
            for news in news_items:
                title = news.get("title", "无标题")
                source = news.get("publisher", "来源未知")
                news_text += f"\n• [{source}] {title}"
        else:
            news_text = "\n📰 暂无相关新闻"
    except:
        news_text = "\n📰 新闻获取失败"

    caption = (
        f"📊 {stock_code} 股票汇报\n"
        f"开市价：RM {open_price:.2f}\n"
        f"收市价：RM {close_price:.2f}\n"
        f"涨跌：{trend_icon} RM {change:.2f}（{pct_change:.2f}%）\n"
        f"{reason}\n"
        f"{trend_advice}"
        f"{news_text}"
    )

    # 画图
    hist_df = yf.download(stock_code, period="60d", interval="1d", auto_adjust=False)
    hist_df["MA5"] = hist_df["Close"].rolling(window=5).mean()
    hist_df["MA20"] = hist_df["Close"].rolling(window=20).mean()

    os.makedirs("charts", exist_ok=True)
    filename = f"charts/{stock_code.replace('.KL', '')}.png"
    plt.figure(figsize=(10, 5))
    plt.plot(hist_df["Close"], label="收盘", color="black")
    plt.plot(hist_df["MA5"], label="MA5", color="blue")
    plt.plot(hist_df["MA20"], label="MA20", color="red")
    plt.title(f"{stock_code} - 60日走势图")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    send_telegram_photo(filename, caption)

# ========================== 多股票执行 ==========================
def run_all():
    stock_list = ["5255.KL", "0209.KL"]
    for code in stock_list:
        generate_stock_report(code)

# ========================== Flask 路由 ==========================
@app.route("/")
def index():
    return "✅ MyStock Bot 正在运行"

@app.route("/run")
def run_now():
    threading.Thread(target=run_all).start()
    return "📈 股票分析开始执行"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 收到消息：", data)
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "").lower()
            if "stock" in text or "报告" in text:
                send_message(chat_id, "📊 正在生成股票报告...")
                threading.Thread(target=run_all).start()
            else:
                send_message(chat_id, f"✅ 你发送了：{text}")
        return "OK"
    except Exception as e:
        print("❌ Webhook 错误：", e)
        return "Internal Server Error", 500

# ========================== 启动 Flask 应用 ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
