# 北京首都国际机场航班信息

## 案例概况
- 难点：加密会话握手与 WebSocket MessagePack 数据通道。
- 已记录结果：代码包含新会话握手、响应解码及航班列表消息处理。
- 方案：纯 Python 复现两层 AES-128-CBC 协议后连接航班数据通道。

## 解决思路
复现页面侧固定种子加密和会话密钥提取，再用会话参数加密后续数据；保持 Base64 替换规则、PKCS#7 padding、etag/IV 等细节一致。握手后通过 WebSocket 接收 MessagePack 消息并解析列表。代理服务地址通过 `BDIA_PROXY_API_URL` 环境变量配置。

## 代码
- `code/flight_list.py`：协议客户端实现。

## 依赖与边界
Python 3.10+、`requests`、PyCryptodome、`websocket-client`。需要按运行环境配置可用代理服务。此案例是请求协议复现，不是传统验证码求解。
