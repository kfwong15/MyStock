import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import os

# ✅ 从 GitHub 环境变量读取配置（更安全）
bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")

# 发送图片到 Telegram
def send_telegram_photo(photo_path, caption=""):
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
my_stocks = ["5255.KL", "0209.KL", "1562.KL"]

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    df = yf.download(stock, period="5d", interval="1d", auto_adjust=False)
    if df.empty:
        print(f"⚠️ 未获取到 {stock} 的数据")
        continue

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    latest = df.iloc[[-1]]  # 保证仍是 DataFrame

    try:
        open_price = float(latest["Open"].iloc[0])
        close_price = float(latest["Close"].iloc[0])
    except:
        open_price = close_price = 0.0

    change = close_price - open_price
    pct_change = (change / open_price) * 100 if open_price else 0.0

    # 涨跌趋势分析
    if change > 0:
        trend_icon = "📈 上涨"
        reason = "可能受到市场乐观或业绩预期带动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或负面情绪影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # 获取昨日 MA 数据
    if len(df) >= 2:
        yesterday = df.iloc[[-2]]
        yesterday_MA5 = float(yesterday["MA5"].iloc[0]) if pd.notna(yesterday["MA5"].iloc[0]) else 0.0
        yesterday_MA20 = float(yesterday["MA20"].iloc[0]) if pd.notna(yesterday["MA20"].iloc[0]) else 0.0
    else:
        yesterday_MA5 = yesterday_MA20 = 0.0

    # 今日 MA
    today_MA5 = float(latest["MA5"].iloc[0]) if pd.notna(latest["MA5"].iloc[0]) else 0.0
    today_MA20 = float(latest["MA20"].iloc[0]) if pd.notna(latest["MA20"].iloc[0]) else 0.0

    # 趋势建议
    trend_advice = ""
    if close_price > today_MA20:
        trend_advice = "⚠️ 明日关注：当前股价已上穿 MA20，有短期上升动能。"
    elif today_MA5 > today_MA20 and yesterday_MA5 < yesterday_MA20:
        trend_advice = "⚠️ 明日关注：出现 MA5 金叉 MA20，或有短线机会。"
    elif today_MA5 < today_MA20 and yesterday_MA5 > yesterday_MA20:
        trend_advice = "⚠️ 注意：出现 MA5 死叉 MA20，或有短期回调压力。"

    # 新闻
    try:
        ticker = yf.Ticker(stock)
        news_items = ticker.news[:3]
        if news_items:
            news_text = "\n📰 今日相关新闻："
            for news in news_items:
                title = news.get("title", "无标题")
                source = news.get("publisher", "来源未知")
                news_text += f"\n• [{source}] {title}"
        else:
            news_text = "\n📰 今日相关新闻：暂无相关新闻。"
    except:
        news_text = "\n📰 今日相关新闻：获取失败。"

    # 总结
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
    hist_df = yf.download(stock, period="60d", interval="1d", auto_adjust=False)
    hist_df["MA5"] = hist_df["Close"].rolling(window=5).mean()
    hist_df["MA20"] = hist_df["Close"].rolling(window=20).mean()

    plt.figure(figsize=(12, 6))
    plt.plot(hist_df["Close"], label="收盘价", color="black")
    plt.plot(hist_df["MA5"], label="5日均线", color="blue")
    plt.plot(hist_df["MA20"], label="20日均线", color="red")
    plt.title(f"{stock} - 近60日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ 图表已生成：{filename}")
    send_telegram_photo(filename, caption)
