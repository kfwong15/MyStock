import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import pandas_ta as ta
import requests
import os
import json

# Telegram Bot 配置（优先读取环境变量，fallback 到 config.json）
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

if not TG_BOT_TOKEN or not TG_CHAT_ID:
    with open("config.json", "r") as f:
        config = json.load(f)
        TG_BOT_TOKEN = config["bot_token"]
        TG_CHAT_ID = str(config["chat_id"])

# 发送图片到 Telegram
def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        response = requests.post(url, data={"chat_id": TG_CHAT_ID, "caption": caption}, files={"photo": photo})
    if response.ok:
        print(f"✅ 已发送：{photo_path}")
    else:
        print(f"❌ 发送失败：{response.text}")

# 自选股列表
my_stocks = ["5255.KL", "0209.KL"]

# 创建图表目录
os.makedirs("charts", exist_ok=True)

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    df = yf.download(stock, period="60d", interval="1d", auto_adjust=True)

    if df.empty or len(df) < 30:
        print(f"⚠️ 数据不足或无法获取 {stock}")
        continue

    # 添加均线、MACD、RSI
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()

    macd_df = ta.macd(df["Close"])
    if macd_df is not None:
        df["MACD"] = macd_df["MACD_12_26_9"]
        df["MACD_signal"] = macd_df["MACDs_12_26_9"]
        df["MACD_hist"] = macd_df["MACDh_12_26_9"]
    else:
        df["MACD"] = df["MACD_signal"] = df["MACD_hist"] = 0.0

    df["RSI"] = ta.rsi(df["Close"], length=14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    open_price = round(float(latest["Open"]), 3)
    close_price = round(float(latest["Close"]), 3)
    change = close_price - open_price
    pct_change = round((change / open_price) * 100, 2) if open_price != 0 else 0

    # 涨跌趋势判断
    if change > 0:
        trend_icon = "📈 上涨"
        reason = "可能受到市场乐观或业绩预期带动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或负面情绪影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # 趋势提醒
    trend_advice = []
    if close_price > latest["MA20"]:
        trend_advice.append("⚠️ 股价上穿 MA20，短期偏强。")
    if latest["MA5"] > latest["MA20"] and prev["MA5"] < prev["MA20"]:
        trend_advice.append("⚠️ 出现 MA5 金叉 MA20，短线机会。")
    if latest["MA5"] < latest["MA20"] and prev["MA5"] > prev["MA20"]:
        trend_advice.append("⚠️ 出现 MA5 死叉 MA20，可能回调。")
    if latest["RSI"] < 30:
        trend_advice.append("🧪 RSI < 30，超卖区，可能反弹。")
    elif latest["RSI"] > 70:
        trend_advice.append("🧪 RSI > 70，超买区，注意回调。")
    if latest["MACD"] > latest["MACD_signal"] and prev["MACD"] < prev["MACD_signal"]:
        trend_advice.append("📊 MACD 金叉，可能开始上涨。")
    elif latest["MACD"] < latest["MACD_signal"] and prev["MACD"] > prev["MACD_signal"]:
        trend_advice.append("📊 MACD 死叉，可能开始下跌。")

    # 获取新闻
    try:
        news_items = yf.Ticker(stock).news[:3]
        if news_items:
            news_text = "\n📰 今日新闻："
            for n in news_items:
                news_text += f"\n• [{n['publisher']}] {n['title']}"
        else:
            news_text = "\n📰 今日新闻：暂无新闻"
    except:
        news_text = "\n📰 今日新闻：获取失败"

    # 汇总报告文字
    caption = (
        f"📊 {stock} 股票走势报告\n"
        f"开市价：RM {open_price}\n"
        f"收市价：RM {close_price}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n"
        f"说明：{reason}\n"
        + "\n".join(trend_advice) + "\n"
        + news_text
    )

    # 绘图
    plt.figure(figsize=(12, 6))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue", linestyle="--")
    plt.plot(df["MA20"], label="MA20", color="red", linestyle="--")
    plt.title(f"{stock} - 收盘价与均线走势")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    chart_path = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(chart_path)
    plt.close()

    print(f"✅ 图表已生成：{chart_path}")
    send_telegram_photo(chart_path, caption)
