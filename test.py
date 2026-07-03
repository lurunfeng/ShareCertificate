# 验证接口可用性（单独测试）
import akshare as ak
# 测试单只股票接口
test_code = "000001"
try:
    # 注意：部分版本的 spot 接口需要带市场后缀，或参数格式变更
    df = ak.stock_zh_a_spot(symbol=test_code)
    print(f"测试 {test_code} 成功：\n", df.head(1))
except Exception as e:
    print(f"接口调用失败原因：{e}")