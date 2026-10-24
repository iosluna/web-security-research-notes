# 海关信用系统（月度数据）

## 案例概况
- 挑战类型：HTTP 412 JavaScript 挑战，涉及 Cookie 域、过期时间和 HttpOnly 属性。
- 已记录结果：挑战脚本执行后重放请求，客户端检查最终 HTTP 响应；挑战轮数和总重试次数均有限制。
- 方案：Node 执行页面脚本，Python 会话按浏览器可见性规则更新 Cookie。

## 解决思路
解析挑战 HTML 中的内联和外链脚本，交给 JS 执行器运行。仅向页面脚本提供当前 URL 可见的非 HttpOnly Cookie；将脚本写 Cookie 的结果按 domain、path、expires 应用到 HTTP CookieJar，阻止脚本覆盖 HttpOnly Cookie。沿用同一 Session 重发请求，失败时清理状态并有限重试。

## 代码
- `code/protocol_client.py`：独立 HTTP 会话和挑战重试编排。
- `code/helpers.py`：HTML 提取及 Cookie 语义处理。
- `code/run.js`、`code/env_core.js`：JavaScript 挑战执行环境。

## 依赖与边界
Python `requests`、Node.js、`@napi-rs/canvas`、`sdenv`。运行前在 `code/` 安装 JS 依赖，并确保 Python 能导入同目录 `helpers.py`。该代码只覆盖月度数据使用的挑战流程；站点变更后需重新验收。
