import time
import os
import pandas as pd
import random
import requests
import re
from wcwidth import wcswidth

# ====================== 持仓数据 ======================
holdings = {
    "300323": {"name": "华灿光电", "buy_price": 16.6164, "shares": 1600},
    "600740": {"name": "山西焦化", "buy_price": 4.1541, "shares": 1800},
    "000751": {"name": "锌业股份", "buy_price": 4.8581, "shares": 0},
    "601990": {"name": "南京证券", "buy_price": 9.9227, "shares": 500},
    "600059": {"name": "古越龙山", "buy_price": 10.9008, "shares": 1000},
    "000019": {"name": "深粮控股", "buy_price": 9.6507, "shares": 1000},
    "601179": {"name": "中国西电", "buy_price": 20.12, "shares": 700},
    "603258": {"name": "电魂网络", "buy_price": 20.6888, "shares": 900},
    "600422": {"name": "昆药集团", "buy_price": 21.0619, "shares": 600},
    "600879": {"name": "航天电子", "buy_price": 26.2661, "shares": 700},
    "601066": {"name": "中信建投", "buy_price": 27.6302, "shares": 3400},
    "002716": {"name": "湖南白银", "buy_price": 18.3681, "shares": 1000},
    "300589": {"name": "江龙船艇", "buy_price": 22.8225, "shares": 1200},
    "300129": {"name": "泰胜风能", "buy_price": 14.9016, "shares": 2300},
    "600172": {"name": "黄河旋风", "buy_price": 12.2123, "shares": 0},
    "600115": {"name": "东方航空", "buy_price": 3.8, "shares": 0},
    "600745": {"name": "闻泰科技", "buy_price": 18.6687, "shares": 800},
    "601398": {"name": "工商银行", "buy_price": 7.9, "shares": 0},
    "603399": {"name": "永衫锂电", "buy_price": 20.0, "shares": 0},
    "688055": {"name": "龙腾光电", "buy_price": 5.47, "shares": 0},
    "600598": {"name": "北大荒", "buy_price": 12.47, "shares": 0},
}
my_codes = list(holdings.keys())

# 颜色定义
RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# 固定列宽（单位：英文字符宽度，已经测试足够容纳所有内容）
# 可根据你的终端微调这些值
COL_WIDTHS = {
    "代码": 8,
    "名称": 10,
    "最新价": 8,
    "购入价": 8,
    "持仓数": 8,
    "总盈亏(元)": 10,
    "总盈亏率": 10,
    "当日盈亏(元)": 10,
    "当日盈亏率": 10,
}
HEADERS = ["代码", "名称", "最新价", "购入价", "持仓数", "总盈亏(元)", "总盈亏率", "当日盈亏(元)", "当日盈亏率"]


def visible_width(text):
    """计算字符串的实际显示宽度（忽略 ANSI 颜色代码）"""
    # 移除颜色代码
    clean = re.sub(r'\033\[[0-9;]*m', '', str(text))
    width = wcswidth(clean)
    return width if width >= 0 else len(clean)


def pad_cell(content, width, align='left'):
    """
    将单元格内容填充到指定显示宽度，支持内容中包含 ANSI 颜色代码。
    颜色代码不占用显示宽度，填充空格被添加到颜色代码之外。
    """
    # 计算可视宽度（不含颜色）
    cur_width = visible_width(content)
    pad = width - cur_width
    if pad <= 0:
        return content
    if align == 'left':
        # 内容后加空格
        return content + ' ' * pad
    else:
        # 内容前加空格（右对齐）
        return ' ' * pad + content


def color_num(value, fmt="{:.2f}", suffix=""):
    """根据数值正负返回带颜色的字符串（正红负绿）"""
    if value > 0:
        color = RED
    elif value < 0:
        color = GREEN
    else:
        return f"{fmt.format(value)}{suffix}"
    return f"{color}{fmt.format(value)}{suffix}{RESET}"


