#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查询当日全市场涨幅超过指定阈值（默认5%）的股票
数据源：新浪财经（涨跌幅排名接口）
显示全部符合条件的股票，不截断
"""

import time
import requests
import pandas as pd
from datetime import datetime

# ================== 配置 ==================
THRESHOLD = 5      # 涨幅阈值（%）

# pandas 显示配置：不限制最大行数，不限制列宽
pd.set_option('display.max_rows', None)       # 显示所有行
pd.set_option('display.max_columns', None)    # 显示所有列
pd.set_option('display.width', 200)           # 控制台宽度
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

# ================== 新浪接口 ==================
def fetch_top_gainers(page=1, num=80):
    """
    获取新浪财经的涨跌幅排名数据（从高到低）
    page: 页码
    num: 每页数量（最大80）
    返回 DataFrame，包含代码、名称、最新价、涨跌幅等
    """
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {
        "page": page,
        "num": num,
        "sort": "changepercent",   # 按涨跌幅排序
        "asc": 0,                  # 降序
        "node": "hs_a",            # 沪深A股
        "_s_r_a": "init"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn"
    }
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.encoding = "gbk"
    text = resp.text.strip()
    if not text.startswith('['):
        raise Exception("接口返回格式异常")
    import json
    data = json.loads(text)
    if not data:
        return None
    df = pd.DataFrame(data)
    df = df.rename(columns={
        "symbol": "代码",
        "name": "名称",
        "trade": "最新价",
        "changepercent": "涨跌幅",
        "volume": "成交量",
        "amount": "成交额",
        "turnoverratio": "换手率"
    })
    # 数值转换
    df["最新价"] = pd.to_numeric(df["最新价"], errors="coerce")
    df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
    df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")
    df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")
    return df

def get_all_gainers(threshold=5, max_pages=20):
    """
    通过分页获取所有涨幅超过 threshold 的股票
    """
    all_stocks = []
    page = 1
    while True:
        print(f"  正在获取第 {page} 页...")
        df_page = fetch_top_gainers(page=page, num=80)
        if df_page is None or df_page.empty:
            break
        # 筛选涨幅 > threshold
        mask = df_page["涨跌幅"] > threshold
        gainers = df_page[mask]
        if gainers.empty:
            break
        all_stocks.append(gainers)
        # 如果当前页不足80只，说明已是最后一页
        if len(df_page) < 80:
            break
        page += 1
        if page > max_pages:
            break
        time.sleep(0.5)  # 礼貌间隔
    if not all_stocks:
        return None
    return pd.concat(all_stocks, ignore_index=True)

def main():
    print("=" * 80)
    print(f"         全市场涨幅超过 {THRESHOLD}% 的股票查询  ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 80)

    try:
        print("\n正在获取涨跌幅排名数据（新浪财经）...")
        gain_df = get_all_gainers(threshold=THRESHOLD, max_pages=20)

        if gain_df is None or gain_df.empty:
            print(f"\n📉 当前全市场没有涨幅超过 {THRESHOLD}% 的股票。")
            return

        # 按涨幅降序
        gain_df = gain_df.sort_values(by="涨跌幅", ascending=False)
        total = len(gain_df)
        print(f"\n🔥 涨幅超过 {THRESHOLD}% 的股票共 {total} 只，全部显示如下：\n")

        # 格式化输出列
        out_df = gain_df[["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额", "换手率"]].copy()
        out_df["最新价"] = out_df["最新价"].map(lambda x: f"{x:.2f}")
        out_df["涨跌幅"] = out_df["涨跌幅"].map(lambda x: f"{x:.2f}%")
        out_df["成交量"] = out_df["成交量"].map(lambda x: f"{x:.0f}")
        out_df["成交额"] = out_df["成交额"].map(lambda x: f"{x:.2f}")
        out_df["换手率"] = out_df["换手率"].map(lambda x: f"{x:.2f}%")

        # 打印全部（pandas 会因 max_rows=None 而打印全部）
        print(out_df.to_string(index=False))

        print("\n✅ 查询完成！")

    except Exception as e:
        print(f"\n❌ 程序运行失败: {e}")
        print("可能原因：网络问题或新浪接口变更。请稍后重试。")

if __name__ == "__main__":
    main()