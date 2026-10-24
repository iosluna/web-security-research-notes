# 中国专利网

## 案例概况
- 挑战类型：瑞数动态挑战页。
- 已记录结果：查询客户端具备挑战初始化和检索请求链路；HTTP 200 被用作进程成功条件。
- 方案：`sdenv`/jsdom 执行页面挑战，在同一 DOM 会话发起 XHR。

## 解决思路
由 `jsdomFromUrl` 加载入口页，让挑战脚本在带浏览器对象的环境中运行并管理 Cookie。等待挑战完成事件或超时后，通过同一个 `window` 创建 XHR POST `/Dxb/IndexQuery`。此路线属于浏览器环境仿真，不是纯算法还原。

## 代码
- `code/cnipa_client.js`：挑战初始化、Cookie 获取和查询客户端。
- `code/package.json`：Node 依赖声明。

## 依赖与边界
Node.js、`sdenv` 1.1.3。安装依赖后，在 `code/` 目录执行 `node cnipa_client.js [检索词]`。状态码 200 不等于结果内容一定完整，使用时应同时检查返回正文。