def extract_code_from_line(line):
    match = re.search(r'hq_str_(sh\d+|sz\d+)', line)
    if match:
        return match.group(1)[2:]
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
            codes_str = ",".join(sina_codes)
            timestamp = int(time.time() * 1000)
            url = f"https://hq.sinajs.cn/rn={timestamp}&list={codes_str}"
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = 'gbk'
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            rows = []
            for line in resp.text.strip().split("\n"):
                if not line.strip():
                    continue
                match = re.search(r'="(.*)"', line)
                if not match:
                    continue
                fields = match.group(1).split(",")
                if len(fields) >= 32:
                    code = extract_code_from_line(line)
                    if code is None:
                        continue
                    try:
                        rows.append({
                            "股票代码": code,
                            "股票名称": fields[0],
                            "最新价": float(fields[3]),
                            "昨日收盘价": float(fields[2])
                        })
                    except:
                        continue
            if not rows:
                raise Exception("无数据")
            df = pd.DataFrame(rows)
            df = df[df["股票代码"].isin(my_codes)]
            return df
        except Exception as e:
            print(f"请求失败 ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    raise Exception("获取数据失败")


# ====================== 主循环 ======================
while True:
    request_interval = random.uniform(45, 90)
    time.sleep(request_interval)
    os.system("cls")

    try:
        print(f"正在请求数据... (下次 {request_interval:.0f} 秒后)")
        df = fetch_data_with_retry()

        # 添加持仓数据
        df["购入价"] = df["股票代码"].map(lambda x: holdings[x]["buy_price"])
        df["持仓数"] = df["股票代码"].map(lambda x: holdings[x]["shares"])
        df["最新价"] = pd.to_numeric(df["最新价"])
        df["昨日收盘价"] = pd.to_numeric(df["昨日收盘价"])
        df["购入价"] = pd.to_numeric(df["购入价"])
        df["持仓数"] = pd.to_numeric(df["持仓数"])
        df["总成本"] = df["购入价"] * df["持仓数"]
        df["当前市值"] = df["最新价"] * df["持仓数"]
        df["总盈亏_元"] = df["当前市值"] - df["总成本"]
        df["总盈亏率_%"] = (df["总盈亏_元"] / df["总成本"]) * 100
        df["当日盈亏_元"] = (df["最新价"] - df["昨日收盘价"]) * df["持仓数"]
        df["当日盈亏率_%"] = ((df["最新价"] - df["昨日收盘价"]) / df["昨日收盘价"]) * 100

        # 保留两位小数
        for col in ["最新价", "购入价", "总盈亏_元", "总盈亏率_%", "当日盈亏_元", "当日盈亏率_%"]:
            df[col] = df[col].round(2)

        # 按总盈亏降序排序
        df = df.sort_values(by="总盈亏_元", ascending=False)

        # ----- 打印表头 -----
        header_line = ""
        for h in HEADERS:
            # 表头右移处理
            if h == "代码":
                display = "  代码"
            elif h == "名称":
                display = "  名称"
            elif h == "最新价":
                display = "    最新价"
            elif h == "购入价":
                display = "   购入价"
            elif h == "持仓数":
                display = "   持仓数"
            elif h == "总盈亏(元)":
                display = "   总盈亏(元)"
            elif h == "总盈亏率":
                display = "  总盈亏率"
            elif h == "当日盈亏(元)":
                display = " 当日盈亏(元)"
            elif h == "当日盈亏率":
                display = "  当日盈亏率"
            else:
                display = h
            align = 'left' if h in ["代码", "名称"] else 'right'
            header_line += pad_cell(display, COL_WIDTHS[h], align)
        total_width = sum(COL_WIDTHS.values())
        print("=" * total_width)
        print(header_line)
        print("-" * total_width)

        # ----- 打印数据行 -----
        for _, row in df.iterrows():
            # 构建每个单元格（带颜色）
            cells = []
            # 代码（无色）
            cells.append(pad_cell(row["股票代码"], COL_WIDTHS["代码"], 'left'))
            # 名称（无色）
            cells.append(pad_cell(row["股票名称"], COL_WIDTHS["名称"], 'left'))
            # 最新价（无色）
            cells.append(pad_cell(f"{row['最新价']:.2f}", COL_WIDTHS["最新价"], 'right'))
            # 购入价（无色）
            cells.append(pad_cell(f"{row['购入价']:.2f}", COL_WIDTHS["购入价"], 'right'))
            # 持仓数（无色）
            cells.append(pad_cell(f"{row['持仓数']:.0f}", COL_WIDTHS["持仓数"], 'right'))
            # 总盈亏(元)（带颜色）
            total_pnl_str = color_num(row["总盈亏_元"])
            cells.append(pad_cell(total_pnl_str, COL_WIDTHS["总盈亏(元)"], 'right'))
            # 总盈亏率（带颜色）
            total_rate_str = color_num(row["总盈亏率_%"], suffix="%")
            cells.append(pad_cell(total_rate_str, COL_WIDTHS["总盈亏率"], 'right'))
            # 当日盈亏(元)（带颜色）
            daily_pnl_str = color_num(row["当日盈亏_元"])
            cells.append(pad_cell(daily_pnl_str, COL_WIDTHS["当日盈亏(元)"], 'right'))
            # 当日盈亏率（带颜色）
            daily_rate_str = color_num(row["当日盈亏率_%"], suffix="%")
            cells.append(pad_cell(daily_rate_str, COL_WIDTHS["当日盈亏率"], 'right'))

            print("".join(cells))

        # ----- 合计行（无色）-----
        total_cost = df["总成本"].sum()
        total_pnl = df["总盈亏_元"].sum()
        total_daily_pnl = df["当日盈亏_元"].sum()
        total_pnl_rate = (total_pnl / total_cost) * 100 if total_cost != 0 else 0

        total_cells = [
            pad_cell("合计", COL_WIDTHS["代码"], 'left'),
            pad_cell("", COL_WIDTHS["名称"], 'left'),
            pad_cell("", COL_WIDTHS["最新价"], 'right'),
            pad_cell("", COL_WIDTHS["购入价"], 'right'),
            pad_cell("", COL_WIDTHS["持仓数"], 'right'),
            pad_cell(f"{total_pnl:.2f}", COL_WIDTHS["总盈亏(元)"], 'right'),
            pad_cell(f"{total_pnl_rate:.2f}%", COL_WIDTHS["总盈亏率"], 'right'),
            pad_cell(f"{total_daily_pnl:.2f}", COL_WIDTHS["当日盈亏(元)"], 'right'),
            pad_cell("", COL_WIDTHS["当日盈亏率"], 'right'),
        ]
        print("-" * total_width)
        print("".join(total_cells))
        print("=" * total_width)
        print("数据获取成功!")

    except Exception as e:
        print(f"错误: {e}")
        time.sleep(30)
