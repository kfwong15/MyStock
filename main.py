import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import json
import os
import talib

# 支持中文显示（防止 matplotlib 中文乱码）
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']  # 兼容 GitHub Actions 环境

# 读取 Telegram 配置
bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")

# 发送图片到 Telegram
def send_telegram_photo(bot_token, chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": chat_id, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送：{photo_path}")
        else:
            print(f"❌ 发送失败：{response.text}")

# 创建图表目录
os.makedirs("charts", exist_ok=True)

# 自选股列表
my_stocks = ["5255.KL", "0209.KL"]

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    df = yf.download(stock, period="60d", interval="1d", auto_adjust=False)
    if df.empty:
        print(f"⚠️ 无法获取 {stock} 数据")
        continue

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['RSI'] = talib.RSI(df['Close'], timeperiod=14)
    macd, macdsignal, macdhist = talib.MACD(df['Close'], fastperiod=12, slowperiod=26, signalperiod=9)
    df['MACD'] = macd
    df['MACD_SIGNAL'] = macdsignal

    latest = df.iloc[-1]
    open_price = round(float(latest["Open"]), 3)
    close_price = round(float(latest["Close"]), 3)
    change = close_price - open_price
    pct_change = (change / open_price) * 100 if open_price != 0 else 0

    # 涨跌说明
    if change > 0:
        trend_icon = "📈 上涨"
        reason = "市场乐观或业绩利好"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "市场调整或利空消息"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "股价稳定波动较小"

    # 技术指标判断
    trend_advice = ""
    rsi = latest["RSI"]
    macd_val = latest["MACD"]
    macd_signal = latest["MACD_SIGNAL"]

    if rsi < 30:
        trend_advice += "\n🔎 RSI 进入超卖区，可能有反弹机会"
    elif rsi > 70:
        trend_advice += "\n⚠️ RSI 进入超买区，可能有回调风险"

    if macd_val > macd_signal:
        trend_advice += "\n📊 MACD 金叉信号，可能进入上升趋势"
    elif macd_val < macd_signal:
        trend_advice += "\n📉 MACD 死叉信号，可能进入下降趋势"

    # 获取新闻
    try:
        ticker = yf.Ticker(stock)
        news_items = ticker.news[:3]
        if news_items:
            news_text = "\n📰 今日新闻："
            for news in news_items:
                title = news.get("title", "无标题")
                source = news.get("publisher", "来源未知")
                news_text += f"\n• [{source}] {title}"
        else:
            news_text = "\n📰 今日新闻：暂无新闻"
    except:
        news_text = "\n📰 今日新闻：获取失败"

    # 总结报告
    caption = (
        f"📊 {stock} 股票走势报告\n"
        f"开盘价：RM {open_price:.3f}\n"
        f"收盘价：RM {close_price:.3f}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n"
        f"说明：{reason}"
        f"{trend_advice}"
        f"{news_text}"
    )

    # 画图
    plt.figure(figsize=(12, 6))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{stock} - 近60日走势图（含MA、RSI、MACD）")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    chart_path = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(chart_path)
    plt.close()

    print(f"✅ 图表已生成：{chart_path}")
    send_telegram_photo(bot_token, chat_id, chart_path, caption)
