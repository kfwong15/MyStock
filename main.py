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

# 主程序
for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    df = yf.download(stock, period="60d", interval="1d")

    if df.empty:
        print(f"⚠️ 没有抓到 {stock} 的数据")
        continue

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    # 画图
    plt.figure(figsize=(12, 6))
    plt.plot(df['Close'], label='收盘价', color='black')
    plt.plot(df['MA5'], label='5日均线', color='blue')
    plt.plot(df['MA20'], label='20日均线', color='red')
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

    # 推送 Telegram
    send_telegram_photo(bot_token, chat_id, filename, caption=f"{stock} 股票走势图")
