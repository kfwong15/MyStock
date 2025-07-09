import os
import datetime
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
import requests

# 设置中文字体避免警告
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 读取 Telegram 配置（通过 GitHub Secrets 设置）
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# 股票列表（你可以继续增加）
stock_list = ["5255.KL", "0209.KL"]

# 设置图表保存目录
os.makedirs("charts", exist_ok=True)

# 获取今天日期
today = datetime.date.today().strftime("%Y-%m-%d")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data)
    return response.json()

def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": TG_CHAT_ID, "caption": caption}
        response = requests.post(url, files=files, data=data)
    return response.json()

def fetch_news_placeholder(stock_code):
    # 你可以改成真实爬虫或 API 采集
    return f"暂无重要新闻。"

def analyze_stock(stock):
    print(f"📈 抓取 {stock} 的数据...")
    df = yf.download(stock, period="10d", interval="1d", auto_adjust=False)

    if df.empty or len(df) < 2:
        print(f"❌ 无法获取 {stock} 的有效数据")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    latest = df.iloc[-1]
    yesterday = df.iloc[-2]

    # 使用 .iloc[0] 避免 FutureWarning
    open_price = round(float(latest["Open"]), 3)
    close_price = round(float(latest["Close"]), 3)

    change = close_price - open_price
    percent_change = round(change / open_price * 100, 2)

    if change > 0:
        arrow = "📈 上涨"
        reason = "今日股价上涨，投资者积极进场。"
    elif change < 0:
        arrow = "📉 下跌"
        reason = "今日股价下跌，可能受市场情绪影响。"
    else:
        arrow = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    ma5_today = latest["MA5"]
    ma5_yesterday = yesterday["MA5"]
    trend_note = ""
    if not pd.isna(ma5_today) and not pd.isna(ma5_yesterday):
        if ma5_today > ma5_yesterday:
            trend_note = "5日均线走高，短期上升趋势。"
        elif ma5_today < ma5_yesterday:
            trend_note = "5日均线下滑，短期承压。"

    # 新闻摘要（你可以替换成真实 API 或爬虫）
    news_text = fetch_news_placeholder(stock)

    # 输出分析文本
    message = (
        f"📊 *{stock} 股票走势汇报*\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{arrow} RM {abs(change):.3f}（{abs(percent_change):.2f}%）\n"
        f"说明：{reason}\n"
        f"{trend_note}\n\n"
        f"📰 今日相关新闻：\n{news_text}"
    )

    send_telegram_message(message)

    # 绘图
    plt.figure(figsize=(10, 5))
    df["Close"].plot(label="收市价", color="blue")
    df["MA5"].plot(label="5日均线", linestyle="--", color="orange")
    plt.title(f"{stock} - 收盘价与5日均线")
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"✅ 图表已生成：{filename}")

    res = send_telegram_photo(filename)
    if res.get("ok"):
        print(f"✅ 已发送图表至 Telegram")
    else:
        print(f"❌ 发送失败：{res}")

# 主执行逻辑
for code in stock_list:
    analyze_stock(code)
