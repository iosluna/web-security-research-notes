# 易车汽车接口：签名与天御挑战 Cookie

## 案例概况
- 挑战类型：汽车参数接口 `x-sign` 签名；部分页面另会返回天御 challenge，并要求 `tws2_*` Cookie。
- 解决思路：分别处理接口签名和页面 challenge。challenge 响应中提取 `_xvasu`、`_xvpts`，按 `xvpts:xvasu` 拼接后用 RC4 计算，再 Base64 编码为对应 Cookie；同一请求最多有限重试。
- 边界：源码包含 challenge 检测、Cookie 构造和重试逻辑，但未发现与本地源码同时保存的独立运行日志/响应样本。需在有授权的环境自行验收，不宣称当前线上稳定可用。

## 解决思路
签名接口将 `cid`、紧凑 JSON 参数、固定后缀和毫秒时间戳按既有格式拼接后计算 MD5。天御处理用于网页请求：从 challenge 页面提取动态字段，生成域为 `.yiche.com`、路径为 `/` 的 `tws2_<xvasu>` Cookie，并将原请求有限次重放。遇到明确验证码页面但无 challenge 字段时，不应把验证码页面当成功结果。

## 代码
- `code/yiche_sign.py`：构造参数签名 URL 与请求头。
- `code/tianyu_cookie.py`：从 challenge 文本构造 Cookie；调用端负责设置 Cookie、控制重试并验证实际业务响应。

## 依赖与限制
Python 3.10+，仅用标准库。挑战格式、签名字段及算法来自既有实现，站点更新后可能失效。仅用于授权访问；不要把登录凭据、Cookie 或个人数据提交到仓库。
