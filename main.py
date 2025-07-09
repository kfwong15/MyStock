import os
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import numpy as np
import pytz
from datetime import datetime, timedelta
import time
import re
import json
import traceback

# ========== 配置 ==========
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 处理股票列表
stock_list_str = os.getenv("STOCK_LIST", "5255.KL,0209.KL")
STOCK_LIST = [s.strip().upper() for s in stock_list_str.split(",") if s.strip()]

# 如果没有股票列表，使用默认值
if not STOCK_LIST:
    STOCK_LIST = ["5255.KL", "0209.KL"]

CHART_DIR = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# 设置马来西亚时区
MYT = pytz.timezone('Asia/Kuala_Lumpur')

# ========== 工具函数 ==========
def fetch_data(symbol, retries=3):
    """获取股票数据，带重试机制和备用数据源"""
    if not symbol or not re.match(r"^[A-Z0-9]+\.[A-Z]+$", symbol):
        print(f"⚠️ 无效的股票代码: {symbol}")
        return pd.DataFrame()
    
    # 尝试使用 yfinance 获取数据
    df = fetch_with_yfinance(symbol, retries)
    if not df.empty:
        return df
    
    # 如果 yfinance 失败，尝试备用 API
    print(f"⚠️ yfinance 获取 {symbol} 失败，尝试备用数据源...")
    return fetch_with_backup_api(symbol)

def fetch_with_yfinance(symbol, retries=3):
    """使用 yfinance 获取数据"""
    for attempt in range(retries):
        try:
            print(f"🔍 [yfinance] 获取 {symbol} 数据 (尝试 {attempt+1}/{retries})...")
            
            # 创建 Ticker 对象并获取历史数据
            ticker = yf.Ticker(symbol)
            
            # 获取3个月数据
            end_date = datetime.now(MYT)
            start_date = end_date - timedelta(days=90)
            
            df = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=True
            )
            
            if not df.empty and len(df) > 10:
                # 转换为马来西亚时区
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC').tz_convert(MYT)
                else:
                    df.index = df.index.tz_convert(MYT)
                df.dropna(inplace=True)
                print(f"✅ [yfinance] 成功获取 {symbol} 数据 ({len(df)} 条记录)")
                return df
            else:
                print(f"⚠️ [yfinance] {symbol} 返回空数据")
        except Exception as e:
            print(f"⚠️ [yfinance] 获取 {symbol} 数据失败: {str(e)}")
            traceback.print_exc()
            time.sleep(2)  # 等待后重试
    
    return pd.DataFrame()

def fetch_with_backup_api(symbol):
    """使用备用API获取马来西亚股票数据"""
    try:
        print(f"🔍 [备用API] 获取 {symbol} 数据...")
        
        # 移除.KL后缀
        symbol_code = symbol.replace('.KL', '')
        
        # 使用马来西亚交易所API
        url = f"https://www.malaysiastock.biz/StockChart.aspx?type=C&value={symbol_code}"
        
        # 设置请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"https://www.malaysiastock.biz/Stock-Chart.aspx?symbol={symbol_code}"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 解析响应数据
        data = response.json()
        
        # 创建DataFrame - 修复这里的语法错误
        df = pd.DataFrame({
            'Date': pd.to_datetime(data['t']),  # 修复这里的括号问题
            'Open': data['o'],
            'High': data['h'],
            'Low': data['l'],
            'Close': data['c'],
            'Volume': data['v']
        })
        
        # 设置日期为索引
        df.set_index('Date', inplace=True)
        
        # 转换为马来西亚时区
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(MYT)
        else:
            df.index = df.index.tz_convert(MYT)
        
        if not df.empty:
            print(f"✅ [备用API] 成功获取 {symbol} 数据 ({len(df)} 条记录)")
            return df
        else:
            print(f"⚠️ [备用API] {symbol} 返回空数据")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"⚠️ [备用API] 获取 {symbol} 数据失败: {str(e)}")
        traceback.print_exc()
        return pd.DataFrame()

