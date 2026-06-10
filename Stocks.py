import efinance as ef
import time
import os
from tabulate import tabulate

my_codes = [
    "300323", "600740", "000751", "601990",
    "600059", "000019", "601179", "603258",
    "600422", "600879", "601066", "002716",
    "300589", "300129"
]

while True:
    os.system("cls")
    try:
        df = ef.stock.get_realtime_quotes()
        df = df[df["股票代码"].isin(my_codes)]
        df = df[["股票代码", "股票名称", "最新价", "涨跌幅"]]

        # 转为列表格式，适配 tabulate
        table_data = df.values.tolist()
        headers = df.columns.tolist()

        # 输出网格表格（支持 plain/simple/grid/markdown 等样式）
        print(tabulate(table_data, headers=headers, tablefmt="grid", stralign="left", numalign="right"))

    except Exception as e:
        print("异常：", e)
    time.sleep(60)