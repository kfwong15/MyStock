import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import pandas_ta as ta
import requests
import os
import json

# 读取 Telegram 配置（从环境变量或 config.json）
bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")

if not bot_token or not chat_id:
    # 本地开发用 config.json
    with open("config.json", "r") as f:
        config = json.load(f)
        bot_token = config["bot_token"]
        chat_id = config["chat_id"]

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

    # 下载近60日数据
    df = yf.download(stock, period="60d", interval="1d", auto_adjust=False)

    if df.empty:
        print(f"⚠️ 未获取到 {stock} 的数据")
        continue

    # 添加技术指标：MA、RSI、MACD
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["RSI"] = ta.rsi(df["Close"], length=14)
    macd_df = ta.macd(df["Close"])
    df["MACD"] = macd_df["MACD_12_26_9"]
    df["MACD_SIGNAL"] = macd_df["MACDs_12_26_9"]

    latest = df.iloc[-1]
    open_price = float(latest["Open"])
    close_price = float(latest["Close"])
    change = close_price - open_price
    pct_change = (change / open_price) * 100 if open_price != 0 else 0

    if change > 0:
        trend_icon = "📈 上涨"
        reason = "可能受到市场乐观或业绩预期带动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或负面情绪影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # 获取昨日 MA
    yesterday = df.iloc[-2] if len(df) >= 2 else latest
    ma5_today = float(latest["MA5"]) if pd.notna(latest["MA5"]) else 0.0
    ma20_today = float(latest["MA20"]) if pd.notna(latest["MA20"]) else 0.0
    ma5_yest = float(yesterday["MA5"]) if pd.notna(yesterday["MA5"]) else 0.0
    ma20_yest = float(yesterday["MA20"]) if pd.notna(yesterday["MA20"]) else 0.0

    # 趋势提醒判断
    trend_advice = ""
    if close_price > ma20_today:
        trend_advice += "⚠️ 明日关注：股价上穿 MA20，短期或有动能。\n"
    if ma5_today > ma20_today and ma5_yest < ma20_yest:
        trend_advice += "📊 出现 MA5 金叉 MA20，或为短线买入信号。\n"
    if ma5_today < ma20_today and ma5_yest > ma20_yest:
        trend_advice += "⚠️ 出现 MA5 死叉 MA20，注意回调风险。\n"

    # RSI/MACD 判断
    rsi = float(latest["RSI"]) if pd.notna(latest["RSI"]) else 0.0
    macd = float(latest["MACD"]) if pd.notna(latest["MACD"]) else 0.0
    macd_signal = float(latest["MACD_SIGNAL"]) if pd.notna(latest["MACD_SIGNAL"]) else 0.0

    if rsi < 30:
        trend_advice += "📉 RSI < 30：超卖，或有反弹机会。\n"
    elif rsi > 70:
        trend_advice += "📈 RSI > 70：超买，或将调整。\n"

    if macd > macd_signal:
        trend_advice += "📈 MACD 金叉，或为上涨信号。\n"
    elif macd < macd_signal:
        trend_advice += "📉 MACD 死叉，或为下跌信号。\n"

    # 获取新闻
    try:
        news = yf.Ticker(stock).news[:3]
        if news:
            news_text = "\n📰 今日相关新闻："
            for item in news:
                news_text += f"\n• [{item.get('publisher')}] {item.get('title')}"
        else:
            news_text = "\n📰 今日相关新闻：暂无新闻。"
    except:
        news_text = "\n📰 今日相关新闻：获取失败。"

    # 文字说明
    caption = (
        f"📊 {stock} 股票走势汇报\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n"
        f"说明：{reason}\n"
        f"{trend_advice}"
        f"{news_text}"
    )

    # 绘图
    plt.figure(figsize=(12, 6))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{stock} - 近60日走势图")
    plt.xlabel("日期")
    plt.ylabel("RM")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ 图表已生成：{filename}")
    send_telegram_photo(bot_token, chat_id, filename, caption=caption)
