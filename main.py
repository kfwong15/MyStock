import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import json
import os

# 读取 Telegram 配置
with open("config.json", "r") as f:
    config = json.load(f)
bot_token = config["bot_token"]
chat_id = config["chat_id"]

# Telegram 发图函数
def send_telegram_photo(bot_token, chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": chat_id, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送到 Telegram：{photo_path}")
        else:
            print(f"❌ 发送失败：{response.text}")

# 创建图表目录
os.makedirs("charts", exist_ok=True)

# 自选股列表
my_stocks = ["5255.KL", "0209.KL"]

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    # 下载近5天数据，用于分析最新行情
    df = yf.download(stock, period="5d", interval="1d")

    if df.empty:
        print(f"⚠️ 没有抓到 {stock} 的数据")
        continue

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    latest = df.iloc[-1]  # 最新一天
    open_price = latest["Open"]
    close_price = latest["Close"]
    change = close_price - open_price
    pct_change = (change / open_price) * 100

    if change > 0:
        trend_icon = "📈 上涨"
        reason = "可能受到市场乐观或业绩预期带动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或负面情绪影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    caption = (
        f"📊 {stock} 股票走势汇报\n"
        f"开市价：RM {open_price:.2f}\n"
        f"收市价：RM {close_price:.2f}\n"
        f"涨跌：{trend_icon} RM {change:.2f}（{pct_change:.2f}%）\n"
        f"说明：{reason}"
    )

    # 下载 60 天数据绘图
    hist_df = yf.download(stock, period="60d", interval="1d")
    hist_df['MA5'] = hist_df['Close'].rolling(window=5).mean()
    hist_df['MA20'] = hist_df['Close'].rolling(window=20).mean()

    # 绘图
    plt.figure(figsize=(12, 6))
    plt.plot(hist_df['Close'], label='收盘价', color='black')
    plt.plot(hist_df['MA5'], label='5日均线', color='blue')
    plt.plot(hist_df['MA20'], label='20日均线', color='red')
    plt.title(f"{stock} - 近60日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    # 保存图像
    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ 图表已生成：{filename}")

    # 推送到 Telegram（附说明）
    send_telegram_photo(bot_token, chat_id, filename, caption=caption)