def compute_indicators(df):
    """计算技术指标"""
    if df.empty or len(df) < 5:
        print(f"⚠️ 数据不足 ({len(df)} 条)，无法计算指标")
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
    """绘制股票图表"""
    if df.empty or len(df) < 5:
        print(f"⚠️ 无法为 {symbol} 绘制图表: 数据不足")
        return None
        
    plt.figure(figsize=(10, 6))
    
    # 自适应显示天数
    days = min(60, len(df))
    tail_df = df.tail(days)
    
    # 价格曲线
    plt.plot(tail_df.index, tail_df["Close"], label="收盘价", linewidth=2, color="#1f77b4")
    
    # 移动平均线
    if "MA5" in df and not df["MA5"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA5"], label="MA5", linestyle="--", color="orange")
    if "MA20" in df and not df["MA20"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA20"], label="MA20", linestyle="-.", color="red")
    
    # 格式化日期
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d', tz=MYT))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.title(f"{symbol} {days}日走势", fontsize=14)
    plt.xlabel("日期", fontsize=10)
    plt.ylabel("价格 (RM)", fontsize=10)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    path = f"{CHART_DIR}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"📊 已生成 {symbol} 图表: {path}")
    return path

def ask_deepseek(prompt):
    """调用DeepSeek API获取分析"""
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key 未设置"
    
    print(f"🤖 正在获取AI分析: {prompt[:100]}...")
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
                        "content": "你是有经验的马来西亚股票分析师，提供简洁的技术分析，使用中文回复。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=25
        )
        res.raise_for_status()
        data = res.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "❌ API响应格式异常")
        print(f"✅ 获取到AI分析: {content[:100]}...")
        return content
    except requests.exceptions.Timeout:
        return "❌ API请求超时"
    except Exception as e:
        return f"❌ API错误: {str(e)}"

