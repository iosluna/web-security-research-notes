# 全国排污许可证管理平台监测数据

## 案例概况
- 挑战类型：拼图滑块，校验请求还需签名和 AES 加密点位参数。
- 已记录结果：校验业务码为 `repCode == 0000` 后，携带 `verifyid`、`verifyx` 重发监测请求。
- 方案：OpenCV 估算缺口距离，构造 SHA-1 签名与 AES-ECB 点位 JSON。

## 解决思路
获取背景图、滑块图、token、secretKey；用图像匹配定位缺口并按展示尺寸缩放距离；依据协议生成时间/随机串签名及 AES 加密点位 JSON；调用校验接口。业务码通过后将验证标识和横坐标带入原监测请求，验证失败则有限重试。

## 代码
- `code/integrated_reference.py`：独立集成版采集与滑块流程。代理服务 URL 使用 `ENVSC_PROXY_API_URL` 环境变量。

## 依赖与边界
Python、`requests`、OpenCV、NumPy、PyCryptodome、`ddddocr`、Pillow。设置代理环境变量后运行；代理池不可用时需自行调整网络配置。接口参数和挑战算法可能变化，应以验证码校验响应及后续业务数据验收。
