import efinance as ef
import pandas as pd
import time
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

def safe_get_stock_data(stock_code: str, start_date: str, end_date: str, max_try=5):
    base_delay = 2
    for attempt in range(max_try):
        try:
            time.sleep(random.uniform(0.8, 2))
            # 获取前复权日线
            df = ef.stock.get_quote_history(stock_code, beg=start_date, end=end_date, adjust='qfq')
            if not df.empty:
                # 统一列名对齐
                df = df.rename(columns={
                    '日期': '日期',
                    '开盘': '开盘',
                    '收盘': '收盘',
                    '最高': '最高',
                    '最低': '最低',
                    '成交量': '成交量'
                })
                return df
        except Exception as e:
            if attempt == max_try - 1:
                print(f"重试{max_try}次全部失败: {e}")
                return None
            wait = base_delay * (2 ** attempt) + random.uniform(0,1)
            print(f"请求失败，第{attempt+1}次重试，等待{wait:.2f}s")
            time.sleep(wait)
    return None

def stock_price_analysis(stock_code: str):
    # 动态计算3年区间
    today = datetime.now()
    end_date = today.strftime("%Y%m%d")
    start_date = (today - relativedelta(years=3)).strftime("%Y%m%d")
    print(f"\n===== 数据查询区间：{start_date} ~ {end_date} =====")

    df_total = safe_get_stock_data(stock_code, start_date, end_date)
    if df_total is None or df_total.empty:
        print("未获取行情数据，检查代码/网络后重试！")
        return None, None, None

    df_total = df_total.sort_values("日期").reset_index(drop=True)

    # 1. 最近30个交易日
    df_30d = df_total.tail(30).copy()
    print("\n" + "=" * 60)
    print(f"【{stock_code} 最近30个交易日价格】")
    print(df_30d[["日期", "开盘", "收盘", "最高", "最低"]])

    # 2. 近三年日内最低价最小20个
    low_series = df_total["最低"]
    top20_low = low_series.nsmallest(20).sort_values(ascending=True)
    print("\n" + "=" * 60)
    print("【近三年日内最低价，最小20个价格（升序）】")
    print(top20_low.reset_index(drop=True))

    # 3. 20个最低价对应完整行情
    low_values = top20_low.values
    df_low20 = df_total[df_total["最低"].isin(low_values)].sort_values("最低").reset_index(drop=True)
    print("\n" + "=" * 60)
    print("【20个最低价对应的日期与行情】")
    print(df_low20[["日期", "最低", "收盘", "成交量"]])

    return df_30d, top20_low, df_low20

if __name__ == "__main__":
    target_code = "600982"
    stock_price_analysis(target_code)