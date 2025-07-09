import os
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import numpy as np
from flask import Flask, request, jsonify

# ========== 环境变量 ==========
TG_BOT_TOKEN     = os.getenv("TG_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CHART_DIR        = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# ========== Flask App ==========
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": True})

    msg = data["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]

    if text.startswith("/stock"):
        parts = text.split()
        if len(parts) != 2:
            send_to_telegram("⚠️ 用法：/stock 股票代码，例如 /stock 5255.KL", chat_id)
        else:
            symbol = parts[1].upper()
            result, chart_path = generate_stock_report(symbol)
            send_to_telegram(result, chat_id, chart_path)
    else:
        send_to_telegram("🤖 指令无效，请输入 /stock 股票代码", chat_id)

    return jsonify({"ok": True})

# ========== 工具函数 ==========
def fetch_data(symbol):
    try:
        df = yf.download(symbol, period="3mo", interval="1d", auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.dropna(inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def compute_indicators(df):
    # 确保有足够数据计算指标
    if len(df) < 20:
        return df
        
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    
    # RSI 计算 (带安全保护)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    
    # 处理除零情况
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
        
    plt.figure(figsize=(10,5))
    
    # 自适应显示天数 (最多60天)
    days = min(60, len(df))
    tail_df = df.tail(days)
    
    tail_df["Close"].plot(label="收盘价", color="black")
    
    # 只绘制有值的均线
    if "MA5" in df and not df["MA5"].isnull().all():
        tail_df["MA5"].plot(label="MA5", linestyle="--", color="blue")
    if "MA20" in df and not df["MA20"].isnull().all():
        tail_df["MA20"].plot(label="MA20", linestyle="--", color="red")
        
    plt.title(f"{symbol} 近{days}日走势")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    path = f"{CHART_DIR}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path)
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
                    {"role":"system", "content":"你是马来西亚股票分析师，回复简洁中文。"},
                    {"role":"user",   "content": prompt}
                ]
            },
            timeout=15
        )
        res.raise_for_status()
        data = res.json()
        
        # 验证响应结构
        if "choices" not in data or len(data["choices"]) == 0:
            return "❌ DeepSeek API 响应格式异常"
            
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "❌ DeepSeek API 请求超时"
    except Exception as e:
        return f"❌ DeepSeek API 错误：{str(e)}"

def send_to_telegram(text, chat_id, img_path=None):
    try:
        if img_path and os.path.exists(img_path):
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
            with open(img_path, "rb") as pic:
                files = {"photo": pic}
                data = {"chat_id": chat_id, "caption": text[:1000]}  # 限制标题长度
                requests.post(url, data=data, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": chat_id, 
                "text": text[:4000],  # 限制消息长度
                "parse_mode": "Markdown"
            }, timeout=10)
    except Exception:
        # 简化错误处理
        pass

def generate_stock_report(symbol):
    # 获取数据
    df = fetch_data(symbol)
    if df.empty:
        return f"⚠️ 找不到 {symbol} 的数据或数据源暂时不可用。", None
        
    # 计算技术指标
    df = compute_indicators(df)
    
    # 检查足够数据点
    if len(df) < 2:
        return f"⚠️ {symbol} 数据不足，无法生成分析报告。", None
        
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
    
    # MACD 信号 (带存在检查)
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
        f"作为马来西亚股票分析师，请用中文简洁分析：{symbol} "
        f"今日开盘 RM{open_p:.3f}，收盘 RM{close_p:.3f}（{trend} {abs(diff):.3f} / {pct:.2f}%）。"
    )
    
    # 添加技术指标到提示
    if "MA5" in df.columns:
        prompt += f" MA5={today['MA5']:.3f}, MA20={today['MA20']:.3f};"
    if "RSI" in df.columns:
        prompt += f" RSI={today['RSI']:.1f};"
    if "MACD" in df.columns:
        prompt += f" MACD={today['MACD']:.3f}, 信号线={today['MACD_SIGNAL']:.3f}。"
    
    prompt += " 给出1-2句技术分析结论。"
    
    # 获取AI分析 (带降级处理)
    ai_comment = ask_deepseek(prompt)
    
    # 如果API失败，生成基础分析
    if ai_comment.startswith("❌"):
        ai_comment = (
            "🤖 技术分析："
            f"收盘价{'高于' if close_p > open_p else '低于'}开盘价，显示{trend.replace('📈','').replace('📉','')}趋势。"
        )
        if signals:
            ai_comment += " 关键信号：" + "，".join(signals)
    
    # 构建最终消息
    msg = (
        f"📊 *{symbol} 股票简报*\n"
        f"• 开市价：`RM {open_p:.3f}`\n"
        f"• 收市价：`RM {close_p:.3f}`\n"
        f"• 涨跌幅：{trend} `RM {abs(diff):.3f}` ({pct:.2f}%)\n"
    )
    
    # 添加技术信号
    if signals:
        msg += "\n📈 *技术信号*:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
    
    msg += f"\n🤖 *AI分析*:\n{ai_comment}\n\n_数据来源：Yahoo Finance_"
    
    # 生成图表
    chart_path = draw_chart(symbol, df)
    
    return msg, chart_path

# ========== 本地测试模式 ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
