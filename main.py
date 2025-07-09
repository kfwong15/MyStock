import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import os
from datetime import datetime, timedelta, date

# === 安全读取环境变量 ===
bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")

# === Telegram 发送图片函数 ===
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

# 判断是否今天有交易数据
def is_trading_day(df):
    today_str = date.today().strftime('%Y-%m-%d')
    return today_str in df.index.strftime('%Y-%m-%d')

# 创建图表文件夹
os.makedirs("charts", exist_ok=True)

# 自选股票列表
my_stocks = ["5255.KL", "0209.KL"]

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")

    # 获取近 5 日用于分析
    df = yf.download(stock, period="5d", interval="1d", auto_adjust=False)

    # 检查是否为交易日
    if not is_trading_day(df):
        print(f"📭 今天 ({date.today()}) 没有 {stock} 的交易数据，跳过发送。")
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
        reason = "可能受到市场乐观或利好消息推动。"
    elif change < 0:
        trend_icon = "📉 下跌"
        reason = "可能受到市场回调或不利消息影响。"
    else:
        trend_icon = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # MA 数据准备
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_MA5 = float(yesterday["MA5"]) if not pd.isna(yesterday["MA5"]) else 0.0
        yesterday_MA20 = float(yesterday["MA20"]) if not pd.isna(yesterday["MA20"]) else 0.0
    else:
        yesterday_MA5 = yesterday_MA20 = 0.0

    today_MA5 = float(latest["MA5"]) if not pd.isna(latest["MA5"]) else 0.0
    today_MA20 = float(latest["MA20"]) if not pd.isna(latest["MA20"]) else 0.0

    # 趋势判断
    trend_advice = ""
    if close_price > today_MA20:
        trend_advice = "⚠️ 股价上穿 MA20，有上升动能。"
    elif today_MA5 > today_MA20 and yesterday_MA5 < yesterday_MA20:
        trend_advice = "⚠️ MA5 金叉 MA20，或有短线机会。"
    elif today_MA5 < today_MA20 and yesterday_MA5 > yesterday_MA20:
        trend_advice = "⚠️ MA5 死叉 MA20，注意风险。"

    # 新闻整合
    try:
        ticker = yf.Ticker(stock)
        all_news = ticker.news
        news_text = "\n📰 相关新闻："
        news_found = False

        for news in all_news:
            pub_date = datetime.fromtimestamp(news.get("providerPublishTime", 0))
            if datetime.now() - pub_date <= timedelta(days=7):
                title = news.get("title", "无标题")
                source = news.get("publisher", "来源未知")
                news_text += f"\n• [{source}] {title}"
                news_found = True

        if not news_found and all_news:
            latest_news = all_news[0]
            title = latest_news.get("title", "无标题")
            source = latest_news.get("publisher", "来源未知")
            pub_date = datetime.fromtimestamp(latest_news.get("providerPublishTime", 0)).strftime('%Y-%m-%d')
            news_text += f"\n• [最靠近的旧新闻] {title}（{source}，{pub_date}）"
        elif not all_news:
            news_text += "\n• 暂无相关新闻。"

    except Exception:
        news_text = "\n📰 新闻获取失败。"

    # 汇总文字信息
    caption = (
        f"📊 {stock} 股票走势汇报\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n"
        f"说明：{reason}\n"
        f"{trend_advice}"
        f"{news_text}"
    )

    # 图表绘制（60天）
    hist_df = yf.download(stock, period="60d", interval="1d", auto_adjust=False)
    hist_df['MA5'] = hist_df['Close'].rolling(window=5).mean()
    hist_df['MA20'] = hist_df['Close'].rolling(window=20).mean()

    plt.figure(figsize=(12, 6))
    plt.plot(hist_df['Close'], label='收盘价', color='black')
    plt.plot(hist_df['MA5'], label='MA5', color='blue')
    plt.plot(hist_df['MA20'], label='MA20', color='red')
    plt.title(f"{stock} - 近60日走势")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()

    print(f"✅ 图表已生成：{filename}")
    send_telegram_photo(bot_token, chat_id, filename, caption=caption)
