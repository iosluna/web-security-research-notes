# 已解决网点反爬案例

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

按网点分别整理已完成案例的反爬、解决思路及代码。

## 案例索引

| 网点 | 反爬问题与解决方向 | 分站文档 |
|---|---|---|
| 湖南省税务局 | HTTP 412 / MMB JavaScript 挑战；执行挑战脚本生成 Cookie，并在原会话重放请求 | [案例说明](web-security-research-notes/01-hunan-tax-mmb/README.md) |
| 中国专利网 | 瑞数动态挑战；在浏览器仿真 DOM 会话中初始化挑战并发起检索 | [案例说明](web-security-research-notes/02-cnipa-ruishu/README.md) |
| 海关信用系统（月度数据） | HTTP 412 JavaScript 挑战；处理 Cookie 域、过期时间及 HttpOnly 属性 | [案例说明](web-security-research-notes/03-customs-412/README.md) |
| 工信部电信业务综合管理企业查询 | 图形验证码与会话校验；同一会话取码、识别并提交查询 | [案例说明](web-security-research-notes/04-miit-captcha/README.md) |
| 全国排污许可证管理平台 | 拼图滑块、SHA-1 签名及 AES 加密校验参数 | [案例说明](web-security-research-notes/05-envsc-slider/README.md) |
| 北京首都国际机场航班信息 | AES 加密握手及 WebSocket / MessagePack 数据通道 | [案例说明](web-security-research-notes/06-bdia-flight/README.md) |
| 新浪投诉搜索 | 搜索接口 SHA-256 签名与分页请求 | [案例说明](web-security-research-notes/07-sina-complaint/README.md) |
| POI86 地理数据 | 图形验证码、会话复用及 GeoJSON ZIP 响应解析 | [案例说明](web-security-research-notes/08-poi86-captcha/README.md) |
| ICKEY / 云汉搜索 | 获取动态签名脚本并生成搜索参数 `p` | [案例说明](web-security-research-notes/09-ickey-param-sign/README.md) |
| 易车汽车参数接口 | 生成 `x-sign`、时间戳及配套请求头参数 | [案例说明](web-security-research-notes/10-yiche-api-sign/README.md) |

## 目录结构

```text
README.md
web-security-research-notes/
├── 01-hunan-tax-mmb/
│   ├── README.md
│   └── code/
│       ├── pass_412.py
│       └── solve_mmb_cookie.js
├── 02-cnipa-ruishu/
│   ├── README.md
│   └── code/
│       ├── cnipa_client.js
│       └── package.json
├── 03-customs-412/
│   ├── README.md
│   └── code/
│       ├── env_core.js
│       ├── helpers.py
│       ├── protocol_client.py
│       └── run.js
├── 04-miit-captcha/
│   ├── README.md
│   └── code/captcha_client.py
├── 05-envsc-slider/
│   ├── README.md
│   └── code/integrated_reference.py
├── 06-bdia-flight/
│   ├── README.md
│   └── code/flight_list.py
├── 07-sina-complaint/
│   ├── README.md
│   └── code/signature.py
├── 08-poi86-captcha/
│   ├── README.md
│   └── code/poi_client.py
├── 09-ickey-param-sign/
│   ├── README.md
│   └── code/
│       ├── ickey_challenge.js
│       └── ickey_signer.py
└── 10-yiche-api-sign/
    ├── README.md
    └── code/yiche_sign.py
```

每个分站 README 介绍该网点的解决思路、代码入口、运行依赖及验收边界。HTTP 200 不单独等于业务成功；目标策略变化后需重新验证。


## 使用注意

- 仅用于本人有权访问的数据、授权测试及安全研究；使用前确认目标网站服务条款和适用法律，不绕过访问控制开展未授权采集。
- 尊重网站 robots、频率限制及个人信息/数据保护要求；控制请求速率，避免影响目标服务。遇到验证码、封禁或权限提示时应停止并确认授权，不持续规避限制。
- 文档中的站点策略、接口和验证结果来自整理时的记录，不保证当前有效；先小规模验证业务响应，再决定是否继续。
- 不要提交账号密码、Cookie、API Key、代理凭据、个人数据或生产响应样本；通过环境变量或本地安全配置提供敏感参数。
- 各案例依赖和第三方库有各自许可；使用、分发前检查其许可证及目标站点条款。仓库 MIT 许可不替代第三方组件许可，也不授予访问目标站点的授权。

## License

本仓库文档及原创代码按 [MIT License](LICENSE) 发布。第三方依赖、站点资源及明确注明来源的材料不包含在本许可授予范围内。

免责声明：本仓库仅供学习、授权测试与合规研究。使用者须自行确认授权并遵守适用法律、隐私和数据保护要求；维护者不对未授权使用或由此造成的损失承担责任。
