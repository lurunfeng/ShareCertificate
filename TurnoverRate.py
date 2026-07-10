"""
休市后查询当日换手率≥5%，数据源东方财富/新浪（自动轮换）
解决RemoteDisconnected远程断开，兼容低版本akshare
功能：分批读取缓存、高换手筛选、近5日K线、Excel多sheet导出
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import warnings
import requests
from requests.exceptions import ConnectionError, Timeout

warnings.filterwarnings("ignore")

# ==================== 配置区 ====================
TARGET_DATE = "2026-07-03"
TURNOVER_THRESHOLD = 5.0
HISTORY_DAYS = 5
RETRY_TIMES = 8
BASE_SLEEP = 5.0
RAND_SLEEP_RANGE = (2.0, 3.0)
BATCH_SIZE = 5
BATCH_INTERVAL_MIN = 60
BATCH_INTERVAL_MAX = 90

GLOBAL_SPOT_CACHE = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}

session = requests.Session()
session.headers.update(HEADERS)
requests.session = lambda: session

def check_trading_day(date_str: str) -> tuple[bool, str]:
    try:
        df = ak.tool_trade_date_hist_sina()
        trade_days = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d").tolist()
        if date_str in trade_days:
            return True, date_str
        print(f"❌ {date_str} 不是交易日，自动向前匹配最近日期")
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        for i in range(1, 10):
            check_dt = (target_dt - timedelta(days=i)).strftime("%Y-%m-%d")
            if check_dt in trade_days:
                print(f"✅ 切换有效交易日：{check_dt}")
                return True, check_dt
        print("❌ 近10天未查询到交易日")
        return False, date_str
    except Exception as e:
        print(f"⚠️ 交易日历接口异常，沿用原日期：{e}")
        return True, date_str

def find_column(df, keywords):
    """在DataFrame列名中查找包含任一关键词的列，返回第一个匹配的列名，否则返回None"""
    for col in df.columns:
        for kw in keywords:
            if kw in col or col.lower() in kw.lower():
                return col
    return None

def load_all_spot_cache(target_dt: str):
    global GLOBAL_SPOT_CACHE
    if GLOBAL_SPOT_CACHE is not None:
        return GLOBAL_SPOT_CACHE

    # 数据源列表
    sources = [
        ("东方财富", ak.stock_zh_a_spot_em),
        ("新浪", ak.stock_zh_a_spot),
    ]

    for source_name, source_func in sources:
        if source_func is None:
            print(f"⚠️ {source_name} 接口不可用，跳过")
            continue

        print(f"🔁 尝试 {source_name} 接口...")
        for rt in range(RETRY_TIMES):
            try:
                df = source_func()
                print(f"   {source_name} 返回列名: {list(df.columns)}")  # 调试信息

                # 查找代码列
                code_col = find_column(df, ["代码", "code", "symbol", "股票代码"])
                if code_col is None:
                    print(f"⚠️ {source_name} 无代码列，跳过")
                    break
                if code_col != "代码":
                    df.rename(columns={code_col: "代码"}, inplace=True)

                # 查找换手率列（模糊匹配）
                turnover_col = find_column(df, ["换手", "turnover", "turnoverratio", "换手率"])
                if turnover_col is None:
                    print(f"⚠️ {source_name} 无换手率字段，请检查列名: {list(df.columns)}")
                    break
                if turnover_col != "换手率":
                    df.rename(columns={turnover_col: "换手率"}, inplace=True)

                # 标准化代码类型
                df["代码"] = df["代码"].astype(str)
                # 转换换手率（可能带%）
                df["换手率"] = df["换手率"].astype(str).str.replace("%", "").str.strip()
                df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")

                # 判断单位：如果最大换手率 <= 1，则乘以100（视为小数）
                if not df["换手率"].isnull().all():
                    max_val = df["换手率"].max()
                    if max_val <= 1:
                        df["换手率"] = df["换手率"] * 100

                GLOBAL_SPOT_CACHE = df
                print(f"✅ {source_name} 缓存加载成功，合计{len(df)}只股票")
                return GLOBAL_SPOT_CACHE

            except (ConnectionError, Timeout, Exception) as e:
                wait = 5 * (rt + 1)
                err_msg = str(e)[:100]
                print(f"⚠️ {source_name} 第{rt+1}次失败，等待{wait}s重试：{err_msg}")
                time.sleep(wait)
        print(f"❌ {source_name} 多次失败，切换下一数据源")

    print("❌ 所有数据源均失败，请检查网络或稍后重试")
    print("💡 建议：切换网络环境（如手机热点）或使用代理后重试")
    return pd.DataFrame()

def get_single_spot(code: str, target_dt: str):
    df_cache = load_all_spot_cache(target_dt)
    if df_cache.empty:
        return None
    row = df_cache[df_cache["代码"] == code]
    if row.empty:
        return None
    return row.iloc[0].to_dict()

def get_all_stock_code() -> pd.DataFrame:
    print("📋 加载A股代码列表...")
    try:
        df = ak.stock_info_a_code_name()
    except Exception:
        print("⚠️ 主代码接口异常，切换备用接口")
        df = ak.stock_info_a_code_name_csindex()
    df.columns = ["代码", "名称"]
    df["代码"] = df["代码"].astype(str)
    df = df[df["代码"].str.match(r"^(60|00|30)\d{4}$")]
    print(f"✅ 筛选完成，共{len(df)}只A股")
    return df

def get_batch_spot_safe(batch_df: pd.DataFrame, batch_num: int, total_batches, target_dt):
    res_list = []
    fail_count = 0
    batch_size = len(batch_df)
    print(f"\n📦 处理第 {batch_num}/{total_batches} 批次，共{batch_size}只")
    for idx, row in batch_df.iterrows():
        code = row["代码"]
        name = row["名称"]
        spot_data = get_single_spot(code, target_dt)
        if spot_data is None:
            fail_count += 1
            if fail_count / batch_size > 0.6:
                print(f"❌ 本批次失败率过高，跳过剩余个股")
                break
            continue
        spot_data["代码"] = code
        spot_data["名称"] = name
        res_list.append(spot_data)
        sleep_sec = BASE_SLEEP + random.uniform(*RAND_SLEEP_RANGE)
        time.sleep(sleep_sec)
        if (idx + 1) % 4 == 0:
            print(f"  批次进度：{idx+1}/{batch_size} | 失败{fail_count}只")
    if not res_list:
        return pd.DataFrame()
    df_out = pd.DataFrame(res_list)
    print(f"✅ 批次完成：成功{len(res_list)}只，失败{fail_count}只")
    return df_out

def get_all_spot_safe(code_df: pd.DataFrame, target_dt: str):
    total_stocks = len(code_df)
    total_batches = (total_stocks + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\n🔄 分批遍历行情缓存，总{total_batches}批，每批{BATCH_SIZE}只")
    all_results = []
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min((batch_num + 1) * BATCH_SIZE, total_stocks)
        batch_data = code_df.iloc[start_idx:end_idx]
        batch_res = get_batch_spot_safe(batch_data, batch_num + 1, total_batches, target_dt)
        if not batch_res.empty:
            all_results.append(batch_res)
        if batch_num < total_batches - 1:
            wait_t = random.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX)
            if (batch_num + 1) % 10 == 0:
                extra = random.uniform(8, 15)
                wait_t += extra
                print(f"\n⏳ 累计10批，额外休息{extra:.1f}s，总等待{wait_t:.1f}s")
            else:
                print(f"\n⏳ 批次间隔等待 {wait_t:.1f} 秒")
            time.sleep(wait_t)
    if not all_results:
        return pd.DataFrame()
    return pd.concat(all_results, ignore_index=True)

def filter_by_turnover(df: pd.DataFrame):
    if "换手率" not in df.columns:
        print("❌ 数据缺失换手率字段，无法筛选")
        return pd.DataFrame()
    df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")
    df = df.dropna(subset=["换手率"])
    target_df = df[df["换手率"] >= TURNOVER_THRESHOLD].copy()
    target_df = target_df.sort_values("换手率", ascending=False)
    print(f"🎯 换手率≥{TURNOVER_THRESHOLD}% 共{len(target_df)}只股票")
    return target_df

def get_history_data(symbol: str, target_dt: str):
    try:
        end_dt = datetime.strptime(target_dt, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=HISTORY_DAYS * 5)
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=end_dt.strftime("%Y%m%d"),
            adjust=""
        )
        if df.empty:
            return pd.DataFrame()
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期", ascending=False).head(HISTORY_DAYS)
        df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")
        return df[["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "换手率"]]
    except Exception:
        return pd.DataFrame()

def fetch_history_batch(stock_df: pd.DataFrame, target_dt: str):
    out_dict = {}
    total = len(stock_df)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min((batch_num + 1) * BATCH_SIZE, total)
        batch_df = stock_df.iloc[start_idx:end_idx]
        print(f"\n📜 历史K线 第{batch_num+1}/{total_batches}批次")
        for idx, row in batch_df.iterrows():
            code = row["代码"]
            name = row["名称"]
            seq = start_idx + idx + 1
            print(f"[{seq}/{total}] 获取{code}历史行情")
            hist = get_history_data(code, target_dt)
            out_dict[code] = {"名称": name, "历史数据": hist}
            time.sleep(random.uniform(1.0, 1.8))
        if batch_num < total_batches - 1:
            wait_t = random.uniform(BATCH_INTERVAL_MIN//2, BATCH_INTERVAL_MAX//2)
            print(f"\n⏳ 历史批次等待{wait_t:.1f}秒")
            time.sleep(wait_t)
    return out_dict

def main():
    global TARGET_DATE
    print("=" * 70)
    print(f"目标日期:{TARGET_DATE} | 换手率≥{TURNOVER_THRESHOLD} | 回溯{HISTORY_DAYS}日")
    print(f"每批{BATCH_SIZE}只 | 间隔{BATCH_INTERVAL_MIN}~{BATCH_INTERVAL_MAX}秒")
    print("=" * 70)

    valid, real_target = check_trading_day(TARGET_DATE)
    if not valid:
        return
    TARGET_DATE = real_target
    print(f"✅ 生效交易日：{TARGET_DATE}")

    code_df = get_all_stock_code()
    if code_df.empty:
        print("❌ 无法获取股票代码，程序退出")
        return

    all_spot = get_all_spot_safe(code_df, TARGET_DATE)
    if all_spot.empty:
        print("❌ 未获取到行情数据，程序退出")
        return

    filter_df = filter_by_turnover(all_spot)
    if filter_df.empty:
        print(f"\n📉 当日没有换手率大于等于{TURNOVER_THRESHOLD}%的股票")
        return

    print("\n" + "-" * 70 + "\n开始获取个股近5日历史数据\n" + "-" * 70)
    stock_history = fetch_history_batch(filter_df)

    print("\n" + "=" * 70 + "\n筛选结果汇总\n" + "=" * 70)
    show_cols = ["代码", "名称", "最新价", "涨跌幅", "换手率"]
    show_cols = [c for c in show_cols if c in filter_df.columns]
    print(filter_df[show_cols].head(20).to_string(index=False))

    print(f"\n前10只股票近{HISTORY_DAYS}日行情明细：")
    show_limit = 10
    cnt = 0
    for code, info in stock_history.items():
        if cnt >= show_limit:
            break
        cnt += 1
        name = info["名称"]
        curr_turn = filter_df[filter_df["代码"] == code]["换手率"].iloc[0]
        print(f"\n{cnt}. {code} {name} | 当日换手率 {curr_turn:.2f}%")
        hist = info["历史数据"]
        if hist.empty:
            print("   无历史K线数据")
            continue
        for _, r in hist.iterrows():
            d_str = r["日期"].strftime("%Y-%m-%d")
            vol_yi = r["成交额"] / 1e8
            print(f"   {d_str} 收盘{r['收盘']:.2f} 换手{r['换手率']:.2f}% 成交额{vol_yi:.2f}亿")

    try:
        file_name = f"高换手股票_{TARGET_DATE}.xlsx"
        with pd.ExcelWriter(file_name, engine="openpyxl") as w:
            filter_df.to_excel(w, sheet_name="当日高换手汇总", index=False)
            history_total = []
            for c, val in stock_history.items():
                h = val["历史数据"]
                if h.empty:
                    continue
                for _, r in h.iterrows():
                    history_total.append({
                        "代码": c,
                        "名称": val["名称"],
                        "日期": r["日期"].strftime("%Y-%m-%d"),
                        "开盘": r["开盘"],
                        "收盘": r["收盘"],
                        "最高": r["最高"],
                        "最低": r["最低"],
                        "成交量": r["成交量"],
                        "成交额": r["成交额"],
                        "换手率(%)": r["换手率"]
                    })
            if history_total:
                pd.DataFrame(history_total).to_excel(w, sheet_name="历史数据总表", index=False)
            write_cnt = 0
            for c, val in stock_history.items():
                if write_cnt >= 20 or val["历史数据"].empty:
                    continue
                sheet_title = f"{c}_{val['名称'][:4]}"[:31]
                val["历史数据"].to_excel(w, sheet_name=sheet_title, index=False)
                write_cnt += 1
        print(f"\n✅ Excel文件导出成功：{file_name}")
    except Exception as e:
        print(f"\n⚠️ Excel导出失败：{e}")

if __name__ == "__main__":
    main()