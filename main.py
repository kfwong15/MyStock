import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

# 读取 Telegram 配置
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

# 创建图表文件夹
os.makedirs("charts", exist_ok=True)

# 自选股票列表
my_stocks = ["5255.KL", "0209.KL"]

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    # 抓近5日用于分析
    df = yf.download(stock, period="5d", interval="1d", auto_adjust=False)

    if df.empty:
        print(f"⚠️ 未获取到 {stock} 数据")
        continue

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    latest = df.iloc[-1]

    open_price = float(latest["Open"])
    close_price = float(latest["Close"])
    change = close_price - open_price
    pct_change = (change / open_price) * 100

    # 涨跌说明
    if change > 0:
        trend_icon = "📈 上涨"
        reason = "可能受到市场乐观或业绩预期带动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或负面情绪影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # 获取昨日 MA 数据（安全转换）
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        try:
            yesterday_MA5 = float(yesterday["MA5"])
        except:
            yesterday_MA5 = 0.0
        try:
            yesterday_MA20 = float(yesterday["MA20"])
        except:
            yesterday_MA20 = 0.0
    else:
        yesterday_MA5 = yesterday_MA20 = 0.0

    # 获取今日 MA 数据（安全转换）
    try:
        today_MA5 = float(latest["MA5"])
    except:
        today_MA5 = 0.0
    try:
        today_MA20 = float(latest["MA20"])
    except:
        today_MA20 = 0.0

    # 趋势提醒
    trend_advice = ""
    if close_price > today_MA20:
        trend_advice = "⚠️ 明日关注：当前股价已上穿 MA20，有短期上升动能。"
    elif today_MA5 > today_MA20 and yesterday_MA5 < yesterday_MA20:
        trend_advice = "⚠️ 明日关注：出现 MA5 金叉 MA20，或有短线机会。"
    elif today_MA5 < today_MA20 and yesterday_MA5 > yesterday_MA20:
        trend_advice = "⚠️ 注意：出现 MA5 死叉 MA20，或有短期回调压力。"

    # 新闻整合逻辑（近7天 + 最近一次旧新闻）
    try:
        ticker = yf.Ticker(stock)
        all_news = ticker.news
        news_text = "\n📰 相关新闻："
        news_found = False

        for news in all_news:
            try:
                pub_date = datetime.fromtimestamp(news.get("providerPublishTime", 0))
            except:
                continue
            if datetime.now() - pub_date <= timedelta(days=7):
                title = news.get("title", "无标题")
                source = news.get("publisher", "来源未知")
                news_text += f"\n• [{source}] {title}"
                news_found = True

        # 如果 7 天内没有新闻，显示最近一条旧新闻
        if not news_found and all_news:
            latest_news = all_news[0]
            title = latest_news.get("title", "无标题")
            source = latest_news.get("publisher", "来源未知")
            pub_date = datetime.fromtimestamp(latest_news.get("providerPublishTime", 0)).strftime('%Y-%m-%d')
            news_text += f"\n• [最靠近的旧新闻] {title}（{source}，{pub_date}）"
        elif not all_news:
            news_text += "\n• 暂无相关新闻。"

    except Exception as e:
        news_text = "\n📰 新闻获取失败。"

    # 整体信息文字
    caption = (
        f"📊 {stock} 股票走势汇报\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n"
        f"说明：{reason}\n"
        f"{trend_advice}"
        f"{news_text}"
    )

    # 获取图表数据（60 天）
    hist_df = yf.download(stock, period="60d", interval="1d", auto_adjust=False)
    hist_df['MA5'] = hist_df['Close'].rolling(window=5).mean()
    hist_df['MA20'] = hist_df['Close'].rolling(window=20).mean()

    # 画图
    plt.figure(figsize=(12, 6))
    plt.plot(hist_df['Close'], label='收盘价', color='black')
    plt.plot(hist_df['MA5'], label='5日均线', color='blue')
    plt.plot(hist_df['MA20'], label='20日均线', color='red')
    plt.title(f"{stock} - 近60日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ 图表已生成：{filename}")
    send_telegram_photo(bot_token, chat_id, filename, caption=caption)
