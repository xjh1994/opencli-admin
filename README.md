# OpenCLI Admin

多渠道数据采集管理平台。通过可视化界面统一管理数据源、定时计划、采集任务和通知规则，底层接入 [opencli](https://github.com/jackwener/opencli) CLI 工具采集国内外主流平台内容。

> **支持 Docker 一键运行，对本地环境零侵入。** opencli、Chrome、所有运行时依赖均已打包在镜像内，宿主机只需安装 Docker；也可直接原生运行，复用本地已有环境。

**多实例多账号同时采集**
<img width="852" height="297" alt="566109092-d456fd3d-1d2d-4846-b38a-1a86cbbf298a" src="https://github.com/user-attachments/assets/205450a5-e0d8-495e-8d7b-0e05caa4af9a" />

**支持 chrome 实例自动/手动路由**
<img width="840" height="463" alt="566335801-c147dfd9-24a8-47b2-bced-aafb7ae06b61" src="https://github.com/user-attachments/assets/1344c159-01dc-4582-b8f9-55212ba14439" />

**支持自定义 agent 智能体对采集的数据打标签**
<img width="839" height="221" alt="566120897-994046c5-88ae-436f-8108-3327108cb2cc" src="https://github.com/user-attachments/assets/f0c59128-f74e-4cb7-84ee-87818743a4b6" />

## 功能概览

- **数据源管理** — 支持 opencli、RSS、API、Web 爬虫、CLI 五种渠道类型，可视化配置、一键触发
- **定时计划** — 结构化频率设置（每 N 分钟 / 每小时 / 每天 / 每周 / 每月 / 指定时间），支持时区和一次性执行；可为每条计划指定专用 Chrome 实例
- **采集任务** — 实时查看任务状态、执行历史、错误信息；手动触发时可临时指定 Chrome 实例
- **采集记录** — 归一化展示所有采集到的数据，支持状态筛选、多选批量删除、一键清空
- **浏览器管理** — 将站点与指定 Chrome 实例绑定，触发任务时自动路由到对应实例；卡片式交互，点选即绑，noVNC 链接一键直达
- **AI 智能体** — 采集完成后自动调用 AI 对内容进行分析、摘要、打标等处理，结果附加到记录上；支持 Claude、OpenAI、DeepSeek、Kimi、GLM、MiniMax、Ollama 等模型提供商，内置预设 Prompt 模板，占位符自动匹配各站点实际字段
- **通知推送** — 按触发事件（新记录入库 / AI 处理完成 / 任务失败）向 Webhook、邮件、飞书、钉钉、企业微信推送，各渠道结构化配置表单，支持签名验证
- **工作节点** — 分布式模式下查看 Celery Worker 状态

### 支持平台（opencli 渠道）

| 分类 | 平台 |
|------|------|
| 🇨🇳 国内 | 小红书、Bilibili、知乎、微博、V2EX、雪球、什么值得买、Boss直聘、携程、小宇宙 |
| 🌐 Public | Hacker News、BBC、Reuters |
| 🌍 Global | Twitter/X、Reddit、YouTube、LinkedIn、Yahoo Finance、Barchart |

## 快速开始

两种启动方式，按需选择：

### 方式一：原生 Shell

直接复用宿主机已有的 opencli 和 Chrome，适合本地开发。

**前置要求**：Python 3.11+、Node.js 18+、[Playwright MCP Bridge](https://github.com/jackwener/opencli/blob/main/README.zh-CN.md#playwright-mcp-bridge-%E6%89%A9%E5%B1%95%E9%85%8D%E7%BD%AE)（原生模式浏览器驱动依赖）

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 一键启动
./start.sh
```

| 服务 | 地址 |
|------|------|
| 管理界面 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |

脚本自动完成：创建 Python venv、安装依赖、初始化数据库、启动 Chrome CDP、后端（热重载）、前端（HMR）。

**可选参数**

```bash
./start.sh --no-chrome      # 跳过 Chrome（RSS/API 渠道不需要）
./start.sh --no-frontend    # 仅启动后端 API
./start.sh --cdp-port 9223  # 自定义 Chrome CDP 端口
```

**停止**：`Ctrl+C`，自动关闭所有进程。

---

### 方式二：Docker

**前置要求**：Docker & Docker Compose

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 按需修改 .env（最少只需改 SECRET_KEY）

# 3. 启动（默认从 Docker Hub 拉取镜像）
docker compose up -d
```

| 服务 | 地址 |
|------|------|
| 管理界面 | http://localhost:8030 |
| API 文档 | http://localhost:8031/docs |
| Chrome noVNC | http://localhost:3010 |

预构建镜像发布在 Docker Hub（`xjh1994/opencli-admin-{api,frontend,chrome}:0.1.0`），无需本地 build 即可启动。如需从源码构建：

```bash
# 本地构建模式
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d
```

切换版本：

```bash
IMAGE_TAG=0.2.0 docker compose up -d
```

**浏览器控制模式**

Chrome 实例支持以下控制模式，在「浏览器管理」页面按实例配置，无需重启容器即可切换：

| 模式 | 原理 | 适用场景 | 状态 |
|------|------|----------|------|
| **Bridge** | opencli 1.0 + daemon.js + opencli Browser Bridge 扩展 | 需要账号登录的站点（B站、小红书、微博等），Cookie 持久保存 | ✅ 已支持 |
| **CDP** | opencli 0.9 + Playwright 直连 Chrome DevTools Protocol | 无需登录的公开页面，链路更简单 | ✅ 已支持 |
| **Playwright MCP Bridge** | Playwright MCP Bridge 扩展（待接入） | — | 🚧 规划中 |

扩展（opencli Browser Bridge）随容器启动自动加载，无需手动安装。

**多实例 Chrome 并行采集**

默认启动单个 Chrome 实例（chrome-1）。推荐通过「浏览器管理」页面动态新增实例，新增时可选择控制模式，无需重启。
<img width="223" height="366" alt="566655820-29bd05db-40bc-4cd1-aca9-d5dbbb13c714 (1)" src="https://github.com/user-attachments/assets/5e37776c-22ba-49e6-b300-81ba97cf7471" />


如界面操作不可用，也可通过脚本手动管理：

```bash
# 启动 3 个 Chrome 实例（含默认的 chrome-1，共扩展到 3 个）
./scripts/chrome-pool.sh start 3

# 查看所有实例状态
./scripts/chrome-pool.sh status

# 缩减回单实例（多余的自动停止）
./scripts/chrome-pool.sh start 1

# 停止所有额外实例
./scripts/chrome-pool.sh stop
```

将输出的 `CHROME_POOL_ENDPOINTS` 写入 `.env`，重启 API 即生效：

```bash
docker compose restart api
```

每个实例拥有独立的浏览器 Profile 和 noVNC 端口（从 `NOVNC_PORT` 递增），首次启动后需分别通过 noVNC 登录各平台账号。

**Chrome 实例路由**

多实例模式下，可以将不同数据源的采集任务路由到指定的 Chrome 实例，实现登录态隔离（例如：小红书账号只登录在 chrome-2，Twitter 账号只登录在 chrome-3）。

路由优先级（高 → 低）：

| 优先级 | 入口 | 作用 |
|--------|------|------|
| 1（最高） | 数据源列表 → 触发 → Chrome 实例 | 仅本次手动触发使用，一次性覆盖 |
| 2 | 定时计划 → 编辑计划 → Chrome 实例 | 该计划每次触发固定使用指定实例 |
| 3 | **浏览器管理** → 站点绑定 | 按站点自动路由，无需每条计划单独配置 |
| 4（兜底） | — | 自动分配当前空闲实例（负载均衡） |

**推荐工作流**：在「浏览器管理」页将站点绑定到对应实例一次，之后所有涉及该站点的任务均自动路由，无需逐条配置计划。

**停止**

```bash
docker compose down
```

---

### 登录采集账号（opencli 渠道必须）

opencli 渠道依赖浏览器登录态，首次使用需手动登录各平台账号。登录后状态持久保存，后续无需重复操作。

| 启动方式 | 操作 |
|----------|------|
| 原生 Shell | 脚本启动后 Chrome 窗口自动打开，在其中访问平台网址登录即可。登录态保存在 `~/.opencli-admin/chrome-profile/` |
| Docker 单实例 | 打开 http://localhost:3010（noVNC），在浏览器界面中访问平台网址登录 |
| Docker 多实例 | 每个实例独立 Profile，需分别登录。chrome-2 → :3011，chrome-3 → :3012，以此类推 |

> **需要登录的平台**：小红书、Bilibili、知乎、微博、Twitter/X、LinkedIn、YouTube 等。Hacker News、BBC、Reuters、RSS 等公开内容无需登录。

### 浏览器状态管理

**Profile 持久化**

每个 Chrome 实例的 Profile（Cookies、LocalStorage、扩展数据等）保存在独立的 Docker named volume 中：

| 实例 | Volume 名称 |
|------|------------|
| chrome（实例 1） | `{project}_chrome_profile` |
| chrome-2 | `{project}_chrome_profile_2` |
| chrome-N | `{project}_chrome_profile_N` |

容器重启、镜像升级均不会丢失登录状态。

**重置登录状态**

如需清除某个实例的所有登录信息（如账号切换、Cookie 失效）：

```bash
# 停止并删除实例及其 volume（以 chrome-2 为例）
docker rm -f chrome-2
docker volume rm opencli-admin_chrome_profile_2

# 重新启动，按提示重新登录
./scripts/chrome-pool.sh start 3
```

**多实例登录注意事项**

- 各实例 Profile 完全隔离，在一个实例中登录不影响其他实例
- 同一平台需在每个实例中分别登录，否则该实例执行对应采集任务时会因无登录态而失败
- 建议：扩容后先通过 noVNC 逐一确认各实例登录状态，再将 `CHROME_POOL_ENDPOINTS` 写入 `.env`

## 服务端口

两种模式共用同一套端口配置，在 `.env` 中修改即可：

| 服务 | 默认端口 | `.env` 变量 |
|------|----------|-------------|
| 管理界面 | 8030 | `FRONTEND_PORT` |
| API | 8031 | `API_PORT` |
| Chrome noVNC（实例 1） | 3010 | `NOVNC_PORT`（仅 Docker） |
| Chrome noVNC（实例 N） | 3010 + N−1 | 由 `chrome-pool.sh` 自动分配 |
| Chrome CDP | 9222 | `CDP_PORT`（仅原生） |

原生模式支持命令行参数临时覆盖（优先级高于 `.env`）：

```bash
./start.sh --api-port 9000 --frontend-port 9001
```

## 配置说明

编辑 `.env` 文件：

```bash
# 应用密钥（生产环境必须修改）
SECRET_KEY=your-random-secret-key

# 任务执行模式（见下方说明）
TASK_EXECUTOR=local

# AI 智能体所需密钥（按实际使用的提供商填写，也可在智能体配置页面单独填写）
ANTHROPIC_API_KEY=sk-ant-...   # Claude
OPENAI_API_KEY=sk-...          # OpenAI
# DEEPSEEK_API_KEY / MOONSHOT_API_KEY 等在智能体配置中直接填写
```

完整配置项参见 [.env.example](.env.example)。

## 任务执行模式

### 单机模式（默认）

任务在 API 进程内 asyncio 执行，无需额外依赖，适合单机部署。

```bash
TASK_EXECUTOR=local
```

### 分布式模式

任务通过 Celery + Redis 分发到 Worker 节点，适合高并发或多机部署。

```bash
TASK_EXECUTOR=celery

# Docker 模式下额外启动 redis + worker + beat
docker-compose --profile celery up -d
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（默认）/ PostgreSQL |
| 任务队列 | asyncio（单机）/ Celery + Redis（分布式） |
| 浏览器 | Chromium + noVNC + opencli Browser Bridge（Bridge/CDP 双模式，动态多实例池） |
| 部署 | 原生 Shell / Docker Compose |

## 采集流水线

```
触发方式
  ├─ 手动触发（可临时指定 Chrome 实例）
  ├─ 定时计划（cron，可绑定 Chrome 实例）
  └─ Webhook（HMAC 签名验证）
    ↓
Chrome 实例路由（opencli 渠道）
  ├─ 手动指定 > 计划绑定 > 站点绑定（浏览器管理页）> 自动分配
    ↓
渠道采集
  ├─ opencli  — Chrome 浏览器池（LocalPool / RedisPool）按路由分配实例
  ├─ RSS       — feedparser
  ├─ API       — REST / GraphQL 直连
  ├─ Web 爬虫 — httpx + BeautifulSoup
  └─ CLI       — 通用命令行工具包装
    ↓
数据归一化
  └─ 标准字段：title / url / content / author / published_at
     扩展字段：extra_* （各站点特有，如 rank / heat / play 等）
    ↓
去重存储（SHA-256 内容哈希）
    ↓
AI 智能体处理（可选）
  └─ 支持：Claude · OpenAI · DeepSeek · Kimi · GLM · MiniMax · Ollama · 自定义
    ↓
通知推送（可选，按触发事件 + 数据源过滤）
  └─ 渠道：Webhook · 飞书 · 钉钉 · 企业微信 · Email
```

## Chrome 浏览器池架构

opencli 渠道通过浏览器池管理并发与路由，每个实例支持独立的控制模式：

```
采集任务
  │  chrome_endpoint=None        → LocalBrowserPool._acquire_any()
  │                                 竞争所有空闲实例，取最先释放的
  │  chrome_endpoint="http://chrome-2:19222"
  │                              → LocalBrowserPool.acquire(endpoint=...)
  │                                 等待指定实例专属 slot 释放
  ↓
BrowserPool（单机：asyncio.Queue / 分布式：Redis BLPOP）
  ├─ chrome-1  (slot: 1, mode: bridge)
  ├─ chrome-2  (slot: 1, mode: cdp)    ← 每实例同一时刻最多执行 1 个任务
  └─ chrome-N  (slot: 1, mode: ...)
    ↓
按 mode 选择 opencli 版本
  ├─ bridge → opencli 1.0（OPENCLI_DAEMON_HOST=chrome-N）
  │             └─ daemon.js → opencli Browser Bridge 扩展 → Chrome APIs
  └─ cdp    → opencli 0.9（OPENCLI_CDP_ENDPOINT=http://chrome-N:19222）
               └─ Playwright → Chrome DevTools Protocol → Chromium
```

`chrome_endpoint` 通过任务 `parameters` 传递，在定时计划和手动触发时均可配置，不影响数据源本身的定义。站点绑定（浏览器管理页）在 pipeline 预处理阶段自动注入，对上层完全透明。

## 项目结构

```
├── backend/
│   ├── api/v1/          # FastAPI 路由（sources / tasks / records / schedules /
│   │                    #   browsers / agents / notifications / workers / dashboard）
│   ├── browser_pool.py  # Chrome 浏览器池（LocalBrowserPool / RedisBrowserPool）
│   ├── channels/        # 渠道实现（opencli / rss / api / web_scraper / cli）
│   ├── executor/        # 任务执行器（local / celery）
│   ├── pipeline/        # 采集流水线（collect → normalize → store → ai → notify）
│   ├── models/          # SQLAlchemy 模型（含 BrowserBinding 站点绑定）
│   ├── scheduler.py     # 本地异步调度器
│   └── worker/          # Celery 任务定义
├── frontend/
│   └── src/
│       ├── pages/       # 页面组件（含 BrowsersPage 浏览器管理）
│       ├── components/  # 公共组件
│       └── api/         # API 客户端
├── chrome/              # Chrome 容器（noVNC + CDP，Docker 模式使用）
├── scripts/
│   └── chrome-pool.sh   # 动态管理 Chrome 实例数量（扩容 / 缩容 / 状态）
├── docker-compose.yml
├── start.sh             # 原生 shell 启动脚本
└── .env.example
```

<img width="3360" height="1958" alt="565679904-db302792-5593-4199-bcad-0982e860ec41" src="https://github.com/user-attachments/assets/ea9c3b6f-e3f6-4792-a388-9e470bf3de7e" />
<img width="3360" height="1864" alt="565680032-ce644c00-c8dd-492b-97f1-172516e3d78d" src="https://github.com/user-attachments/assets/c9694c60-90b2-4241-9d8b-5753a7066f8c" />
<img width="3360" height="1856" alt="566009767-1236b60d-b682-4327-bbfd-4e6da1f857cf" src="https://github.com/user-attachments/assets/05712eda-5f7d-4cb8-b772-2b481b2f9f51" />
<img width="3360" height="2128" alt="566026018-c2860e1c-23f0-4ce5-94de-599f4b9de062" src="https://github.com/user-attachments/assets/3b965d29-8783-49fc-a58f-30ef88213899" />
<img width="3358" height="884" alt="566120897-994046c5-88ae-436f-8108-3327108cb2cc" src="https://github.com/user-attachments/assets/e8975aa7-206f-4880-9072-e93d913803d5" />

## License

[Apache License 2.0](LICENSE)
