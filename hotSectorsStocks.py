import os
import time
import random
import akshare as ak
import pandas as pd

# 全局禁用代理，解决网络连接中断问题
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

# 全局配置
RETRY_TIMES = 3  # 接口最大重试次数
BASE_SLEEP = 2  # 基础休眠秒数


def fetch_with_retry(func):
    """通用重试函数 + 随机延时，规避反爬，不再传入timeout参数"""
    for idx in range(RETRY_TIMES):
        try:
            # 随机延时 2~4秒，模拟人工访问，降低限流概率
            time.sleep(BASE_SLEEP + random.random() * 2)
            return func()
        except Exception as e:
            print(f"第{idx + 1}次请求失败: {str(e)}")
            time.sleep(BASE_SLEEP * (idx + 1))
    print("多次重试失败，跳过当前接口")
    return pd.DataFrame()


def safe_convert_num(x):
    """安全数值转换，过滤列表、空值、异常字符"""
    if isinstance(x, (list, dict)):
        return float("nan")
    try:
        return float(str(x).strip())
    except (ValueError, TypeError):
        return float("nan")


def get_top10_industry_sector():
    """获取东方财富行业板块 当日涨幅TOP10"""
    # 板块列表接口：不支持任何额外参数，直接调用
    df_sector = fetch_with_retry(ak.stock_board_industry_name_em)
    if df_sector.empty:
        return pd.DataFrame()

    # 清洗涨跌幅字段
    df_sector["涨跌幅"] = df_sector["涨跌幅"].apply(safe_convert_num)
    # 剔除无效数据
    df_sector = df_sector.dropna(subset=["涨跌幅"])
    df_sector = df_sector[df_sector["涨跌幅"] != 0]
    if df_sector.empty:
        print("无有效板块数据")
        return pd.DataFrame()

    # 按涨幅降序，取前10名
    df_sector = df_sector.sort_values(by="涨跌幅", ascending=False)
    top10 = df_sector.head(10).reset_index(drop=True)
    return top10[["板块名称", "涨跌幅"]]


def get_sector_top10_stocks(sector_name):
    """根据板块名称，获取板块内涨幅TOP10个股"""

    # 成分股接口：仅传入板块名称，不使用timeout
    def get_stock_data():
        return ak.stock_board_industry_cons_em(symbol=sector_name)

    df_stock = fetch_with_retry(get_stock_data)
    if df_stock.empty:
        return pd.DataFrame()

    # 清洗价格、涨跌幅
    df_stock["涨跌幅"] = df_stock["涨跌幅"].apply(safe_convert_num)
    df_stock["最新价"] = df_stock["最新价"].apply(safe_convert_num)

    # 过滤无效数据
    df_stock = df_stock.dropna(subset=["涨跌幅", "最新价"])
    if df_stock.empty:
        return pd.DataFrame()

    # 按涨幅降序取前10
    df_stock = df_stock.sort_values(by="涨跌幅", ascending=False)
    top10_stock = df_stock.head(10).reset_index(drop=True)
    return top10_stock[["代码", "名称", "最新价", "涨跌幅"]]


if __name__ == "__main__":
    print("=" * 65)
    print("📈 A股行业板块涨幅TOP10监控（东方财富数据源）")
    print("=" * 65)

    # 1. 获取涨幅前十板块
    top_sectors = get_top10_industry_sector()
    if top_sectors.empty:
        print("❌ 未能获取板块数据，请检查网络或在A股交易时段(9:30-15:00)运行")
    else:
        # 遍历每个TOP10板块
        for rank, row in top_sectors.iterrows():
            current_rank = rank + 1
            board_name = row["板块名称"]
            board_change = row["涨跌幅"]

            print(f"\n【第{current_rank}名】板块：{board_name} | 板块涨幅：{board_change:.2f}%")
            print("-" * 55)

            # 2. 获取板块内涨幅前十个股
            stock_list = get_sector_top10_stocks(board_name)
            if stock_list.empty:
                print("  暂无有效个股数据")
                continue

            # 打印个股信息
            for s_rank, s_row in stock_list.iterrows():
                s_num = s_rank + 1
                code = s_row["代码"]
                name = s_row["名称"]
                price = s_row["最新价"]
                change = s_row["涨跌幅"]
                print(f"  {s_num}. {code} {name:8s} | 现价:{price:6.2f} | 涨幅:{change:+.2f}%")

    print("\n" + "=" * 65)
    print("✅ 本轮数据采集完成")