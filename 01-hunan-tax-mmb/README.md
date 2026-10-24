# 湖南省税务局 MMB 挑战

## 案例概况
- 挑战类型：HTTP 412 + MMB JavaScript。
- 已记录结果：首请求 412；挑战脚本执行后重放请求返回 200，页面标题匹配，并保存响应 HTML。
- 方案：Python 请求会话与 Node `vm` 挑战执行器配合生成 Cookie。

## 解决思路
1. 请求目标页，提取挑战脚本 URL 和服务端初始 Cookie。
2. 将脚本路径、页面 URL、User-Agent、Cookie 传给 Node 执行器。
3. 在普通 `vm` sandbox 中运行挑战脚本，模拟其所需浏览器接口并收集 `document.cookie` 写入。
4. 用相同 User-Agent 更新原 HTTP 会话 Cookie，再请求目标页并检查状态和页面内容。

## 代码
- `code/pass_412.py`：请求、挑战脚本获取、求解器调用和重试。
- `code/solve_mmb_cookie.js`：Node 沙箱及 Cookie 捕获逻辑。

## 依赖与边界
Python `requests`、Node.js。挑战脚本按页面返回地址获取。已有记录指出 `Proxy has=true` 会令此混淆脚本卡住，不应启用该代理行为。挑战实现针对已观察到的页面结构，网站更新后需重新验证。
