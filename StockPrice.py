import akshare as ak
import pandas as pd
import mplfinance as mpf
import numpy as np
import time
from requests.exceptions import ConnectionError

STOCK_CODE = "300323"
PERIOD = "daily"
START_DATE = "20260610"
IS_FIRST_PLOT = True  # 只画一次图


# 重试函数
def try_fetch(func, max_retry=3):
    err = None
    for i in range(max_retry):
        try:
            res = func()
            return res
        except Exception as e:
            err = e
            time.sleep((i + 1) * 1)
    raise err


# 获取实时价格（雪球单票，最稳）
def get_real_price(code):
    try:
        df_xq = try_fetch(lambda: ak.stock_individual_spot_xq(symbol=code))
        return round(float(df_xq["现价"].iloc[0]), 2)
    except:
        pass

    # 兜底：分时
    try:
        df_min = try_fetch(lambda: ak.stock_intraday_sina(symbol=code, date=time.strftime("%Y%m%d")))
        return round(df_min["成交"].iloc[-1], 2)
    except:
        pass

    # 最终兜底：日线收盘
    df_back = try_fetch(lambda: ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START_DATE, adjust="qfq"))
    return round(df_back["收盘"].iloc[-1], 2)


# 获取K线
def get_stock_data():
    df = try_fetch(lambda: ak.stock_zh_a_hist(symbol=STOCK_CODE, period=PERIOD, start_date=START_DATE, adjust="qfq"))
    df = df.iloc[:, :11]
    df.columns = ["date", "open", "close", "high", "low", "volume",
                  "amount", "amplitude", "change_pct", "change_amt", "turnover"]
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.index.name = "Date"
    return df


# 计算指标
def calculate_trend(df):
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    exp12 = df["close"].ewm(span=12, adjust=False).mean()
    exp26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = exp12 - exp26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


# 判断趋势
def judge_trend(df):
    df_clean = df.dropna()
    if len(df_clean) == 0:
        return "数据不足", "数据不足"
    last = df_clean.iloc[-1]
    trend = "⚪ 横盘震荡"
    signal = "观望"
    if last["ma5"] > last["ma10"] > last["ma20"] > last["ma60"]:
        trend = "🚀 强势上涨"
        signal = "买入/持有"
    elif last["ma5"] < last["ma10"] < last["ma20"] < last["ma60"]:
        trend = "📉 弱势下跌"
        signal = "卖出/空仓"
    if not np.isnan(last["rsi"]):
        if last["rsi"] > 70:
            signal = "超买，警惕回落"
        elif last["rsi"] < 30:
            signal = "超卖，可关注抄底"
    return trend, signal


# 画图
def plot_chart(df):
    df_plot = df.dropna()
    if len(df_plot) == 0:
        print("数据不足无法绘图")
        return
    add_plot = [
        mpf.make_addplot(df_plot["ma5"], color="blue"),
        mpf.make_addplot(df_plot["ma10"], color="orange"),
        mpf.make_addplot(df_plot["ma20"], color="red"),
        mpf.make_addplot(df_plot["ma60"], color="green"),
    ]
    mpf.plot(df_plot, type="candle", style="yahoo", title=f"{STOCK_CODE}", addplot=add_plot, volume=True)


# ==================== 主循环（1分钟刷新）====================
if __name__ == "__main__":
    # 移除错误的 global 声明（IS_FIRST_PLOT 已是全局变量）
    print("📊 实时监控启动｜每60秒自动刷新｜Ctrl+C 停止")

    while True:
        try:
            real_price = get_real_price(STOCK_CODE)
            # df = get_stock_data()
            # df = calculate_trend(df)
            # trend, signal = judge_trend(df)
            # close_last = round(df.iloc[-1]["close"], 2)

            print("\n====== 趋势分析结果 ======")
            print(f"代码：{STOCK_CODE}")
            print(f"实时价格：{real_price}")
            print("当前时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
            # print(f"昨日收盘：{close_last}")
            # print(f"趋势判断：{trend}")
            # print(f"操作建议：{signal}")
            print("==========================\n")

            # 只第一次画图
            if IS_FIRST_PLOT:
                # plot_chart(df)
                IS_FIRST_PLOT = False  # 直接修改全局变量，无需声明

        except Exception as err:
            print(f"异常：{err}，等待下一轮...")

        time.sleep(60)