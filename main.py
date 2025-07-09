import os
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import numpy as np
from flask import Flask, request, jsonify
import threading
import time

# ========== Flask Webhook ==========
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "").strip()
        
        if text.startswith("/stock"):
            parts = text.split()
            if len(parts) == 1:
                # 默认分析所有股票
                send_to_telegram("📊 正在生成所有股票简报...", chat_id=chat_id)
                threading.Thread(target=run_stock_analysis, args=(chat_id,)).start()
            elif len(parts) == 2:
                # 分析特定股票
                symbol = parts[1].upper()
                send_to_telegram(f"📊 正在生成 {symbol} 股票简报...", chat_id=chat_id)
                threading.Thread(target=analyze_single_stock, args=(symbol, chat_id)).start()
            else:
                send_to_telegram("⚠️ 用法：/stock 或 /stock [股票代码]", chat_id=chat_id)
        else:
            send_to_telegram("🤖 请输入 /stock 获取股票分析", chat_id=chat_id)
            
    return jsonify({"ok": True})

# ========== 配置 ==========
TG_BOT_TOKEN     = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID       = os.getenv("TG_CHAT_ID")  # 默认聊天 ID
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
STOCK_LIST       = ["5255.KL", "0209.KL"]  # 默认股票列表
CHART_DIR        = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# ========== 工具函数 ==========
def fetch_data(symbol, retries=2):
    for attempt in range(retries):
        try:
            df = yf.download(symbol, period="3mo", interval="1d", auto_adjust=True)
            if not df.empty:
                df.dropna(inplace=True)
                return df
        except Exception as e:
            print(f"⚠️ 获取 {symbol} 数据失败: {e}")
            time.sleep(2)
    return pd.DataFrame()

def compute_indicators(df):
    if len(df) < 20:
        return df
        
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
        
    plt.figure(figsize=(10, 5))
    
    # 自适应显示天数
    days = min(60, len(df))
    tail_df = df.tail(days)
    
    tail_df["Close"].plot(label="收盘价", linewidth=2, color="#1f77b4")
    
    # 只绘制有值的均线
    if "MA5" in df and not df["MA5"].isnull().all():
        tail_df["MA5"].plot(label="MA5", linestyle="--", color="orange")
    if "MA20" in df and not df["MA20"].isnull().all():
        tail_df["MA20"].plot(label="MA20", linestyle="-.", color="red")
        
    plt.title(f"{symbol} 近{days}日走势", fontsize=14)
    plt.xlabel("日期", fontsize=10)
    plt.ylabel("价格 (RM)", fontsize=10)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    path = f"{CHART_DIR}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path, dpi=100)
    plt.close()
    return path

def ask_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key 未设置"
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
                    {"role": "system", "content": "你是有经验的马来西亚股票分析师，用中文简洁分析，包含技术指标评估。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 300
            },
            timeout=15
        )
        res.raise_for_status()
        data = res.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "❌ DeepSeek API 响应格式异常")
    except requests.exceptions.Timeout:
        return "❌ DeepSeek API 请求超时"
    except Exception as e:
        return f"❌ DeepSeek API 错误：{str(e)}"

def send_to_telegram(text, img_path=None, chat_id=None):
    if chat_id is None:
        chat_id = TG_CHAT_ID
    
    try:
        if img_path and os.path.exists(img_path):
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
            with open(img_path, "rb") as pic:
                files = {"photo": pic}
                data = {"chat_id": chat_id, "caption": text[:1000], "parse_mode": "Markdown"}
                requests.post(url, data=data, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            data = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "Markdown"}
            requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram发送失败: {e}")