def send_to_telegram(text, img_path=None):
    """发送消息到Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram凭证未设置")
        return
        
    try:
        print(f"📤 正在发送消息到Telegram...")
        if img_path and os.path.exists(img_path):
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
            with open(img_path, "rb") as pic:
                files = {"photo": pic}
                data = {"chat_id": TG_CHAT_ID, "caption": text[:1000], "parse_mode": "Markdown"}
                response = requests.post(url, data=data, files=files, timeout=15)
                print(f"📷 已发送带图消息 (状态: {response.status_code})")
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            data = {"chat_id": TG_CHAT_ID, "text": text[:4000], "parse_mode": "Markdown"}
            response = requests.post(url, json=data, timeout=10)
            print(f"💬 已发送文本消息 (状态: {response.status_code})")
    except Exception as e:
        print(f"⚠️ Telegram发送失败: {str(e)}")

def analyze_stock(symbol):
    """分析单只股票并返回报告内容和图表路径"""
    if not symbol:
        return "⚠️ 股票代码为空，跳过分析", None
        
    print(f"\n{'='*40}")
    print(f"📈 开始分析 {symbol}")
    print(f"{'='*40}")
    
    try:
        df = fetch_data(symbol)
        if df.empty:
            return f"⚠️ 找不到 {symbol} 的数据", None

        df = compute_indicators(df)
        
        if len(df) < 2:
            return f"⚠️ {symbol} 数据不足，无法分析", None
            
        # 获取最新数据
        today = df.iloc[-1]
        yesterday = df.iloc[-2] if len(df) >= 2 else today
        
        # 基础价格数据
        open_p = today["Open"]
        close_p = today["Close"]
        high_p = today["High"]
        low_p = today["Low"]
        diff = close_p - open_p
        pct = (diff / open_p) * 100 if open_p != 0 else 0
        trend = "📈 上涨" if diff > 0 else "📉 下跌" if diff < 0 else "➖ 平盘"
        last_trade_date = today.name.strftime('%Y-%m-%d')
        volume = today["Volume"] if "Volume" in today else 0
        
        # 生成技术信号
        signals = []
        
        # MACD 信号
        if all(col in df.columns for col in ["MACD", "MACD_SIGNAL"]):
            macd_val = today.get("MACD", 0)
            signal_val = today.get("MACD_SIGNAL", 0)
            
            if macd_val > signal_val and yesterday.get("MACD", 0) <= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🟢 MACD金叉 - 潜在上涨信号")
            elif macd_val < signal_val and yesterday.get("MACD", 0) >= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🔴 MACD死叉 - 潜在下跌信号")
        
        # RSI 信号
        if "RSI" in df.columns:
            rsi_val = today.get("RSI", 50)
            if rsi_val > 70:
                signals.append(f"🔴 RSI超买 ({rsi_val:.1f})")
            elif rsi_val < 30:
                signals.append(f"🟢 RSI超卖 ({rsi_val:.1f})")
        
        # 均线信号
        if "MA5" in df.columns and "MA20" in df.columns:
            ma5 = today.get("MA5", 0)
            ma20 = today.get("MA20", 0)
            
            if ma5 > ma20 and yesterday.get("MA5", 0) <= yesterday.get("MA20", 0):
                signals.append("🟢 MA5上穿MA20 - 短期看涨")
            elif ma5 < ma20 and yesterday.get("MA5", 0) >= yesterday.get("MA20", 0):
                signals.append("🔴 MA5下穿MA20 - 短期看跌")
        
        # 构建AI提示
        prompt = (
            f"作为专业股票分析师，请用中文简洁分析 {symbol}："
            f"最后交易日 {last_trade_date}，开盘价 RM{open_p:.3f}，最高价 RM{high_p:.3f}，"
            f"最低价 RM{low_p:.3f}，收盘价 RM{close_p:.3f}（{trend} {abs(diff):.3f}，涨跌幅 {pct:.2f}%），"
            f"成交量 {volume:,}。"
        )
        
        # 添加技术指标
        if "MA5" in df.columns:
            prompt += f" 5日均线(MA5)=RM{today['MA5']:.3f}, 20日均线(MA20)=RM{today['MA20']:.3f};"
        if "RSI" in df.columns:
            prompt += f" RSI={today['RSI']:.1f};"
        if "MACD" in df.columns and "MACD_SIGNAL" in df.columns:
            prompt += f" MACD={today['MACD']:.3f}, 信号线={today['MACD_SIGNAL']:.3f}。"
        
        prompt += " 请给出1-2句技术分析结论和操作建议。"
        
        # 获取AI分析
        ai_comment = ask_deepseek(prompt)
        
        # 构建消息
        msg = (
            f"📊 *{symbol} 股票分析报告*\n"
            f"• 最后交易日: `{last_trade_date}`\n"
            f"• 开盘价: `RM {open_p:.3f}`\n"
            f"• 最高价: `RM {high_p:.3f}`\n"
            f"• 最低价: `RM {low_p:.3f}`\n"
            f"• 收盘价: `RM {close_p:.3f}`\n"
            f"• 涨跌幅: {trend} `RM {abs(diff):.3f}` ({pct:.2f}%)\n"
            f"• 成交量: `{volume:,}`\n"
        )
        
        # 添加技术信号
        if signals:
            msg += "\n📈 *技术信号*:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
        
        msg += f"\n🤖 *AI分析*:\n{ai_comment}\n\n_更新于: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}_"
        
        # 生成图表
        chart_path = draw_chart(symbol, df)
        
        return msg, chart_path
        
    except Exception as e:
        error_msg = f"⚠️ 分析 {symbol} 时出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return error_msg, None

# ========== 主执行逻辑 ==========
def main():
    print(f"\n{'='*50}")
    print(f"🚀 开始股票分析 - {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}")
    print(f"📋 分析 {len(STOCK_LIST)} 只股票: {', '.join(STOCK_LIST)}")
    print(f"{'='*50}\n")
    
    for symbol in STOCK_LIST:
        msg, chart_path = analyze_stock(symbol)
        if msg:
            send_to_telegram(msg, chart_path)
        time.sleep(3)  # 避免API限流
    
    print(f"\n{'='*50}")
    print(f"✅ 分析完成! 已处理 {len(STOCK_LIST)} 只股票")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
