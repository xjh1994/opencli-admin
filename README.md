# OpenCLI Admin

[![Docker](https://img.shields.io/badge/Docker%20Hub-0.3.3-blue?logo=docker)](https://hub.docker.com/u/xjh1994)

**现代化的数据采集系统** — 可视化管理多渠道数据采集，接入 [opencli](https://github.com/jackwener/opencli) 驱动国内外主流平台，支持 AI 处理、多节点分布式调度与实时通知推送。

**仪表盘**
<img width="1600" height="900" alt="dashboard" src="https://raw.githubusercontent.com/xjh1994/opencli-admin/develop/docs/dashboard.png" />

**Agent 节点自动路由**
<img width="949" height="726" alt="clipboard-image-1774003758" src="https://github.com/user-attachments/assets/2838af3b-2ecb-4d3b-8d8e-21c69db174fc" />

**AI 智能体自动打标签**
<img width="839" height="221" alt="566120897-994046c5-88ae-436f-8108-3327108cb2cc" src="https://github.com/user-attachments/assets/f0c59128-f74e-4cb7-84ee-87818743a4b6" />

## 功能

- **数据看板** — 7 天趋势折线图、采集量柱状图、今日/昨日对比、最近执行一览
- **数据源管理** — opencli、RSS、API、Web 爬虫、CLI 五种渠道；卡片布局，搜索 + 类型筛选，一键测试连通性
- **定时计划** — 结构化 cron（每 N 分钟/小时/天/周/月），支持时区与一次性执行，可绑定专用 Agent 实例
- **采集任务** — 实时任务状态、逐步执行链路追踪、错误详情；手动触发可临时指定节点
- **采集记录** — 全文搜索（normalized_data / raw_data），行展开查看格式化 JSON + AI 分析，多选批量删除
- **节点管理** — 采集模式卡片（本地模式 / Agent 模式）一键切换；本地模式展示本地 Chrome 端点及 Bridge/CDP 切换，Agent 模式展示远端节点列表及新增节点向导；在线状态、注册时间线、按站点绑定路由
- **AI 智能体** — 采集后自动分析、摘要、打标签；支持 Claude、OpenAI、DeepSeek、Kimi、GLM、MiniMax、Ollama
- **通知推送** — 新记录入库 / AI 完成 / 任务失败触发；Webhook、飞书、钉钉、企业微信、Email

### 支持平台（opencli 渠道）

| 分类 | 平台 |
|------|------|
| 🇨🇳 国内 | 小红书、Bilibili、知乎、微博、V2EX、雪球、什么值得买、Boss直聘、携程、小宇宙、新浪财经 7x24 |
| 🌐 Public | Hacker News、BBC、Reuters、Bloomberg、arXiv、Wikipedia |
| 🌍 Global | Twitter/X、Reddit、YouTube、LinkedIn、Yahoo Finance、Barchart |

## 典型场景

### 多台 Mac Mini 组成采集集群

家里几台闲置 Mac Mini，各自登录不同账号，中心统一调度：

```
Mac Mini A（主控）              Mac Mini B                 Mac Mini C
┌──────────────────┐    WS     ┌─────────────────┐   WS  ┌─────────────────┐
│ opencli-admin    │◄──────────│ opencli-agent   │       │ opencli-agent   │
│ 管理界面 :8030   │◄──────────│ 登录：B站/小红书 │       │ 登录：Twitter/X │
│ API :8031        │           │ 采集国内平台     │       │ 采集海外平台     │
└──────────────────┘           └─────────────────┘       └─────────────────┘
```

B / C 两台用 Shell 脚本一键安装 Agent，WS 反向通道注册，穿透 NAT。在「节点管理」按站点绑定，任务自动路由。

---

### 云服务器 + 本地 Mac 混合采集

本地 Mac 持有登录 Cookie，云端负责公开数据高并发抓取：

```
本地 Mac（家庭网络）                云服务器（公网）
┌──────────────────┐              ┌──────────────────────────┐
│ opencli-agent    │──── WS ─────►│ opencli-admin（中心）     │
│ 登录：微博/知乎   │              │                          │
│       小红书/B站  │              │  内置 Agent               │
└──────────────────┘              │  HackerNews / RSS / BBC   │
                                  └──────────────────────────┘
```

敏感 Cookie 留在本地，公开数据走云端，不出内网。

---

### 单机全能采集（最简部署）

```bash
docker compose up -d   # 启动中心 + agent-1
```

在「节点管理」动态添加 agent-2、agent-3，各实例独立 Chrome Profile，支持同一平台多账号并行。

---

### 定时抓取 + AI 摘要 + 推送工作流

无需写代码，全程可视化配置：

1. **数据源** — 添加知乎热榜、HN、Twitter 列表
2. **定时计划** — 每小时执行，绑定对应 Agent
3. **AI 智能体** — 采集完成后自动调用 DeepSeek 提取摘要、打标签
4. **通知推送** — AI 完成后推送到飞书 / 企业微信

每天早晨打开飞书，信息流已处理好等你阅读。

---

## 快速开始

### 方式一：原生 Shell

直接复用本地 opencli 和 Chrome，适合开发和个人使用。

**前置要求**：Python 3.11+、Node.js 18+、[opencli Browser Bridge 扩展](https://github.com/jackwener/opencli/blob/main/README.zh-CN.md#playwright-mcp-bridge-%E6%89%A9%E5%B1%95%E9%85%8D%E7%BD%AE)

```bash
cp .env.example .env
./start.sh
```

| 服务 | 地址 |
|------|------|
| 管理界面 | http://localhost:8030 |
| API 文档 | http://localhost:8031/docs |

脚本自动创建 venv、安装依赖、初始化数据库、启动 Chrome CDP、后端热重载、前端 HMR。

```bash
./start.sh --no-chrome      # 跳过 Chrome（RSS/API 渠道不需要）
./start.sh --no-frontend    # 仅启动后端 API
./start.sh --cdp-port 9223  # 自定义 Chrome CDP 端口
```

**停止**：`Ctrl+C`，自动关闭所有进程。

---

### 方式二：Docker

**前置要求**：Docker & Docker Compose

> **Agent 镜像两个变体**：
> - `opencli-admin-agent:0.3.3` — 默认，约 200 MB，通过 `host.docker.internal` 连接宿主机 Chrome
> - `opencli-admin-agent:0.3.3-chrome` — 约 1.2 GB，内置 Chromium，完全自包含

**启动宿主机 Chrome**（若使用默认无 Chrome 变体）：

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
    --no-first-run --no-default-browser-check &

# Bridge 模式额外需要启动 daemon
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &
```

```bash
cp .env.example .env
docker compose up -d
```

| 服务 | 地址 |
|------|------|
| 管理界面 | http://localhost:8030 |
| API 文档 | http://localhost:8031/docs |
| Agent noVNC | http://localhost:3010 |

镜像已发布至 Docker Hub（`xjh1994/opencli-admin-{api,frontend,agent}:0.3.3`），无需本地构建。从源码构建：

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build -d
```

**停止**：`docker compose down`

---

### 登录采集账号

opencli 渠道依赖浏览器登录态，首次使用需手动登录各平台账号，之后持久保存。

| 启动方式 | 操作 |
|----------|------|
| 原生 Shell | 脚本启动后在 Chrome 窗口中登录。登录态保存在 `~/.opencli-admin/chrome-profile/` |
| Docker 单实例 | 打开 http://localhost:3010（noVNC）在界面中登录 |
| Docker 多实例 | 各实例独立 Profile，分别登录。agent-2 → :3011，agent-3 → :3012 |

> 需要登录：小红书、Bilibili、知乎、微博、Twitter/X、LinkedIn、YouTube。Hacker News、BBC、RSS 等公开内容无需登录。

## 边缘节点

将任意远端机器注册为采集节点，形成分布式集群。

### 注册模式

| 模式 | 原理 | 适用场景 |
|------|------|----------|
| **WS 反向通道** | Agent 主动连接中心，中心通过长连接推送任务 | NAT / 跨网，Agent 无需开放入站端口 |
| **HTTP 直连** | Agent 启动后注册到中心，中心直接请求 Agent | 局域网，中心可直达 Agent |

### 安装

进入管理界面 → **节点管理** → **新增节点**，选择安装方式，复制命令在目标机器执行：

**Docker 安装**

```bash
# WS 模式（NAT / 跨网）
docker run -d --name opencli-agent --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=ws -e AGENT_MODE=bridge \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.3.3

# HTTP 模式（局域网）
docker run -d --name opencli-agent --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e CENTRAL_API_URL=http://<center-ip>:8030 \
  -e AGENT_REGISTER=http -e AGENT_MODE=bridge \
  -p 19823:19823 \
  xjh1994/opencli-admin-agent:0.3.3
```

**一键脚本安装**

```bash
# Docker 安装（无 Chrome 镜像）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | bash

# Docker 安装，含 Chrome（无需宿主机 Chrome）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | bash -s -- docker --install-chrome

# Shell 安装（无 Docker 环境）
curl -fsSL http://<center>:8030/api/v1/nodes/install/agent.sh | \
  AGENT_REGISTER=ws AGENT_MODE=bridge bash -s -- python
```

### Bridge 与 CDP 两种连接模式

| 模式 | 原理 | 适用场景 |
|------|------|----------|
| **Bridge** | opencli + daemon.js + Browser Bridge 扩展 | 需要登录账号的平台（B站、小红书、微博等） |
| **CDP** | opencli + Chrome DevTools Protocol 直连 | 无需登录的公开页面，链路更简单 |

本地模式下，每个 Chrome 端点卡片上可切换 Bridge/CDP；Agent 模式下，通过「新增节点」向导（InstallWizardModal）选择连接模式。

### 常用环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CENTRAL_API_URL` | 中心 API 地址（必填） | — |
| `AGENT_REGISTER` | 注册模式：`ws` \| `http` | `ws` |
| `AGENT_MODE` | Chrome 连接模式：`bridge` \| `cdp` | `bridge` |
| `AGENT_PORT` | Agent 监听端口 | `19823` |
| `AGENT_LABEL` | 可读标签 | 主机名 |

### 采集模式

| 模式 | 说明 |
|------|------|
| **本地模式** | 中心直连本地 Chrome（shell 部署），不经过 Agent |
| **Agent 模式** | 通过 Agent 节点采集，支持本地 Docker 容器或远端多机分布式部署 |

```bash
COLLECTION_MODE=local   # 默认
COLLECTION_MODE=agent
```

### Agent 路由优先级

| 优先级 | 入口 | 作用 |
|--------|------|------|
| 1（最高） | 触发时手动指定 | 仅本次覆盖 |
| 2 | 定时计划绑定 | 该计划每次固定使用 |
| 3 | 节点管理 → 站点绑定 | 按站点自动路由 |
| 4（兜底） | — | 自动分配空闲实例 |

## 配置

编辑 `.env`：

```bash
SECRET_KEY=your-random-secret-key          # 生产环境必须修改
PUBLIC_URL=http://192.168.1.1:8031         # 远端 Agent 注册使用，留空自动推断
COLLECTION_MODE=local                      # local | agent
TASK_EXECUTOR=local                        # local | celery（分布式）
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

完整配置项参见 [.env.example](.env.example)。

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
  目标网站              目标网站
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（默认）/ PostgreSQL |
| 任务队列 | asyncio（单机）/ Celery + Redis（分布式） |
| Agent | Chromium + noVNC + opencli（Bridge/CDP，WS/HTTP 双注册） |
| 部署 | 原生 Shell / Docker Compose |

## 采集流水线

```
触发（手动 / 定时 cron / Webhook）
  ↓
Agent 路由（手动指定 > 计划绑定 > 站点绑定 > 自动分配）
  ↓
渠道采集
  ├─ opencli  → Bridge / CDP → 目标平台
  ├─ RSS      → feedparser
  ├─ API      → REST / GraphQL 直连
  ├─ Web 爬虫 → httpx + BeautifulSoup
  └─ CLI      → 通用命令行包装
  ↓
归一化（title / url / content / author / published_at / extra_*）
  ↓
去重存储（SHA-256 内容哈希）
  ↓
AI 处理（可选）— Claude · OpenAI · DeepSeek · Kimi · GLM · Ollama
  ↓
通知推送（可选）— Webhook · 飞书 · 钉钉 · 企微 · Email
```

## 项目结构

```
├── backend/
│   ├── api/v1/          # FastAPI 路由
│   ├── agent_server.py  # 边缘 Agent 服务（WS/HTTP 双注册）
│   ├── channels/        # 渠道插件（opencli / rss / api / web_scraper / cli）
│   ├── pipeline/        # 采集流水线（collect → normalize → store → ai → notify）
│   ├── scheduler.py     # 本地异步调度器
│   └── worker/          # Celery 任务定义
├── frontend/src/
│   ├── pages/           # 页面组件
│   ├── components/      # 公共组件
│   └── api/             # API 客户端
├── scripts/
│   └── install-agent.sh # 一键安装 Agent
├── docker-compose.yml
├── start.sh             # 原生 Shell 启动脚本
└── .env.example
```

<img width="3360" height="1958" alt="565679904-db302792-5593-4199-bcad-0982e860ec41" src="https://github.com/user-attachments/assets/ea9c3b6f-e3f6-4792-a388-9e470bf3de7e" />
<img width="3360" height="1864" alt="565680032-ce644c00-c8dd-492b-97f1-172516e3d78d" src="https://github.com/user-attachments/assets/c9694c60-90b2-4241-9d8b-5753a7066f8c" />
<img width="3360" height="1856" alt="566009767-1236b60d-b682-4327-bbfd-4e6da1f857cf" src="https://github.com/user-attachments/assets/05712eda-5f7d-4cb8-b772-2b481b2f9f51" />
<img width="3360" height="2128" alt="566026018-c2860e1c-23f0-4ce5-94de-599f4b9de062" src="https://github.com/user-attachments/assets/3b965d29-8783-49fc-a58f-30ef88213899" />
<img width="3358" height="884" alt="566120897-994046c5-88ae-436f-8108-3327108cb2cc" src="https://github.com/user-attachments/assets/e8975aa7-206f-4880-9072-e93d913803d5" />

## 集成测试

详见 [TESTING.md](TESTING.md)。

## 发布镜像

构建并推送 amd64 + arm64 多平台镜像（需要 `multiarch` buildx builder）：

```bash
TAG=0.3.3

# API
docker buildx build --builder multiarch \
  --platform linux/amd64,linux/arm64 \
  -t xjh1994/opencli-admin-api:${TAG} --push .

# 前端
docker buildx build --builder multiarch \
  --platform linux/amd64,linux/arm64 \
  -t xjh1994/opencli-admin-frontend:${TAG} --push frontend/

# Agent（含 Chrome）
docker buildx build --builder multiarch \
  --platform linux/amd64,linux/arm64 \
  -t xjh1994/opencli-admin-agent:${TAG}-chrome --push agent/
```

如需同时构建多个镜像，可并行执行（各自重定向日志）：

```bash
docker buildx build --builder multiarch --platform linux/amd64,linux/arm64 \
  -t xjh1994/opencli-admin-api:${TAG} --push . > /tmp/build-api.log 2>&1 &
docker buildx build --builder multiarch --platform linux/amd64,linux/arm64 \
  -t xjh1994/opencli-admin-frontend:${TAG} --push frontend/ > /tmp/build-frontend.log 2>&1 &
wait && echo "done"
```

> 首次使用需创建 builder：`docker buildx create --name multiarch --use`

## License

[Apache License 2.0](LICENSE)
