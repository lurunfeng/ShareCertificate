import efinance as ef
import time
import os
import pandas as pd
import random
import requests
import re

# ====================== 持仓数据 ======================
holdings = {
    "300323": {"name": "华灿光电", "buy_price": 16.6114, "shares": 1600},
    "600740": {"name": "山西焦化", "buy_price": 4.1541, "shares": 1800},
    "000751": {"name": "锌业股份", "buy_price": 4.8581, "shares": 4300},
    "601990": {"name": "南京证券", "buy_price": 9.9227, "shares": 500},
    "600059": {"name": "古越龙山", "buy_price": 10.9008, "shares": 1000},
    "000019": {"name": "深粮控股", "buy_price": 9.6507, "shares": 1000},
    "601179": {"name": "中国西电", "buy_price": 20.12, "shares": 700},
    "603258": {"name": "电魂网络", "buy_price": 20.6888, "shares": 900},
    "600422": {"name": "昆药集团", "buy_price": 21.0619, "shares": 600},
    "600879": {"name": "航天电子", "buy_price": 26.2661, "shares": 700},
    "601066": {"name": "中信建投", "buy_price": 27.6302, "shares": 3400},
    "002716": {"name": "湖南白银", "buy_price": 19.3681, "shares": 1000},
    "300589": {"name": "江龙船艇", "buy_price": 22.8225, "shares": 1200},
    "300129": {"name": "泰胜风能", "buy_price": 14.9016, "shares": 2300}
}
my_codes = list(holdings.keys())
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

def get_display_width(s):
    """计算字符串的显示宽度（中文算2，英文算1）"""
    width = 0
    for ch in str(s):
        if '\u4e00' <= ch <= '\u9fff':
            width += 2
        else:
            width += 1
    return width

def extract_code_from_line(line):
    """从 var hq_str_sh600000 中提取原始股票代码 600000"""
    match = re.search(r'hq_str_(sh\d+|sz\d+)', line)
    if match:
        code = match.group(1)
        return code[2:]
    return None

