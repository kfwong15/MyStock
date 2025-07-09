import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import os
import datetime

# 设置 Telegram 机器人
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN") or "你的TG_BOT_TOKEN"
TG_CHAT_ID = os.getenv("TG_CHAT_ID") or "你的TG_CHAT_ID"

# 你的股票列表
STOCK_LIST = ["5255.KL", "0209.KL"]

# 创建图表目录
os.makedirs("charts", exist_ok=True)

def send_telegram_message(text, image_path=None):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    # 发送文本消息
    r = requests.post(url, data=payload)
    print("✅ 已发送消息：", r.text)

    # 发送图表（如有）
    if image_path and os.path.exists(image_path):
        url_photo = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {"chat_id": TG_CHAT_ID}
            r = requests.post(url_photo, data=data, files=files)
            print("✅ 已发送图表：", r.text)


def analyze_stock(stock_code):
    print(f"📈 抓取 {stock_code} 的数据...")
    df = yf.download(stock_code, period="7d", interval="1d")
    if df.empty:
        print("❌ 数据为空")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    open_price = float(latest.get("Open", 0.0)) if pd.notna(latest.get("Open", 0.0)) else 0.0
    close_price = float(latest.get("Close", 0.0)) if pd.notna(latest.get("Close", 0.0)) else 0.0
    change = close_price - open_price
    pct = (change / open_price * 100) if open_price != 0 else 0

    symbol = "📈 涨" if change > 0 else "📉 跌" if change < 0 else "➖ 无涨跌"
    reason = "今日股价上涨，可能受到正面消息或市场信心提振。" if change > 0 else \
             "今日股价下跌，或因市场情绪不稳或负面消息影响。" if change < 0 else \
             "今日股价稳定，缺乏波动。"

    # 图表保存
    filename = f"charts/{stock_code.split('.')[0]}_chart.png"
    df["Close"].plot(title=f"{stock_code} 收盘价走势", figsize=(10, 4))
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"✅ 图表已生成：{filename}")

    # 消息内容
    message = (
        f"<b>📊 {stock_code} 股票走势汇报</b>\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{symbol} RM {abs(change):.3f}（{pct:.2f}%）\n"
        f"说明：{reason}"
    )

    # 发送 Telegram
    send_telegram_message(message, image_path=filename)

# 主程序
if __name__ == "__main__":
    for s in STOCK_LIST:
        analyze_stock(s)
