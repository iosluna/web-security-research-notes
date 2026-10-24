# POI86 地理数据验证码

## 案例概况
- 挑战类型：GeoJSON 接口前置图形验证码。
- 方案：维持同一 HTTP Session 获取验证码、调用 OCR、提交验证码及地区/街道参数。
- 成功判据：响应不是验证码错误页，且 ZIP 包含数字命名的 GeoJSON 文件并可解析。

## 解决思路
获取 `/Captcha` 图片并转为 Base64，提交给配置的 OCR 服务；保留验证码请求产生的 Cookie，在同一 Session 中 POST `/GeoJson/Area` 或 `/GeoJson/Street`。验证码失败或压缩包格式异常时有限重试；成功后从 ZIP 内存流读取 GeoJSON，不落临时文件。

## 代码
- `code/poi_client.py`：独立请求、OCR 接入和 GeoJSON ZIP 解包流程。

## 依赖与限制
Python 3.10+、`requests`。运行前设置 `POI_OCR_URL` 指向有权使用的 OCR 服务；该地址不内置在代码中。示例：`python poi_client.py 110101`；街道 ID 使用 `--street`。需要遵守站点访问规则并控制请求频率。
