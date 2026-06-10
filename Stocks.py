import efinance as ef
import time
import os
import pandas as pd

# ====================== 你的持仓数据（在这里改）======================
# holdings = {
#     "300323": {"name": "华灿光电", "buy_price": 16.1614, "shares": 1600},
#     "600740": {"name": "山西焦化", "buy_price": 4.1541, "shares": 1800},
#     "000751": {"name": "锌业股份", "buy_price": 4.8581, "shares": 4300},
#     "601990": {"name": "南京证券", "buy_price": 9.9227, "shares": 500},
#     "6000059": {"name": "古越龙山", "buy_price": 10.9008, "shares": 1000},
#     "000019": {"name": "深粮控股", "buy_price": 9.6507, "shares": 1000},
#     "601179": {"name": "中国西电", "buy_price": 20.12, "shares": 700},
#     "603258": {"name": "电魂网络", "buy_price": 20.6888, "shares": 900},
#     "600422": {"name": "昆药集团", "buy_price": 21.0619, "shares": 600},
#     "600879": {"name": "航天电子", "buy_price": 326.2661, "shares": 700},
#     "601066": {"name": "中信建投", "buy_price": 27.6302, "shares": 3400},
#     "002716": {"name": "湖南白银", "buy_price": 19.3681, "shares": 1000},
#     "300589": {"name": "江龙船艇", "buy_price": 228225, "shares": 1200},
#     "300129": {"name": "泰胜风能", "buy_price": 14.9016, "shares": 2300}
# }

holdings = {
    "300323": {"name": "华灿光电", "buy_price": 16.1614, "shares": 1600}
}
# =====================================================================

my_codes = list(holdings.keys())

# Pandas 中文对齐
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

while True:
    os.system("cls")
    try:
        # 1. 拿实时行情
        df = ef.stock.get_realtime_quotes()
        df = df[df["股票代码"].isin(my_codes)]

        # 关键修复：替换为实际的"昨日收盘价"列名（先通过调试代码确认）
        # 这里假设实际列名是"昨日收盘价"，你可根据打印结果修改
        df = df[["股票代码", "股票名称", "最新价", "昨日收盘价"]].copy()
        # 重命名列（统一为"昨收"，避免后续代码修改）
        df.rename(columns={"昨日收盘价": "昨收"}, inplace=True)

        # 2. 插入持仓与成本数据
        df["购入价"] = df["股票代码"].map(lambda x: holdings[x]["buy_price"])
        df["持仓数"] = df["股票代码"].map(lambda x: holdings[x]["shares"])

        # 3. 数值类型转换
        df["最新价"] = pd.to_numeric(df["最新价"])
        df["昨收"] = pd.to_numeric(df["昨收"])
        df["购入价"] = pd.to_numeric(df["购入价"])
        df["持仓数"] = pd.to_numeric(df["持仓数"])

        # 4. 计算各盈亏列
        df["总成本"] = df["购入价"] * df["持仓数"]
        df["当前市值"] = df["最新价"] * df["持仓数"]
        df["总盈亏_元"] = df["当前市值"] - df["总成本"]
        df["总盈亏率_%"] = (df["总盈亏_元"] / df["总成本"]) * 100

        # 当日盈亏（对比昨收）
        df["当日盈亏_元"] = (df["最新价"] - df["昨收"]) * df["持仓数"]
        df["当日盈亏率_%"] = ((df["最新价"] - df["昨收"]) / df["昨收"]) * 100

        # 5. 保留两位小数
        cols_round = ["最新价", "昨收", "购入价", "总成本", "当前市值",
                      "总盈亏_元", "总盈亏率_%", "当日盈亏_元", "当日盈亏率_%"]
        df[cols_round] = df[cols_round].round(2)

        # 6. 打印（对齐 + 颜色）
        print("=" * 110)
        print(f"{'代码':<8}{'名称':<10}{'最新价':>8}{'购入价':>8}{'持仓数':>8}"
              f"{'总盈亏(元)':>12}{'总盈亏率':>10}{'当日盈亏(元)':>12}{'当日盈亏率':>10}")
        print("-" * 110)

        for _, row in df.iterrows():
            # 颜色：红涨绿跌
            color_total = "\033[32m" if row["总盈亏_元"] >= 0 else "\033[31m"
            color_daily = "\033[32m" if row["当日盈亏_元"] >= 0 else "\033[31m"
            reset = "\033[0m"

            print(f"{row['股票代码']:<8}"
                  f"{row['股票名称']:<10}"
                  f"{row['最新价']:>8.2f}"
                  f"{row['购入价']:>8.2f}"
                  f"{row['持仓数']:>8.0f}"
                  f"{color_total}{row['总盈亏_元']:>12.2f}{reset}"
                  f"{color_total}{row['总盈亏率_%']:>9.2f}%{reset}"
                  f"{color_daily}{row['当日盈亏_元']:>12.2f}{reset}"
                  f"{color_daily}{row['当日盈亏率_%']:>9.2f}%{reset}")

        # 7. 汇总行
        total_cost = df["总成本"].sum()
        total_value = df["当前市值"].sum()
        total_pnl = df["总盈亏_元"].sum()
        total_daily_pnl = df["当日盈亏_元"].sum()
        total_pnl_rate = (total_pnl / total_cost) * 100 if total_cost != 0 else 0

        print("-" * 110)
        print(f"{'合计':<8}{'':<10}{'':>8}{'':>8}{'':>8}"
              f"{total_pnl:>12.2f}{total_pnl_rate:>9.2f}%{total_daily_pnl:>12.2f}{'':>10}")
        print("=" * 110)

    except Exception as e:
        print("异常：", e)
        # 可选：打印当前DataFrame的列名，方便调试
        # print("当前列名：", df.columns.tolist())

    time.sleep(30)