def fetch_data_with_retry(max_retries=3, retry_delay=5):
    for attempt in range(max_retries):
        try:
            sina_codes = []
            for code in my_codes:
                if code.startswith('6'):
                    sina_codes.append(f"sh{code}")
                elif code.startswith(('0', '3')):
                    sina_codes.append(f"sz{code}")
                else:
                    print(f"未知代码前缀: {code}")
                    continue
            codes_str = ",".join(sina_codes)

            timestamp = int(time.time() * 1000)
            url = f"https://hq.sinajs.cn/rn={timestamp}&list={codes_str}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://finance.sina.com.cn"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'gbk'

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")

            rows = []
            for line in response.text.strip().split("\n"):
                if not line.strip():
                    continue
                match = re.search(r'="(.*)"', line)
                if not match:
                    continue
                data_str = match.group(1)
                fields = data_str.split(",")

                if len(fields) >= 32:
                    stock_code = extract_code_from_line(line)
                    if stock_code is None:
                        continue
                    try:
                        rows.append({
                            "股票代码": stock_code,
                            "股票名称": fields[0],
                            "最新价": float(fields[3]),
                            "昨日收盘价": float(fields[2])
                        })
                    except (ValueError, IndexError) as e:
                        print(f"数据转换错误 {stock_code}: {e}")
                        continue
                else:
                    print(f"字段数异常: {len(fields)}")

            if not rows:
                raise Exception("未解析到任何股票数据")

            df = pd.DataFrame(rows)
            df = df[df["股票代码"].isin(my_codes)]
            return df

        except Exception as e:
            print(f"新浪接口请求失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    raise Exception("新浪接口获取失败")

# ====================== 主循环 ======================
while True:
    request_interval = random.uniform(60, 120)
    time.sleep(request_interval)

    os.system("cls")
    try:
        print(f"正在请求数据... (下次请求将在 {request_interval:.0f} 秒后)")
        df = fetch_data_with_retry()

        # 添加持仓信息
        df["购入价"] = df["股票代码"].map(lambda x: holdings[x]["buy_price"])
        df["持仓数"] = df["股票代码"].map(lambda x: holdings[x]["shares"])

        # 数值转换
        df["最新价"] = pd.to_numeric(df["最新价"])
        df["昨日收盘价"] = pd.to_numeric(df["昨日收盘价"])
        df["购入价"] = pd.to_numeric(df["购入价"])
        df["持仓数"] = pd.to_numeric(df["持仓数"])

        # 计算盈亏
        df["总成本"] = df["购入价"] * df["持仓数"]
        df["当前市值"] = df["最新价"] * df["持仓数"]
        df["总盈亏_元"] = df["当前市值"] - df["总成本"]
        df["总盈亏率_%"] = (df["总盈亏_元"] / df["总成本"]) * 100

        df["当日盈亏_元"] = (df["最新价"] - df["昨日收盘价"]) * df["持仓数"]
        df["当日盈亏率_%"] = ((df["最新价"] - df["昨日收盘价"]) / df["昨日收盘价"]) * 100

        # 保留两位小数
        cols_round = ["最新价", "昨日收盘价", "购入价", "总成本", "当前市值",
                      "总盈亏_元", "总盈亏率_%", "当日盈亏_元", "当日盈亏率_%"]
        df[cols_round] = df[cols_round].round(2)

        # ---------- 新增：按总盈亏金额降序排序（盈利在前） ----------
        df = df.sort_values(by="总盈亏_元", ascending=False)

        # ---------- 动态计算列宽 ----------
        display_cols = ["股票代码", "股票名称", "最新价", "购入价", "持仓数", "总盈亏_元", "总盈亏率_%", "当日盈亏_元", "当日盈亏率_%"]
        headers = {
            "股票代码": "代码",
            "股票名称": "名称",
            "最新价": "最新价",
            "购入价": "购入价",
            "持仓数": "持仓数",
            "总盈亏_元": "总盈亏(元)",
            "总盈亏率_%": "总盈亏率",
            "当日盈亏_元": "当日盈亏(元)",
            "当日盈亏率_%": "当日盈亏率"
        }

        col_widths = {}
        for col in display_cols:
            header_text = headers[col]
            header_width = get_display_width(header_text)
            if col in ["最新价", "购入价", "总盈亏_元", "当日盈亏_元"]:
                max_data = df[col].apply(lambda x: get_display_width(f"{x:.2f}")).max()
            elif col in ["总盈亏率_%", "当日盈亏率_%"]:
                max_data = df[col].apply(lambda x: get_display_width(f"{x:.2f}%")).max()
            elif col == "持仓数":
                max_data = df[col].apply(lambda x: get_display_width(f"{x:.0f}")).max()
            else:
                max_data = df[col].astype(str).apply(get_display_width).max()
            col_widths[col] = max(header_width, max_data) + 1

        total_width = sum(col_widths.values())
        print("=" * total_width)

        # 打印表头
        header_line = ""
        for col in display_cols:
            header_text = headers[col]
            if col in ["最新价", "购入价", "总盈亏_元", "总盈亏率_%", "当日盈亏_元", "当日盈亏率_%"]:
                header_line += f"{header_text:>{col_widths[col]}}"
            else:
                header_line += f"{header_text:<{col_widths[col]}}"
        print(header_line)
        print("-" * total_width)

        # 打印数据行
        for _, row in df.iterrows():
            color_total = "\033[32m" if row["总盈亏_元"] >= 0 else "\033[31m"
            color_daily = "\033[32m" if row["当日盈亏_元"] >= 0 else "\033[31m"
            reset = "\033[0m"

            line = f"{row['股票代码']:<{col_widths['股票代码']}}"
            line += f"{row['股票名称']:<{col_widths['股票名称']}}"
            line += f"{row['最新价']:>{col_widths['最新价']}.2f}"
            line += f"{row['购入价']:>{col_widths['购入价']}.2f}"
            line += f"{row['持仓数']:>{col_widths['持仓数']}.0f}"
            line += f"{color_total}{row['总盈亏_元']:>{col_widths['总盈亏_元']}.2f}{reset}"
            line += f"{color_total}{row['总盈亏率_%']:>{col_widths['总盈亏率_%']}.2f}%{reset}"
            line += f"{color_daily}{row['当日盈亏_元']:>{col_widths['当日盈亏_元']}.2f}{reset}"
            line += f"{color_daily}{row['当日盈亏率_%']:>{col_widths['当日盈亏率_%']}.2f}%{reset}"
            print(line)

        # 合计行
        total_cost = df["总成本"].sum()
        total_pnl = df["总盈亏_元"].sum()
        total_daily_pnl = df["当日盈亏_元"].sum()
        total_pnl_rate = (total_pnl / total_cost) * 100 if total_cost != 0 else 0

        total_line = f"{'合计':<{col_widths['股票代码']}}"
        total_line += f"{'':<{col_widths['股票名称']}}"
        total_line += f"{'':>{col_widths['最新价']}}"
        total_line += f"{'':>{col_widths['购入价']}}"
        total_line += f"{'':>{col_widths['持仓数']}}"
        total_line += f"{total_pnl:>{col_widths['总盈亏_元']}.2f}"
        total_line += f"{total_pnl_rate:>{col_widths['总盈亏率_%']}.2f}%"
        total_line += f"{total_daily_pnl:>{col_widths['当日盈亏_元']}.2f}"
        total_line += f"{'':>{col_widths['当日盈亏率_%']}}"
        print("-" * total_width)
        print(total_line)
        print("=" * total_width)
        print("数据获取成功!")

    except Exception as e:
        print(f"数据获取失败: {e}")
        time.sleep(30)