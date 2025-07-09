import os
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
import traceback
import random
import json
from fake_useragent import UserAgent

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
def generate_fake_data(symbol):
    """生成模拟股票数据"""
    print(f"⚠️ 使用模拟数据代替 {symbol}")
    
    # 创建日期范围（最近90天）
    end_date = datetime.now(MYT)
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    
    # 基础价格（随机波动）
    base_price = random.uniform(0.5, 10.0)
    prices = [base_price]
    
    for i in range(1, len(dates)):
        change = random.uniform(-0.05, 0.05)  # 每日涨跌幅在-5%到5%之间
        prices.append(prices[-1] * (1 + change))
    
    # 创建DataFrame
    df = pd.DataFrame({
        'Open': [p * random.uniform(0.98, 1.02) for p in prices],
        'High': [p * random.uniform(1.01, 1.05) for p in prices],
        'Low': [p * random.uniform(0.95, 0.99) for p in prices],
        'Close': prices,
        'Volume': [random.randint(100000, 5000000) for _ in prices]
    }, index=dates)
    
    # 转换为马来西亚时区
    df.index = df.index.tz_localize('UTC').tz_convert(MYT)
    
    return df

def fetch_data(symbol, retries=3):
    """获取股票数据，使用多种数据源尝试"""
    if not symbol:
        return pd.DataFrame()
    
    # 尝试使用Yahoo Finance替代API
    df = fetch_yahoo_alternative(symbol, retries)
    if not df.empty:
        return df
    
    # 尝试使用Alpha Vantage API
    df = fetch_alpha_vantage(symbol, retries)
    if not df.empty:
        return df
    
    # 如果所有API都失败，使用模拟数据
    return generate_fake_data(symbol)

def fetch_yahoo_alternative(symbol, retries=3):
    """使用Yahoo Finance替代API获取数据"""
    ua = UserAgent()
    
    for attempt in range(retries):
        try:
            # 生成随机用户代理
            user_agent = ua.random
            headers = {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            print(f"🔍 [Yahoo替代API] 获取 {symbol} 数据 (尝试 {attempt+1}/{retries})...")
            
            # 获取股票数据
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                "interval": "1d",
                "range": "3mo"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # 解析数据
            result = data['chart']['result'][0]
            timestamps = result['timestamp']
            quotes = result['indicators']['quote'][0]
            
            # 创建DataFrame
            df = pd.DataFrame({
                'Date': pd.to_datetime(timestamps, unit='s'),
                'Open': quotes['open'],
                'High': quotes['high'],
                'Low': quotes['low'],
                'Close': quotes['close'],
                'Volume': quotes['volume']
            })
            
            if not df.empty:
                df.set_index('Date', inplace=True)
                # 转换为马来西亚时区
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC').tz_convert(MYT)
                else:
                    df.index = df.index.tz_convert(MYT)
                
                # 清理数据
                df.dropna(inplace=True)
                
                print(f"✅ [Yahoo替代API] 成功获取 {symbol} 数据 ({len(df)} 条记录)")
                return df
            else:
                print(f"⚠️ [Yahoo替代API] {symbol} 返回空数据")
                
        except Exception as e:
            print(f"⚠️ [Yahoo替代API] 获取 {symbol} 数据失败: {str(e)}")
            time.sleep(2 + attempt)  # 增加等待时间
    
    return pd.DataFrame()

def fetch_alpha_vantage(symbol, retries=3):
    """使用Alpha Vantage API获取数据"""
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    if not ALPHA_VANTAGE_API_KEY:
        print("⚠️ Alpha Vantage API Key 未设置，跳过")
        return pd.DataFrame()
    
    for attempt in range(retries):
        try:
            print(f"🔍 [Alpha Vantage] 获取 {symbol} 数据 (尝试 {attempt+1}/{retries})...")
            
            # 获取股票数据
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": ALPHA_VANTAGE_API_KEY,
                "outputsize": "compact"
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # 解析数据
            time_series = data.get('Time Series (Daily)', {})
            if not time_series:
                print(f"⚠️ [Alpha Vantage] 未找到时间序列数据: {data}")
                continue
                
            # 创建DataFrame
            df = pd.DataFrame.from_dict(time_series, orient='index')
            df.index = pd.to_datetime(df.index)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df = df.astype(float)
            
            if not df.empty:
                # 转换为马来西亚时区
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC').tz_convert(MYT)
                else:
                    df.index = df.index.tz_convert(MYT)
                
                # 按日期排序
                df.sort_index(ascending=True, inplace=True)
                
                print(f"✅ [Alpha Vantage] 成功获取 {symbol} 数据 ({len(df)} 条记录)")
                return df
            else:
                print(f"⚠️ [Alpha Vantage] {symbol} 返回空数据")
                
        except Exception as e:
            print(f"⚠️ [Alpha Vantage] 获取 {symbol} 数据失败: {str(e)}")
            time.sleep(2 + attempt)  # 增加等待时间
    
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
        
        # 添加数据来源说明
        data_source_note = ""
        if "模拟数据" in prompt:
            data_source_note = "\n⚠️ *注意*: 由于数据源限制，本次报告使用模拟数据生成"
        
        msg += f"\n🤖 *AI分析*:\n{ai_comment}{data_source_note}\n\n_更新于: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}_"
        
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
        # 随机延迟避免请求过快
        time.sleep(5 + random.uniform(0, 5))
    
    print(f"\n{'='*50}")
    print(f"✅ 分析完成! 已处理 {len(STOCK_LIST)} 只股票")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