# ========== 股票分析逻辑 ==========
def analyze_single_stock(symbol, chat_id=None):
    """分析单只股票并发送报告"""
    try:
        print(f"📈 分析 {symbol}...")
        df = fetch_data(symbol)
        if df.empty:
            send_to_telegram(f"⚠️ 找不到 {symbol} 的数据或数据源暂时不可用。", chat_id=chat_id)
            return

        df = compute_indicators(df)
        
        if len(df) < 2:
            send_to_telegram(f"⚠️ {symbol} 数据不足，无法生成分析报告。", chat_id=chat_id)
            return
            
        # 提取最新数据
        today = df.iloc[-1]
        yesterday = df.iloc[-2] if len(df) >= 2 else today
        
        # 基础价格数据
        open_p  = float(today["Open"])
        close_p = float(today["Close"])
        diff    = close_p - open_p
        pct     = (diff / open_p) * 100 if open_p != 0 else 0
        trend   = "📈 上涨" if diff > 0 else "📉 下跌" if diff < 0 else "➖ 无涨跌"
        
        # 生成技术信号
        signals = []
        
        # MACD 信号
        if all(col in df.columns for col in ["MACD", "MACD_SIGNAL"]):
            macd_val = float(today.get("MACD", 0))
            signal_val = float(today.get("MACD_SIGNAL", 0))
            
            if macd_val > signal_val and float(yesterday.get("MACD", 0)) <= float(yesterday.get("MACD_SIGNAL", 0)):
                signals.append("🟢 MACD 金叉 - 潜在上涨信号")
            elif macd_val < signal_val and float(yesterday.get("MACD", 0)) >= float(yesterday.get("MACD_SIGNAL", 0)):
                signals.append("🔴 MACD 死叉 - 潜在下跌信号")
        
        # RSI 信号
        if "RSI" in df.columns:
            rsi_val = float(today.get("RSI", 50))
            if rsi_val > 70:
                signals.append(f"🔴 RSI 超买 ({rsi_val:.1f})")
            elif rsi_val < 30:
                signals.append(f"🟢 RSI 超卖 ({rsi_val:.1f})")
        
        # 均线信号
        if "MA5" in df.columns and "MA20" in df.columns:
            ma5 = float(today.get("MA5", 0))
            ma20 = float(today.get("MA20", 0))
            
            if ma5 > ma20 and float(yesterday.get("MA5", 0)) <= float(yesterday.get("MA20", 0)):
                signals.append("🟢 MA5 上穿 MA20 - 短期看涨")
            elif ma5 < ma20 and float(yesterday.get("MA5", 0)) >= float(yesterday.get("MA20", 0)):
                signals.append("🔴 MA5 下穿 MA20 - 短期看跌")
        
        # 构建AI提示
        prompt = (
            f"作为股票分析师，请用中文简洁分析 {symbol}："
            f"今日开盘价 RM{open_p:.3f}，收盘价 RM{close_p:.3f}（{trend} {abs(diff):.3f}，涨跌幅 {pct:.2f}%）。"
        )
        
        # 添加技术指标到提示
        if "MA5" in df.columns:
            prompt += f" 5日均线(MA5)={today['MA5']:.3f}, 20日均线(MA20)={today['MA20']:.3f};"
        if "RSI" in df.columns:
            prompt += f" RSI={today['RSI']:.1f};"
        if "MACD" in df.columns:
            prompt += f" MACD={today['MACD']:.3f}, 信号线={today['MACD_SIGNAL']:.3f}。"
        
        prompt += " 请给出1-2句技术分析结论和操作建议。"
        
        # 获取AI分析
        ai_comment = ask_deepseek(prompt)
        
        # 构建最终消息
        msg = (
            f"📊 *{symbol} 股票简报*\n"
            f"• 开市价: `RM {open_p:.3f}`\n"
            f"• 收市价: `RM {close_p:.3f}`\n"
            f"• 涨跌幅: {trend} `RM {abs(diff):.3f}` ({pct:.2f}%)\n"
        )
        
        # 添加技术信号
        if signals:
            msg += "\n📈 *技术信号*:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
        
        msg += f"\n🤖 *AI分析*:\n{ai_comment}\n\n_数据更新: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}_"
        
        # 生成图表
        chart_path = draw_chart(symbol, df)
        send_to_telegram(msg, chart_path, chat_id=chat_id)
        
    except Exception as e:
        error_msg = f"⚠️ 分析 {symbol} 时出错: {str(e)}"
        print(error_msg)
        send_to_telegram(error_msg, chat_id=chat_id)

def run_stock_analysis(chat_id=None):
    """分析股票列表中的所有股票"""
    for symbol in STOCK_LIST:
        analyze_single_stock(symbol, chat_id)
        time.sleep(2)  # 避免API限流

# ========== 启动 Flask ==========
if __name__ == "__main__":
    import sys
    if "run" in sys.argv:
        print("🚀 启动股票分析机器人...")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    else:
        print("🔍 开始分析股票...")
        run_stock_analysis()
