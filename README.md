# OpenCLI Admin

[![Docker](https://img.shields.io/badge/Docker%20Hub-0.3.2-blue?logo=docker)](https://hub.docker.com/u/xjh1994)

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
| 🇨🇳 国内 | 小红书、Bilibili、知乎、微博、V2EX、雪球、什么值得买、Boss直聘、携程、小宇宙、新浪财经 7x24 |
| 🌐 Public | Hacker News、BBC、Reuters、Bloomberg、arXiv、Wikipedia |
| 🌍 Global | Twitter/X、Reddit、YouTube、LinkedIn、Yahoo Finance、Barchart |

## 典型使用场景

### 场景一：多台 Mac Mini 组成采集集群

家庭 / 办公室有多台闲置 Mac Mini，每台登录不同平台账号，通过中心统一调度：

```
Mac Mini A（主控）              Mac Mini B                 Mac Mini C
┌──────────────────┐    WS     ┌─────────────────┐   WS  ┌─────────────────┐
│ opencli-admin    │◄──────────│ opencli-agent   │       │ opencli-agent   │
│ 管理界面 :8030   │◄──────────│ 登录：B站/小红书 │       │ 登录：Twitter/X │
│ API :8031        │           │ 采集国内平台     │       │ 采集海外平台     │
└──────────────────┘           └─────────────────┘       └─────────────────┘
```

B / C 两台 Mac Mini 用 Shell 脚本一键安装 Agent（无需 Docker），WS 反向通道注册，NAT / 跨网段均可穿透。在「节点管理」按站点绑定 Agent，任务自动路由到对应机器。

---

### 场景二：云服务器 + 本地 Mac 混合采集

本地 Mac 负责需要登录 Cookie 的国内平台，云服务器负责公开数据的高并发抓取：

```
本地 Mac（家庭网络）                云服务器（公网）
┌──────────────────┐              ┌──────────────────────────┐
│ opencli-agent    │──── WS ─────►│ opencli-admin（中心）     │
│ 登录：微博/知乎   │              │                          │
│       小红书/B站  │              │  内置 Agent               │
└──────────────────┘              │  HackerNews / RSS / BBC   │
                                  └──────────────────────────┘
```

敏感账号 Cookie 留在本地，公开抓取走云端，Cookie 不出内网。

---

### 场景三：单机全能采集（最简部署）

一台机器（Mac / Linux）运行所有服务，内置多个 Agent 实例并行：

```bash
docker compose up -d   # 启动中心 + agent-1
```

在「节点管理」动态添加 agent-2、agent-3，各实例独立 Chrome Profile，支持同时登录同一平台的多个账号。适合个人重度用户或小团队。

---

### 场景四：定时抓取 + AI 摘要 + 推送工作流

无需写代码，全程可视化配置：

1. **数据源** — 添加知乎热榜、HN、Twitter 列表等
2. **定时计划** — 每小时执行，绑定对应 Agent 实例
3. **AI 智能体** — 采集完成后自动调用 DeepSeek 提取摘要、打标签
4. **通知推送** — AI 处理完成后推送到飞书群 / 企业微信

每天早晨打开飞书，已处理好的信息流等你阅读。

---

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

**前置要求**：Docker & Docker Compose、宿主机已安装并运行 Chrome

> **Agent 镜像有两个变体**：
> - `opencli-admin-agent:0.3.2` — **默认，约 200 MB**，不含 Chrome，通过 `host.docker.internal` 连接宿主机 Chrome
> - `opencli-admin-agent:0.3.2-chrome` — **约 1.2 GB**，内置 Chromium + Xvfb，完全自包含，无需宿主机 Chrome
>
> 使用含 Chrome 变体：在 `.env` 中设置 `INSTALL_CHROME=true` 和 `CHROME_SUFFIX=-chrome`，重启即可拉取对应镜像。

**启动宿主机 Chrome**（必须在 `docker compose up` 前完成）：

```bash
# macOS — 开启 CDP 调试端口
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
    --no-first-run --no-default-browser-check &

# 启动 Bridge Daemon（bridge 模式采集必须，cdp 模式可跳过）
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &
```

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

预构建镜像发布在 Docker Hub（`xjh1994/opencli-admin-{api,frontend,agent}:0.3.2`），无需本地 build 即可启动。如需从源码构建：

```bash
# 本地构建模式
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d
```

切换版本：

```bash
IMAGE_TAG=0.3.2 docker compose up -d
```

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

> **镜像选择**：
> - `xjh1994/opencli-admin-agent:0.3.2` — 默认，约 200 MB，需宿主机提供 Chrome（通过 `host.docker.internal`）
> - `xjh1994/opencli-admin-agent:0.3.2-chrome` — 约 1.2 GB，内置 Chromium，无需宿主机 Chrome
>
> 安装命令中将镜像名替换为对应变体即可，或使用 `--install-chrome` 参数（见下方脚本安装）。

```bash
# WS 模式（NAT / 跨网）
docker run -d \
  --name opencli-agent \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=ws \
  -e AGENT_MODE=bridge \
  -e AGENT_DEPLOY_TYPE=docker \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.3.2        # 无 Chrome；含 Chrome 用 :0.3.2-chrome

# HTTP 模式（局域网）
docker run -d \
  --name opencli-agent \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=http \
  -e AGENT_MODE=bridge \
  -e AGENT_DEPLOY_TYPE=docker \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.3.2

# Host 网络模式（Linux，API 运行在宿主机而非 Docker 时使用）
docker run -d \
  --name opencli-agent \
  --restart unless-stopped \
  --network host \
  -e CENTRAL_API_URL=http://127.0.0.1:8031 \
  -e AGENT_REGISTER=http \
  -e AGENT_MODE=bridge \
  -e AGENT_DEPLOY_TYPE=docker \
  xjh1994/opencli-admin-agent:0.3.2
```

**一键脚本安装**

```bash
# Docker 安装（默认，无 Chrome 镜像）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | bash

# Docker 安装，使用含 Chrome 镜像（~1.2 GB，无需宿主机 Chrome）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | bash -s -- docker --install-chrome

# Shell 安装（无 Docker 环境，Python 原生运行）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | \
  AGENT_REGISTER=ws AGENT_MODE=bridge bash -s -- python
```

脚本自动安装 Python 依赖（支持 `--user` / venv 双路径），无 systemd 时后台运行。

### 两个正交的模式概念

边缘节点涉及两个完全独立的维度，**不可混淆**：

| 维度 | 字段 | 值 | 含义 |
|------|------|-----|------|
| **Chrome 连接模式** | `AGENT_MODE` | `bridge`（推荐）| opencli 通过 Bridge Daemon 连接 Chrome，速度快、稳定 |
| （采集时如何连 Chrome） | | `cdp` | opencli 通过 CDP 协议直连 Chrome |
| **节点部署方式** | `AGENT_DEPLOY_TYPE` | `docker`（默认）| Agent 以 Docker 容器形式运行 |
| （节点如何启动） | | `shell` | Agent 以原生 Shell 进程形式运行 |

> **关键点**：无论 docker 还是 shell 部署，节点都需要 Chrome 浏览器；Chrome 连接模式（bridge/cdp）与部署方式（docker/shell）正交，可以任意组合。

### 常用环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CENTRAL_API_URL` | 中心 API 地址（必填） | — |
| `AGENT_REGISTER` | 注册模式：`ws` \| `http` | `ws` |
| `AGENT_MODE` | Chrome 连接模式：`bridge` \| `cdp` | `bridge` |
| `AGENT_DEPLOY_TYPE` | 节点部署方式：`docker` \| `shell` | `docker` |
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
| **Bridge** | opencli 1.1 + daemon.js + opencli Browser Bridge 扩展 | 需要账号登录的站点（B站、小红书、微博等），Cookie 持久保存 | ✅ 已支持 |
| **CDP** | opencli 1.1 + Playwright 直连 Chrome DevTools Protocol | 无需登录的公开页面，链路更简单 | ✅ 已支持 |

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

## 集成测试

本节记录覆盖所有部署组合的 8 场景集成测试流程，用于验证系统核心采集链路。

### 两个维度 × 两种模式 = 8 种组合（+ 2 个 Chrome 内置变体测试）

| # | 部署方式 | 采集目标 | Chrome 连接模式 | Chrome 来源 | 关键验证点 |
|---|----------|----------|-----------------|-------------|-----------|
| 1 | Shell | 本地 | Bridge | 宿主机原生 | API 直接驱动 opencli，bridge daemon 连接本地 Chrome |
| 2 | Shell | 本地 | CDP | 宿主机原生 | 通过 API 切换模式，无需重启 |
| 3 | Shell | 边缘节点 | Bridge | 宿主机原生 | HTTP dispatch 到 shell 部署的 agent |
| 4 | Shell | 边缘节点 | CDP | 宿主机原生 | API 切换为 cdp，无需重启 agent |
| 5 | Docker | 本地 | Bridge | **宿主机 Chrome**（host.docker.internal） | agent 镜像 ~400MB，COLLECTION_MODE=local |
| 6 | Docker | 本地 | CDP | **宿主机 Chrome** | API 切换模式，无需重启 agent-1 容器 |
| 7 | Docker | 边缘节点 | Bridge | **宿主机 Chrome** | COLLECTION_MODE=agent，dispatch 到 agent-1 |
| 8 | Docker | 边缘节点 | CDP | **宿主机 Chrome** | API 切换 cdp，同一容器无重启 |
| 9 | Docker | 本地 | Bridge | **容器内置 Chrome**（-chrome 镜像） | 无需宿主机 Chrome，Chromium+Xvfb+daemon 内置 |
| 10 | Docker | 本地 | CDP | **容器内置 Chrome**（-chrome 镜像） | CDP 连接容器内 Chromium，完全自包含 |

> **关键原则**：bridge ↔ cdp 模式切换始终通过 `PATCH /api/v1/workers/chrome-pool/{ep}/mode` 完成，agent 容器/进程无需重启。COLLECTION_MODE（local/agent）是系统级配置，修改后需重启 API。

---

### 环境准备

```bash
# 启动 Redis（Celery 模式需要；local 模式可跳过）
docker compose up -d redis

# 运行数据库迁移
cd /path/to/opencli-admin
alembic upgrade head         # Shell 模式（本地 DB）
# Docker 模式由 API 容器启动时自动执行
```

定义公共变量（后续步骤复用）：

```bash
# Shell 模式用 8000，Docker 模式用 8031
BASE_SHELL="http://localhost:8000"
BASE_DOCKER="http://localhost:8031"
```

---

### Shell 部署测试（Tests 1–4）

Shell 部署 = API 和 Agent 均以原生进程运行，不涉及 Docker。

#### 准备：启动 Chrome

```bash
# 启动 Chrome，开启 CDP 调试端口
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 \
    --no-first-run --no-default-browser-check &

# 启动 Bridge Daemon（bridge 模式必须）
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &
```

#### 准备：启动 Shell API（COLLECTION_MODE=local）

```bash
OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9222 \
COLLECTION_MODE=local \
    .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

API 启动后，pool 里会有 `http://127.0.0.1:9222`，默认 bridge 模式。

---

#### Test 1 — Shell + 本地 + Bridge

```bash
# 1. 确认 pool 当前是 bridge 模式
curl -s $BASE_SHELL/api/v1/workers/chrome-pool

# 2. 创建数据源（不填 chrome_endpoint = 使用 pool 默认节点）
SOURCE_ID=$(curl -s -X POST $BASE_SHELL/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Test1-Shell-Local-Bridge","channel_type":"opencli",
       "channel_config":{"site":"v2ex","command":"hot","args":{},"format":"json"},
       "enabled":true}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# 3. 手动触发
TASK_ID=$(curl -s -X POST $BASE_SHELL/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

# 4. 等待并查看结果（应 status=completed，records>0）
sleep 15
curl -s $BASE_SHELL/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，`records_collected > 0`，API 日志显示 `opencli bridge | daemon=127.0.0.1:19825`。

---

#### Test 2 — Shell + 本地 + CDP

模式切换通过 API 完成，**无需重启任何进程**：

```bash
# 1. 切换 pool 节点到 CDP 模式
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://127.0.0.1:9222').decode())")
curl -s -X PATCH $BASE_SHELL/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"cdp"}'
# → {"data":{"endpoint":"http://127.0.0.1:9222","mode":"cdp"}}

# 2. 复用 Test1 的数据源，再次触发
TASK_ID=$(curl -s -X POST $BASE_SHELL/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 15
curl -s $BASE_SHELL/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，API 日志显示 `opencli cdp | cdp=http://127.0.0.1:9222`。

---

#### Test 3 — Shell + 边缘节点 + Bridge

```bash
# 1. 启动 shell 部署的 edge agent（bridge 模式），注册到中心 API
CENTRAL_API_URL=http://127.0.0.1:8000 \
AGENT_MODE=bridge \
AGENT_DEPLOY_TYPE=shell \
AGENT_PORT=8001 \
AGENT_LABEL="shell-edge-bridge" \
    .venv/bin/python -m backend.agent_server &

# 2. 确认节点已注册（node_type=shell, mode=bridge）
curl -s $BASE_SHELL/api/v1/nodes

# 3. 切换 API 为 agent 采集模式（重启 API 进程）
# 停止当前 API，以 COLLECTION_MODE=agent 重启
OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9222 \
COLLECTION_MODE=agent \
    .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# agent 重启后需重新注册（重启 agent 进程）
# 4. 创建指向边缘节点的数据源，触发采集
SOURCE_ID=$(curl -s -X POST $BASE_SHELL/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Test3-Shell-Edge-Bridge","channel_type":"opencli",
       "channel_config":{"site":"v2ex","command":"hot","args":{},"format":"json"},
       "enabled":true}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

TASK_ID=$(curl -s -X POST $BASE_SHELL/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 15
curl -s $BASE_SHELL/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，API 日志显示 `agent dispatch | url=http://127.0.0.1:8001/collect`，task_run 的 `node_url=http://127.0.0.1:8001`。

---

#### Test 4 — Shell + 边缘节点 + CDP

```bash
# 1. 切换 edge agent 节点到 CDP 模式（通过 API，无需重启 agent）
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://127.0.0.1:8001').decode())")
curl -s -X PATCH $BASE_SHELL/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"cdp"}'

# 2. 复用 Test3 数据源，触发
TASK_ID=$(curl -s -X POST $BASE_SHELL/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 15
curl -s $BASE_SHELL/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，agent 进程日志显示 `cdp | cmd=opencli v2ex hot -f json cdp=http://localhost:9222`。

---

### Docker 部署测试（Tests 5–8）

Docker 部署 = API 和 Agent 均以 Docker 容器运行。**Agent 镜像不含 Chrome**，连接宿主机 Chrome。

#### 准备：启动宿主机 Chrome + 构建启动 Docker 服务

```bash
# ── 1. 宿主机启动 Chrome（监听所有网卡，容器可通过 host.docker.internal 访问）
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
    --no-first-run --no-default-browser-check &

# Bridge daemon（bridge 模式必须；cdp 模式可跳过）
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &

# ── 2. 构建镜像（默认 INSTALL_CHROME=false，约 200 MB）
docker compose -f docker-compose.yml -f docker-compose.build.yml build api agent-1

# ── 3. 启动 API（COLLECTION_MODE=local，pool 预加载 agent-1）
COLLECTION_MODE=local \
    docker compose -f docker-compose.yml -f docker-compose.build.yml up -d api

# ── 4. 启动 agent-1 sidecar（bridge 模式，连接宿主机 Chrome）
AGENT_MODE=bridge \
    docker compose -f docker-compose.yml -f docker-compose.build.yml up -d agent-1

sleep 15
# 确认注册（node_type=docker, mode=bridge）
curl -s http://localhost:8031/api/v1/nodes
```

---

#### Test 5 — Docker + 本地 + Bridge

```bash
BASE=$BASE_DOCKER

# 1. 确认 pool 是 bridge 模式
curl -s $BASE/api/v1/workers/chrome-pool

# 2. 创建数据源并触发
SOURCE_ID=$(curl -s -X POST $BASE/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Test5-Docker-Local-Bridge","channel_type":"opencli",
       "channel_config":{"site":"v2ex","command":"hot","args":{},"format":"json"},
       "enabled":true}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，`records_collected > 0`。

---

#### Test 6 — Docker + 本地 + CDP

```bash
BASE=$BASE_DOCKER

# 1. 切换 pool 到 CDP 模式（不重启容器）
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://agent-1:19823').decode())")
curl -s -X PATCH $BASE/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"cdp"}'

# 2. 复用 Test5 数据源，触发
TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，agent-1 容器日志显示 `cdp | cmd=opencli v2ex hot -f json cdp=http://localhost:9222`。

---

#### Test 7 — Docker + 边缘节点 + Bridge

```bash
# 1. 重启 API 为 agent 采集模式
export COLLECTION_MODE=agent
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --force-recreate api
sleep 8

# 2. 切换 pool 到 bridge（或重启 agent-1 使其以 bridge 模式重新注册）
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://agent-1:19823').decode())")
curl -s -X PATCH $BASE_DOCKER/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"bridge"}'

# 等待 agent-1 重新注册（API 重启后 agent-1 需要重新向 API 注册）
docker compose restart agent-1
sleep 15

# 确认注册（mode=bridge）
curl -s $BASE_DOCKER/api/v1/nodes

# 3. 创建数据源并触发
SOURCE_ID=$(curl -s -X POST $BASE_DOCKER/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Test7-Docker-Edge-Bridge","channel_type":"opencli",
       "channel_config":{"site":"v2ex","command":"hot","args":{},"format":"json"},
       "enabled":true}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

TASK_ID=$(curl -s -X POST $BASE_DOCKER/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE_DOCKER/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，API 日志显示 `agent dispatch | url=http://agent-1:19823/collect`，`node_url=http://agent-1:19823`。

---

#### Test 8 — Docker + 边缘节点 + CDP

```bash
BASE=$BASE_DOCKER

# 1. 切换 agent-1 到 CDP 模式（通过 API，不重启容器）
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://agent-1:19823').decode())")
curl -s -X PATCH $BASE/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"cdp"}'

# 2. 复用 Test7 数据源，触发
TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1
```

**预期**：`status=completed`，agent-1 容器日志显示 `cdp | cmd=opencli v2ex hot -f json cdp=http://localhost:9222`，`node_url=http://agent-1:19823`。

---

### Docker 内置 Chrome 测试（Tests 9–10）

这两个 test 验证 `-chrome` 镜像变体（含 Chromium + Xvfb + Bridge Daemon）是否真正自包含，**不依赖宿主机 Chrome**。

#### 准备：切换 agent-1 为 -chrome 镜像

```bash
# 停止当前 agent-1 容器
docker stop agent-1 && docker rm agent-1

# 用 -chrome 镜像启动（AGENT_MODE=bridge，内置 Chromium 和 daemon）
docker run -d \
  --name agent-1-chrome \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://host.docker.internal:8031 \
  -e AGENT_ADVERTISE_URL=http://host.docker.internal:19824 \
  -e AGENT_PORT=19824 \
  -e AGENT_MODE=bridge \
  -e AGENT_DEPLOY_TYPE=docker \
  -e AGENT_LABEL=agent-1-chrome \
  -e AGENT_REGISTER=http \
  -p 19824:19824 \
  xjh1994/opencli-admin-agent:0.3.2-chrome

sleep 20
# 确认节点注册（应有 label=agent-1-chrome, node_type=docker, mode=bridge）
curl -s http://localhost:8031/api/v1/nodes
```

---

#### Test 9 — Docker + 内置Chrome + Bridge

```bash
BASE=$BASE_DOCKER

# 1. 确认 pool 里有 agent-1-chrome，mode=bridge
curl -s $BASE/api/v1/workers/chrome-pool

# 2. 确认 COLLECTION_MODE=local（若不是，切换并重启 API）
curl -s $BASE/api/v1/system/config

# 3. 创建数据源，指定 chrome_endpoint 为 agent-1-chrome
CHROME_EP="http://host.docker.internal:19824"
SOURCE_ID=$(curl -s -X POST $BASE/api/v1/sources \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Test9-Docker-Chrome-Bridge\",\"channel_type\":\"opencli\",
       \"channel_config\":{\"site\":\"v2ex\",\"command\":\"hot\",\"args\":{},\"format\":\"json\"},
       \"enabled\":true}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1 | python3 -m json.tool
```

**预期**：`status=completed`，`records_collected > 0`。容器日志显示内置 Chromium 启动，`bridge | daemon=127.0.0.1:19825`。宿主机可关闭 Chrome，采集仍成功。

```bash
docker logs agent-1-chrome --tail=30
```

---

#### Test 10 — Docker + 内置Chrome + CDP

```bash
BASE=$BASE_DOCKER

# 1. 切换 agent-1-chrome 到 CDP 模式（不重启容器）
EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://host.docker.internal:19824').decode())")
curl -s -X PATCH $BASE/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"cdp"}'

# 2. 复用 Test9 数据源，触发
TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 20
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1 | python3 -m json.tool
```

**预期**：`status=completed`，容器日志显示 `cdp | cmd=opencli v2ex hot -f json cdp=http://localhost:9222`（连接容器内部 Chromium CDP）。

---

### 结果验证

每个 test 完成后，检查以下指标：

```bash
# 查看任务运行记录
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1 | python3 -m json.tool
# 关注: status=completed, records_collected>0, error_message=null

# 查看 API 日志（Shell 模式）
# 关键日志行：
#   "opencli bridge | cmd=... daemon=..."  → 本地 bridge 采集
#   "opencli cdp | cmd=... cdp=..."        → 本地 CDP 采集
#   "agent dispatch | url=...  site=..."   → agent 模式分发
#   "agent done | ... items=N"             → agent 返回结果

# 查看 agent-1 容器日志（Docker 模式）
docker logs agent-1 --tail=20
# 关键日志行：
#   "bridge | cmd=opencli ... daemon=localhost:19825"  → bridge 模式执行
#   "cdp | cmd=opencli ... cdp=http://localhost:9222"  → CDP 模式执行
```

### 已知行为

- **重复数据返回 0 条**：同一来源的数据通过 `content_hash` 去重，重复触发同一数据源时 `records_collected=0` 但 `status=completed` 是正常现象。
- **`browser: false` 的站点（v2ex hot、HN 等）不区分 bridge/cdp**：这类站点直接调用公开 HTTP API，不使用浏览器，两种模式效果相同。需要验证 bridge 与 CDP 真实差异请使用需要浏览器的站点（如 linux-do、zhihu 等）。
- **COLLECTION_MODE 切换需重启 API**：这是系统级配置，对应用户修改 `.env` 后执行 `docker compose up -d api` 的正常运维操作。bridge/cdp 模式切换则无需重启，通过 `PATCH /mode` 接口实时生效。
- **Docker 测试前需在宿主机启动 Chrome**：agent 镜像默认使用无 Chrome 变体（约 400 MB），Tests 5-8 依赖宿主机 Chrome 通过 `host.docker.internal` 提供浏览器能力。如需完全自包含，在 `.env` 中设置 `INSTALL_CHROME=true` 和 `CHROME_SUFFIX=-chrome`，重启后会拉取 `-chrome` 变体（约 1.2 GB）。
- **切换 agent 容器后需清理旧节点**：手动 `docker stop/rm` 旧 agent 后，旧 endpoint 仍残留在 in-memory pool 中（节点 DB 也未清理）。切换前需通过 `DELETE /api/v1/nodes/{id}` 主动删除旧节点，或重启 API 让新 agent 重新注册后再清理。Tests 9-10 中切换到 `-chrome` 镜像时需先删除旧 `agent-1` 节点。

## License

[Apache License 2.0](LICENSE)
