"""
休市后查询当日换手率≥5%，数据源东方财富
解决RemoteDisconnected远程断开，兼容低版本akshare（删除set_option）
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

# ==================== 配置区（防风控调低压力） ====================
TARGET_DATE = "2026-07-03"
TURNOVER_THRESHOLD = 5.0
HISTORY_DAYS = 5
RETRY_TIMES = 8
BASE_SLEEP = 5.0
RAND_SLEEP_RANGE = (2.0, 3.0)
BATCH_SIZE = 5
BATCH_INTERVAL_MIN = 60
BATCH_INTERVAL_MAX = 90

# 全局行情缓存，只请求一次网络，降低风控
GLOBAL_SPOT_CACHE = None

# 浏览器请求头伪装，兼容所有ak版本，不再用ak.set_option
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive"
}

# 全局requests会话统一UA，替代ak.set_option
session = requests.Session()
session.headers.update(HEADERS)
requests.session = lambda: session

def check_trading_day(date_str: str) -> tuple[bool, str]:
    """自动校验交易日，非交易日自动向前匹配最近开盘日"""
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

def load_all_spot_cache(target_dt: str):
    """东方财富全市场行情，移除ak.set_option，无版本报错"""
    global GLOBAL_SPOT_CACHE
    if GLOBAL_SPOT_CACHE is not None:
        return GLOBAL_SPOT_CACHE

    print("🔁 一次性加载东方财富全市场行情缓存（仅1次网络请求）...")
    for rt in range(RETRY_TIMES):
        try:
            # 东财稳定接口，原生自带换手率字段
            df = ak.stock_zh_a_spot_em()
            df["代码"] = df["代码"].astype(str)
            # 东财换手率原生百分比，无需*100
            df["换手率"] = pd.to_numeric(df["换手率"], errors="coerce")
            GLOBAL_SPOT_CACHE = df
            print(f"✅ 行情缓存加载完成，合计{len(df)}只股票")
            return GLOBAL_SPOT_CACHE
        except (ConnectionError, Timeout, Exception) as e:
            wait = 5 * (rt + 1)
            err_msg = str(e)[:100]
            print(f"⚠️ 第{rt+1}次拉取失败，等待{wait}秒重试：{err_msg}")
            time.sleep(wait)
    print("❌ 多次连接被断开，切换手机热点或晚间21点后运行")
    return pd.DataFrame()

def get_single_spot(code: str, target_dt: str):
    """从内存缓存读取，不重复请求网络"""
    df_cache = load_all_spot_cache(target_dt)
    if df_cache.empty:
        return None
    row = df_cache[df_cache["代码"] == code]
    if row.empty:
        return None
    return row.iloc[0].to_dict()

def get_all_stock_code() -> pd.DataFrame:
    """获取沪深主板、创业板股票代码"""
    print("📋 加载A股代码列表...")
    try:
        df = ak.stock_info_a_code_name()
    except Exception:
        print("⚠️ 主代码接口异常，切换备用接口")
        df = ak.stock_info_a_code_name_csindex()
    df.columns = ["代码", "名称"]
    df["代码"] = df["代码"].astype(str)
    # 筛选60沪市、00深主板、30创业板
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
    """按设定换手率阈值筛选股票"""
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
    """获取单只股票近N日日线数据"""
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

# ==================== 主程序 ====================
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

    # 1 获取股票代码
    code_df = get_all_stock_code()
    if code_df.empty:
        print("❌ 无法获取股票代码，程序退出")
        return

    # 2 一次性加载全市场缓存，仅一次网络请求
    all_spot = get_all_spot_safe(code_df, TARGET_DATE)
    if all_spot.empty:
        print("❌ 未获取到行情数据，程序退出")
        return

    # 3 筛选高换手
    filter_df = filter_by_turnover(all_spot)
    if filter_df.empty:
        print(f"\n📉 当日没有换手率大于等于{TURNOVER_THRESHOLD}%的股票")
        return

    # 4 批量拉取历史K线
    print("\n" + "-" * 70 + "\n开始获取个股近5日历史数据\n" + "-" * 70)
    stock_history = fetch_history_batch(filter_df)

    # 控制台打印汇总
    print("\n" + "=" * 70 + "\n筛选结果汇总\n" + "=" * 70)
    show_cols = ["代码", "名称", "最新价", "涨跌幅", "换手率"]
    show_cols = [c for c in show_cols if c in filter_df.columns]
    print(filter_df[show_cols].head(20).to_string(index=False))

    # 打印前10只明细
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

    # 导出Excel
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
            # 最多20个个股独立sheet
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