# OpenCLI Admin

多渠道数据采集管理平台。通过可视化界面统一管理数据源、定时计划、采集任务和通知规则，底层接入 [opencli](https://github.com/jackwener/opencli) CLI 工具采集国内外主流平台内容。

> **支持 Docker 一键运行，对本地环境零侵入。** opencli、Chrome、所有运行时依赖均已打包在镜像内，宿主机只需安装 Docker；也可直接原生运行，复用本地已有环境。

**多实例多账号同时采集**
<img width="852" height="297" alt="566109092-d456fd3d-1d2d-4846-b38a-1a86cbbf298a" src="https://github.com/user-attachments/assets/205450a5-e0d8-495e-8d7b-0e05caa4af9a" />

**支持 Agent 实例自动/手动路由**
<img width="949" height="726" alt="clipboard-image-1774003758" src="https://github.com/user-attachments/assets/2838af3b-2ecb-4d3b-8d8e-21c69db174fc" />

**支持自定义 agent 智能体对采集的数据打标签**
<img width="839" height="221" alt="566120897-994046c5-88ae-436f-8108-3327108cb2cc" src="https://github.com/user-attachments/assets/f0c59128-f74e-4cb7-84ee-87818743a4b6" />

## 功能概览

- **数据源管理** — 支持 opencli、RSS、API、Web 爬虫、CLI 五种渠道类型，可视化配置、一键触发
- **定时计划** — 结构化频率设置（每 N 分钟 / 每小时 / 每天 / 每周 / 每月 / 指定时间），支持时区和一次性执行；可为每条计划指定专用 Agent 实例
- **采集任务** — 实时查看任务状态、执行历史、错误信息；手动触发时可临时指定 Agent 实例
- **采集记录** — 归一化展示所有采集到的数据，支持状态筛选、多选批量删除、一键清空
- **节点管理** — 管理本地与远端 Agent 节点：查看在线状态、注册时间线、按站点路由绑定；支持 Docker / Shell 一键安装，WS / HTTP 双注册模式
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
| Agent noVNC | http://localhost:3010 |

预构建镜像发布在 Docker Hub（`xjh1994/opencli-admin-{api,frontend,agent}:0.2.0`），无需本地 build 即可启动。如需从源码构建：

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
| Docker 多实例 | 每个实例独立 Profile，需分别登录。agent-2 → :3011，agent-3 → :3012，以此类推 |

> **需要登录的平台**：小红书、Bilibili、知乎、微博、Twitter/X、LinkedIn、YouTube 等。Hacker News、BBC、Reuters、RSS 等公开内容无需登录。

## 边缘节点（Agent 分布式采集）

除本地内置 Agent，还支持将任意远端机器注册为采集节点，形成分布式采集集群。

### 注册模式

| 模式 | 原理 | 适用场景 |
|------|------|----------|
| **WS 反向通道** | Agent 主动 WebSocket 连接中心，中心通过长连接推送任务 | NAT / 跨网部署，Agent 无需开放入站端口 |
| **HTTP 直连** | Agent 启动后 POST 注册到中心，中心直接 HTTP 请求 Agent | 局域网，中心可直接访问 Agent |

### 安装方式

进入管理界面 → **节点管理** → **新增节点**，选择安装方式和注册模式，复制命令在目标机器上执行：

**Docker 安装（推荐）**

```bash
# WS 模式（NAT / 跨网）
docker run -d \
  --name opencli-agent \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=ws \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.2.0

# HTTP 模式（局域网）
docker run -d \
  --name opencli-agent \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=http \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.2.0
```

**Shell 脚本安装（无 Docker 环境）**

```bash
# WS 模式
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | AGENT_REGISTER=ws bash

# HTTP 模式
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | AGENT_REGISTER=http bash
```

脚本自动安装 Python 依赖（支持 `--user` / venv 双路径），无 systemd 时后台运行。

### 常用环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CENTRAL_API_URL` | 中心 API 地址（必填） | — |
| `AGENT_REGISTER` | 注册模式：`ws` \| `http` | `ws` |
| `AGENT_PORT` | Agent 监听端口（自动跳过冲突端口） | `19823` |
| `AGENT_LABEL` | 可读标签 | 主机名 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 出站代理 | — |

### 采集模式切换

在节点管理页面顶部切换：

| 模式 | 说明 |
|------|------|
| **本地模式** | API 直接驱动同 Docker 网络内的内置 Agent |
| **Agent 模式** | 任务分发到已注册的远端 Agent 节点执行 |

也可通过 `.env` 持久设置：

```bash
COLLECTION_MODE=local   # 本地（默认）
COLLECTION_MODE=agent   # 远端 Agent
```

修改 `.env` 后需重建容器：`docker compose up -d api`

### 在线历史

每个节点记录完整的上下线事件（注册 / 上线 / 离线），在节点管理页面点击「历史」查看时间线。

## 浏览器控制模式

Agent 支持以下控制模式，在「节点管理」页面按实例配置，无需重启容器即可切换：

| 模式 | 原理 | 适用场景 | 状态 |
|------|------|----------|------|
| **Bridge** | opencli 1.0 + daemon.js + opencli Browser Bridge 扩展 | 需要账号登录的站点（B站、小红书、微博等），Cookie 持久保存 | ✅ 已支持 |
| **CDP** | opencli 0.9 + Playwright 直连 Chrome DevTools Protocol | 无需登录的公开页面，链路更简单 | ✅ 已支持 |

扩展（opencli Browser Bridge）随容器启动自动加载，无需手动安装。

## 多实例并行采集

默认启动单个内置 Agent 实例（agent-1）。推荐通过「节点管理」页面动态新增实例。

**Agent 实例路由优先级（高 → 低）**：

| 优先级 | 入口 | 作用 |
|--------|------|------|
| 1（最高） | 数据源列表 → 触发 → Agent 实例 | 仅本次手动触发，一次性覆盖 |
| 2 | 定时计划 → 编辑计划 → Agent 实例 | 该计划每次触发固定使用指定实例 |
| 3 | **节点管理** → 站点绑定 | 按站点自动路由 |
| 4（兜底） | — | 自动分配空闲实例（负载均衡） |

**推荐工作流**：在「节点管理」页将站点绑定到对应 Agent 实例一次，之后所有涉及该站点的任务均自动路由。

**浏览器 Profile 持久化**

每个 Agent 实例的 Profile（Cookies、LocalStorage、扩展数据等）保存在独立 Docker volume 中（`agent_profile_1`、`agent_profile_2`…），容器重启、镜像升级均不会丢失登录状态。

## 服务端口

| 服务 | 默认端口 | `.env` 变量 |
|------|----------|-------------|
| 管理界面 | 8030 | `FRONTEND_PORT` |
| API | 8031 | `API_PORT` |
| Agent noVNC（实例 1） | 3010 | `NOVNC_PORT` |
| Agent noVNC（实例 N） | 3010 + N−1 | 自动递增 |
| 远端 Agent | 19823 | `AGENT_PORT` |

## 配置说明

编辑 `.env` 文件：

```bash
# 应用密钥（生产环境必须修改）
SECRET_KEY=your-random-secret-key

# 中心对外地址（远端 Agent 注册时使用，留空则自动从请求头推断）
PUBLIC_URL=http://192.168.1.1:8031

# 采集模式
COLLECTION_MODE=local   # local（默认）| agent

# 任务执行模式
TASK_EXECUTOR=local     # local（默认）| celery

# AI 智能体所需密钥
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
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
docker compose --profile celery up -d
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户浏览器                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼──────────────────────────────────────┐
│                        Frontend（React）                             │
│         Dashboard · 数据源 · 任务 · 记录 · 计划 · 节点 · 通知        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API
┌──────────────────────────────▼──────────────────────────────────────┐
│                       Backend API（FastAPI）                          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ Scheduler│  │ Pipeline │  │  AI 处理  │  │  通知分发          │  │
│  │ (定时/   │  │ collect  │  │ Claude/  │  │  Webhook/飞书/     │  │
│  │  webhook)│  │ →store   │  │ OpenAI/  │  │  钉钉/企微/Email   │  │
│  └──────────┘  └────┬─────┘  │ Ollama…  │  └────────────────────┘  │
│                     │        └──────────┘                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     渠道插件（Channels）                       │   │
│  │  opencli · RSS · REST API · Web 爬虫 · 通用 CLI              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────┬────────────────────┬───────────────────────────────────┬─────┘
       │                    │                                   │
       │ CDP/Bridge         │ WS 反向通道 / HTTP 直连            │ SQLite /
       ▼                    ▼                                   ▼ PostgreSQL
┌─────────────┐   ┌──────────────────────┐             ┌───────────────┐
│  内置 Agent  │   │     远端边缘节点       │             │    数据库      │
│  (Docker)   │   │  (Docker / Shell)    │             │               │
│             │   │                      │             └───────────────┘
│ ┌─────────┐ │   │ ┌──────────────────┐ │
│ │ Chrome  │ │   │ │ agent_server.py  │ │
│ │Bridge / │ │   │ │  WS ←─── 中心    │ │
│ │  CDP    │ │   │ │  HTTP ──→ 中心   │ │
│ └────┬────┘ │   │ └───────┬──────────┘ │
└──────┼──────┘   └─────────┼────────────┘
       │                    │
       ▼                    ▼
  opencli CLI          opencli CLI
  目标网站（国内外平台）  目标网站（国内外平台）
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（默认）/ PostgreSQL |
| 任务队列 | asyncio（单机）/ Celery + Redis（分布式） |
| Agent | Chromium + noVNC + opencli（Bridge/CDP 双模式，WS/HTTP 双注册模式） |
| 部署 | 原生 Shell / Docker Compose |

## 采集流水线

```
触发方式
  ├─ 手动触发（可临时指定 Agent 实例）
  ├─ 定时计划（cron，可绑定 Agent 实例）
  └─ Webhook（HMAC 签名验证）
    ↓
Agent 路由（opencli 渠道）
  ├─ 手动指定 > 计划绑定 > 站点绑定（节点管理页）> 自动分配
    ↓
渠道采集
  ├─ 本地模式 → 直接驱动内置 Agent（bridge / cdp）
  ├─ Agent 模式 → 派发到注册节点
  │    ├─ WS 反向通道（NAT 友好）
  │    └─ HTTP 直连（局域网）
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

## 项目结构

```
├── backend/
│   ├── api/v1/          # FastAPI 路由（sources / tasks / records / schedules /
│   │                    #   nodes / browsers / notifications / workers / dashboard）
│   ├── agent_server.py  # 边缘 Agent 服务（运行在远端节点，WS/HTTP 双注册）
│   ├── browser_pool.py  # Agent 浏览器池（LocalBrowserPool）
│   ├── channels/        # 渠道实现（opencli / rss / api / web_scraper / cli）
│   ├── executor/        # 任务执行器（local / celery）
│   ├── models/          # SQLAlchemy 模型（含 EdgeNode / EdgeNodeEvent）
│   ├── pipeline/        # 采集流水线（collect → normalize → store → ai → notify）
│   ├── scheduler.py     # 本地异步调度器
│   └── worker/          # Celery 任务定义
├── frontend/
│   └── src/
│       ├── pages/       # 页面组件（含 NodesPage 节点管理）
│       ├── components/  # 公共组件
│       └── api/         # API 客户端
├── scripts/
│   └── install-agent.sh # 一键安装 Agent（Docker / Shell，WS / HTTP）
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
