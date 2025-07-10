import yfinance as yf
import matplotlib.pyplot as plt
import requests
import os

# === 你的 Telegram Bot 配置（测试用） ===
TG_BOT_TOKEN = "7976682927:AAHVwjcfg4fzP9Wu6wv0ue2LdPSzrmE6oE0"
TG_CHAT_ID = "-1002721174982"

# === 发送图片到 Telegram 群组 ===
def send_telegram_photo(photo_path, caption=""):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        files = {"photo": photo}
        data = {"chat_id": TG_CHAT_ID, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送：{photo_path}")
        else:
            print(f"❌ 发送失败：{response.text}")

# === 抓取股票数据并生成图表 ===
def generate_stock_report(stock_code):
    df = yf.download(stock_code, period="30d", interval="1d", auto_adjust=False)
    if df.empty:
        print(f"⚠️ 无法获取 {stock_code} 的数据")
        return

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()

    plt.figure(figsize=(10, 5))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{stock_code} - 30日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.grid(True)
    plt.legend()

    os.makedirs("charts", exist_ok=True)
    image_path = f"charts/{stock_code.replace('.KL','')}.png"
    plt.savefig(image_path)
    plt.close()

    latest = df.iloc[-1]
    open_price = latest["Open"]
    close_price = latest["Close"]
    change = close_price - open_price
    pct = (change / open_price) * 100 if open_price else 0

    trend = "📈 上涨" if change > 0 else "📉 下跌" if change < 0 else "➖ 持平"

    caption = (
        f"📊 股票：{stock_code}\n"
        f"开市：RM {open_price:.2f}\n"
        f"收市：RM {close_price:.2f}\n"
        f"涨跌：{trend} RM {change:.2f}（{pct:.2f}%）"
    )

    send_telegram_photo(image_path, caption)

# === 主程序入口 ===
if __name__ == "__main__":
    stock_list = ["5255.KL", "0209.KL"]
    for code in stock_list:
        generate_stock_report(code)
