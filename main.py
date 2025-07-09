import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import datetime
import os
import requests
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']  # 支持中文

# 设置 Telegram Token 与 Chat ID（别公开上传，建议用环境变量处理）
TG_BOT_TOKEN = "你的_BOT_TOKEN"
TG_CHAT_ID = "你的_CHAT_ID"  # 5738853645 私人频道 ID

# 股票列表
stock_list = ["5255.KL", "0209.KL"]

# 创建图表目录
if not os.path.exists("charts"):
    os.makedirs("charts")

def get_news(stock_code):
    # 📰 可替换为真实新闻 API，当前用占位文本
    return "（今日暂无相关新闻）"

def analyze_stock(stock):
    print(f"📈 抓取 {stock} 的数据...")

    df = yf.download(stock, period="7d", interval="1d")
    if df.empty or len(df) < 2:
        print(f"⚠️ 无足够数据：{stock}")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    latest = df.iloc[-1]
    previous = df.iloc[-2]

    # 安全提取数据
    open_price = float(latest["Open"]) if pd.notna(latest["Open"]) else 0.0
    close_price = float(latest["Close"]) if pd.notna(latest["Close"]) else 0.0
    prev_close = float(previous["Close"]) if pd.notna(previous["Close"]) else 0.0

    change = close_price - open_price
    percent = (change / open_price) * 100 if open_price != 0 else 0

    # 图表生成
    plt.figure(figsize=(10, 4))
    df["Close"].plot(title=f"{stock} 近期走势")
    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()
    print(f"✅ 图表已生成：{filename}")

    # 说明文字
    if change > 0:
        status = f"📈 上涨 RM {change:.3f}（{percent:.2f}%）"
        reason = "说明：今日市场表现积极，股价上涨。"
    elif change < 0:
        status = f"📉 下跌 RM {abs(change):.3f}（{percent:.2f}%）"
        reason = "说明：今日股价承压，略有下滑。"
    else:
        status = f"➖ 无涨跌 RM {change:.3f}（{percent:.2f}%）"
        reason = "说明：今日股价稳定，缺乏波动。"

    # 获取新闻
    news = get_news(stock)

    # 推送信息
    message = (
        f"📊 {stock} 股票走势汇报\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{status}\n"
        f"{reason}\n\n"
        f"📰 今日相关新闻：\n{news}"
    )
    send_to_telegram(message, filename)

def send_to_telegram(text, chart_path=None):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    image_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"

    # 文本消息
    payload = {"chat_id": TG_CHAT_ID, "text": text}
    res = requests.post(url, json=payload)
    if not res.ok:
        print(f"❌ 文本发送失败：{res.text}")

    # 图片发送
    if chart_path and os.path.exists(chart_path):
        with open(chart_path, "rb") as img:
            files = {"photo": img}
            data = {"chat_id": TG_CHAT_ID}
            res = requests.post(image_url, data=data, files=files)
            if not res.ok:
                print(f"❌ 图片发送失败：{res.text}")

if __name__ == "__main__":
    for s in stock_list:
        analyze_stock(s)
