import os
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 无头环境必须
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import numpy as np
import pytz
from datetime import datetime

# ========== 配置 ==========
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
STOCK_LIST = os.getenv("STOCK_LIST", "5255.KL,0209.KL").split(",")
CHART_DIR = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# 设置马来西亚时区
MYT = pytz.timezone('Asia/Kuala_Lumpur')

# ========== 工具函数 ==========
def fetch_data(symbol, retries=2):
    for attempt in range(retries):
        try:
            df = yf.download(
                symbol, 
                period="3mo", 
                interval="1d", 
                auto_adjust=True,
                progress=False
            )
            if not df.empty and len(df) > 10:
                # 转换为马来西亚时区
                df.index = df.index.tz_convert(MYT)
                df.dropna(inplace=True)
                return df
        except Exception as e:
            print(f"⚠️ 获取 {symbol} 数据失败: {str(e)}")
    return pd.DataFrame()

def compute_indicators(df):
    if len(df) < 20:
        return df
        
    # 移动平均线
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    
    # RSI 计算
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, np.nan)
        df["RSI"] = np.where(~np.isnan(rs), 100 - (100 / (1 + rs)), 50)
    
    # MACD 计算
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    return df

def draw_chart(symbol, df):
    if df.empty or len(df) < 5:
        return None
        
    plt.figure(figsize=(10, 6))
    
    # 自适应显示天数
    days = min(60, len(df))
    tail_df = df.tail(days)
    
    # 价格曲线
    plt.plot(tail_df.index, tail_df["Close"], label="Close Price", linewidth=2, color="#1f77b4")
    
    # 移动平均线
    if "MA5" in df and not df["MA5"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA5"], label="MA5", linestyle="--", color="orange")
    if "MA20" in df and not df["MA20"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA20"], label="MA20", linestyle="-.", color="red")
    
    # 格式化日期
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d', tz=MYT))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.title(f"{symbol} Price Trend ({days} Days)", fontsize=14)
    plt.xlabel("Date", fontsize=10)
    plt.ylabel("Price (RM)", fontsize=10)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    path = f"{CHART_DIR}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path, dpi=100, bbox_inches='tight')
    plt.close()
    return path

def ask_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key not set"
    try:
        res = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a professional Malaysian stock analyst. Provide concise technical analysis in Chinese."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=20
        )
        res.raise_for_status()
        data = res.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "❌ API response format error")
    except requests.exceptions.Timeout:
        return "❌ API request timeout"
    except Exception as e:
        return f"❌ API error: {str(e)}"

def send_to_telegram(text, img_path=None):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram credentials not set")
        return
        
    try:
        if img_path and os.path.exists(img_path):
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
            with open(img_path, "rb") as pic:
                files = {"photo": pic}
                data = {"chat_id": TG_CHAT_ID, "caption": text[:1000], "parse_mode": "Markdown"}
                requests.post(url, data=data, files=files, timeout=15)
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            data = {"chat_id": TG_CHAT_ID, "text": text[:4000], "parse_mode": "Markdown"}
            requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram send failed: {str(e)}")

def analyze_stock(symbol):
    """分析单只股票并返回报告内容和图表路径"""
    try:
        print(f"📈 Analyzing {symbol}...")
        df = fetch_data(symbol)
        if df.empty:
            return f"⚠️ No data found for {symbol}", None

        df = compute_indicators(df)
        
        if len(df) < 2:
            return f"⚠️ Insufficient data for {symbol}", None
            
        # 获取最新数据
        today = df.iloc[-1]
        yesterday = df.iloc[-2] if len(df) >= 2 else today
        
        # 基础价格数据
        open_p = today["Open"]
        close_p = today["Close"]
        diff = close_p - open_p
        pct = (diff / open_p) * 100 if open_p != 0 else 0
        trend = "📈 Up" if diff > 0 else "📉 Down" if diff < 0 else "➖ Flat"
        last_trade_date = today.name.strftime('%Y-%m-%d')
        
        # 生成技术信号
        signals = []
        
        # MACD 信号
        if all(col in df.columns for col in ["MACD", "MACD_SIGNAL"]):
            macd_val = today.get("MACD", 0)
            signal_val = today.get("MACD_SIGNAL", 0)
            
            if macd_val > signal_val and yesterday.get("MACD", 0) <= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🟢 MACD Golden Cross")
            elif macd_val < signal_val and yesterday.get("MACD", 0) >= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🔴 MACD Death Cross")
        
        # RSI 信号
        if "RSI" in df.columns:
            rsi_val = today.get("RSI", 50)
            if rsi_val > 70:
                signals.append(f"🔴 RSI Overbought ({rsi_val:.1f})")
            elif rsi_val < 30:
                signals.append(f"🟢 RSI Oversold ({rsi_val:.1f})")
        
        # 均线信号
        if "MA5" in df.columns and "MA20" in df.columns:
            ma5 = today.get("MA5", 0)
            ma20 = today.get("MA20", 0)
            
            if ma5 > ma20 and yesterday.get("MA5", 0) <= yesterday.get("MA20", 0):
                signals.append("🟢 MA5 Cross Above MA20")
            elif ma5 < ma20 and yesterday.get("MA5", 0) >= yesterday.get("MA20", 0):
                signals.append("🔴 MA5 Cross Below MA20")
        
        # 构建AI提示
        prompt = (
            f"作为专业股票分析师，请用中文简洁分析 {symbol}："
            f"最后交易日 {last_trade_date}，开盘价 RM{open_p:.3f}，收盘价 RM{close_p:.3f}（{trend} {abs(diff):.3f}，涨跌幅 {pct:.2f}%）。"
        )
        
        # 添加技术指标
        if "MA5" in df.columns:
            prompt += f" MA5={today['MA5']:.3f}, MA20={today['MA20']:.3f};"
        if "RSI" in df.columns:
            prompt += f" RSI={today['RSI']:.1f};"
        if "MACD" in df.columns:
            prompt += f" MACD={today['MACD']:.3f}, Signal={today['MACD_SIGNAL']:.3f}。"
        
        prompt += " 给出1-2句技术分析结论和操作建议。"
        
        # 获取AI分析
        ai_comment = ask_deepseek(prompt)
        
        # 构建消息
        msg = (
            f"📊 *{symbol} Stock Report*\n"
            f"• Last Trade: `{last_trade_date}`\n"
            f"• Open: `RM {open_p:.3f}`\n"
            f"• Close: `RM {close_p:.3f}`\n"
            f"• Change: {trend} `RM {abs(diff):.3f}` ({pct:.2f}%)\n"
        )
        
        # 添加技术信号
        if signals:
            msg += "\n📈 *Technical Signals*:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
        
        msg += f"\n🤖 *AI Analysis*:\n{ai_comment}\n\n_Updated: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}_"
        
        # 生成图表
        chart_path = draw_chart(symbol, df)
        
        return msg, chart_path
        
    except Exception as e:
        error_msg = f"⚠️ Error analyzing {symbol}: {str(e)}"
        print(error_msg)
        return error_msg, None

# ========== 主执行逻辑 ==========
def main():
    print("🚀 Starting stock analysis...")
    print(f"📋 Stocks: {', '.join(STOCK_LIST)}")
    
    for symbol in STOCK_LIST:
        msg, chart_path = analyze_stock(symbol)
        if msg:
            send_to_telegram(msg, chart_path)
    
    print("✅ Analysis completed and reports sent")

if __name__ == "__main__":
    main()
