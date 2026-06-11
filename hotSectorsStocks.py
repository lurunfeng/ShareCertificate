#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查询当日最热板块（行业/概念）以及涨幅前十的股票
数据源：东方财富（通过 AKShare）
"""

import akshare as ak
import pandas as pd
from datetime import datetime

# ================== 配置 ==================
pd.set_option('display.max_rows', 20)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 200)
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

# ================== 核心函数 ==================

def get_top_industry_sectors(top_n=10):
    """获取涨幅靠前的行业板块"""
    try:
        # 获取行业板块实时行情（东方财富）
        df = ak.stock_board_industry_name_em()
        # 按涨跌幅降序排序
        df = df.sort_values(by="涨跌幅", ascending=False)
        # 选择关键列并重命名
        result = df[["板块名称", "最新价", "涨跌幅", "涨跌额", "总市值", "换手率"]].head(top_n)
        return result
    except Exception as e:
        print(f"获取行业板块数据失败: {e}")
        return None

def get_top_concept_sectors(top_n=10):
    """获取涨幅靠前的概念板块"""
    try:
        df = ak.stock_board_concept_name_em()
        df = df.sort_values(by="涨跌幅", ascending=False)
        result = df[["板块名称", "最新价", "涨跌幅", "涨跌额", "总市值", "换手率"]].head(top_n)
        return result
    except Exception as e:
        print(f"获取概念板块数据失败: {e}")
        return None

def get_top_stocks(top_n=10):
    """获取全市场涨幅最高的前N只股票"""
    try:
        # 获取A股实时行情（含北交所）
        df = ak.stock_zh_a_spot_em()
        # 涨跌幅列可能名为 "涨跌幅" 或 "涨幅"
        change_col = "涨跌幅" if "涨跌幅" in df.columns else "涨幅"
        df = df.sort_values(by=change_col, ascending=False)
        # 选择关键列
        result = df[["代码", "名称", "最新价", change_col, "成交量", "成交额", "振幅"]].head(top_n)
        # 重命名涨跌幅列名统一
        result = result.rename(columns={change_col: "涨跌幅(%)"})
        return result
    except Exception as e:
        print(f"获取个股数据失败: {e}")
        return None

def save_to_csv(data, filename):
    """保存数据到CSV文件（可选）"""
    if data is not None and not data.empty:
        data.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"数据已保存至: {filename}")

# ================== 主程序 ==================

def main():
    print("=" * 80)
    print(f"          当日热点板块 & 涨幅前十股票  ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 80)

    # 1. 行业板块 TOP10
    print("\n🔥【行业板块涨幅榜 TOP10】")
    industry_df = get_top_industry_sectors(10)
    if industry_df is not None:
        print(industry_df.to_string(index=False))
        save_to_csv(industry_df, f"industry_top10_{datetime.now().strftime('%Y%m%d')}.csv")

    # 2. 概念板块 TOP10
    print("\n🔥【概念板块涨幅榜 TOP10】")
    concept_df = get_top_concept_sectors(10)
    if concept_df is not None:
        print(concept_df.to_string(index=False))
        save_to_csv(concept_df, f"concept_top10_{datetime.now().strftime('%Y%m%d')}.csv")

    # 3. 全市场涨幅前十股票
    print("\n📈【全市场涨幅前十股票】")
    stocks_df = get_top_stocks(10)
    if stocks_df is not None:
        print(stocks_df.to_string(index=False))
        save_to_csv(stocks_df, f"stocks_top10_{datetime.now().strftime('%Y%m%d')}.csv")

    print("\n✅ 查询完成！")

if __name__ == "__main__":
    main()