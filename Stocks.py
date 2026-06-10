import efinance as ef
import time
import os

my_codes = ["300323",
            "600740",
            "000751",
            "601990",
            "600059",
            "000019",
            "601179",
            "603258",
            "600422",
            "600879",
            "601066",
            "002716",
            "300589",
            "300129"
            ]

while True:
    os.system("cls")
    try:
        # 拿全市场
        df = ef.stock.get_realtime_quotes()
        # 过滤你要的
        df = df[df["股票代码"].isin(my_codes)]
        df = df[["股票代码", "股票名称", "最新价", "涨跌幅"]]
        print("=" * 50)
        print(df.to_string(index=False))
    except Exception as e:
        print("异常：", e)
    time.sleep(5)
