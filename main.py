import os
import datetime
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
import requests

# 设置中文字体，避免缺字警告
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 从环境变量获取 Telegram Bot Token 和 Chat ID
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID    = os.getenv("TG_CHAT_ID")

# 关注的股票列表
stock_list = ["5255.KL", "0209.KL"]

# 创建图表目录
os.makedirs("charts", exist_ok=True)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    return requests.post(url, data=data).json()

def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": TG_CHAT_ID, "caption": caption}
        return requests.post(url, files=files, data=data).json()

def fetch_news_placeholder(stock):
    return "暂无重要新闻。"

def analyze_stock(stock):
    print(f"📈 抓取 {stock} 的数据...")
    df = yf.download(stock, period="10d", interval="1d", auto_adjust=False)
    if df.empty or len(df) < 2:
        print(f"❌ 无法获取 {stock} 的有效数据")
        return

    # 计算5日均线
    df["MA5"] = df["Close"].rolling(window=5).mean()

    # 取最后两天数据为 Series
    latest    = df.iloc[-1]  # Series
    yesterday = df.iloc[-2]  # Series

    # 安全获取开盘/收盘价
    open_price  = float(latest["Open"].item())  if hasattr(latest["Open"], "item")  else float(latest["Open"])
    close_price = float(latest["Close"].item()) if hasattr(latest["Close"], "item") else float(latest["Close"])
    change      = close_price - open_price
    pct_change  = round(change / open_price * 100, 2) if open_price != 0 else 0.0

    # 涨跌说明
    if change > 0:
        arrow  = "📈 上涨"
        reason = "今日股价上涨，投资者积极进场。"
    elif change < 0:
        arrow  = "📉 下跌"
        reason = "今日股价下跌，可能受市场情绪影响。"
    else:
        arrow  = "➖ 无涨跌"
        reason = "今日股价稳定，缺乏波动。"

    # 获取 MA5 当日与昨日值
    ma5_today     = float(latest["MA5"].item())     if pd.notna(latest["MA5"])     else 0.0
    ma5_yesterday = float(yesterday["MA5"].item()) if pd.notna(yesterday["MA5"]) else 0.0

    trend_note = ""
    if ma5_today > ma5_yesterday:
        trend_note = "5日均线走高，短期上升趋势。"
    elif ma5_today < ma5_yesterday:
        trend_note = "5日均线下滑，短期承压。"

    news_text = fetch_news_placeholder(stock)

    # 构造 Telegram 文本
    message = (
        f"📊 *{stock} 股票走势汇报*\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{arrow} RM {abs(change):.3f}（{abs(pct_change):.2f}%）\n"
        f"说明：{reason}\n"
        f"{trend_note}\n\n"
        f"📰 今日相关新闻：\n{news_text}"
    )
    send_telegram_message(message)

    # 绘制收盘价与5日均线
    plt.figure(figsize=(10, 5))
    df["Close"].plot(label="收盘价", color="blue")
    df["MA5"].plot(label="5日均线", linestyle="--", color="orange")
    plt.title(f"{stock} - 收盘价与5日均线")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    filename = f"charts/{stock.replace('.KL','')}_chart.png"
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"✅ 图表已生成：{filename}")

    res = send_telegram_photo(filename)
    if res.get("ok"):
        print("✅ 已发送图表至 Telegram")
    else:
        print(f"❌ 发送失败：{res}")

# 主流程
for s in stock_list:
    analyze_stock(s)
