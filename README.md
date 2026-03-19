# OpenCLI Admin

多渠道数据采集管理平台。通过可视化界面统一管理数据源、定时计划、采集任务和通知规则，底层接入 [opencli](https://github.com/jackwener/opencli) CLI 工具采集国内外主流平台内容。

> **支持 Docker 一键运行，对本地环境零侵入。** opencli、Chrome、所有运行时依赖均已打包在镜像内，宿主机只需安装 Docker；也可直接原生运行，复用本地已有环境。

## 功能概览

- **数据源管理** — 支持 opencli、RSS、API、Web 爬虫、CLI 五种渠道类型，可视化配置、一键触发
- **定时计划** — 结构化频率设置（每 N 分钟 / 每小时 / 每天 / 每周 / 每月 / 指定时间），支持时区和一次性执行
- **采集任务** — 实时查看任务状态、执行历史、错误信息
- **采集记录** — 归一化展示所有采集到的数据，支持状态筛选
- **AI 增强** — 采集完成后自动调用 AI 对内容进行分析、摘要、打标等处理，结果附加到记录上；支持 Claude、OpenAI、Ollama（本地模型），通过 Prompt 模板灵活配置处理逻辑
- **通知规则** — 按触发事件（新记录入库 / AI 处理完成 / 任务失败）向 Webhook、邮件、飞书、钉钉、企业微信推送通知，支持按数据源过滤
- **工作节点** — 分布式模式下查看 Celery Worker 状态
<img width="3360" height="1958" alt="image" src="https://github.com/user-attachments/assets/db302792-5593-4199-bcad-0982e860ec41" />
<img width="3360" height="1864" alt="image" src="https://github.com/user-attachments/assets/ce644c00-c8dd-492b-97f1-172516e3d78d" />
<img width="3360" height="1864" alt="image" src="https://github.com/user-attachments/assets/d7a865c5-760d-43e5-9cff-5fe8b415d8c8" />
<img width="3360" height="2128" alt="image" src="https://github.com/user-attachments/assets/c2860e1c-23f0-4ce5-94de-599f4b9de062" />
<img width="3360" height="1856" alt="image" src="https://github.com/user-attachments/assets/1236b60d-b682-4327-bbfd-4e6da1f857cf" />




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

**前置要求**：Python 3.11+、Node.js 18+、[Playwright MCP Bridge](https://github.com/jackwener/opencli/blob/main/README.zh-CN.md#playwright-mcp-bridge-%E6%89%A9%E5%B1%95%E9%85%8D%E7%BD%AE)

opencli 依赖 Playwright MCP Bridge 驱动浏览器，请按上方文档完成配置后再启动。

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

# 3. 启动服务
docker-compose up -d
```

| 服务 | 地址 |
|------|------|
| 管理界面 | http://localhost:8030 |
| API 文档 | http://localhost:8031/docs |
| Chrome noVNC | http://localhost:3010 |

**容器内 Chrome ↔ opencli 通信**

Docker 模式下，opencli 通过 CDP（Chrome DevTools Protocol）驱动浏览器完成登录态采集，链路如下：

```
api 容器
  └─ opencli 调用 Playwright MCP Bridge
       └─ CDP WebSocket → chrome:19222
            └─ nginx 反向代理（Host 头重写）
                 └─ Chrome 本体（127.0.0.1:9222）
```

nginx 代理的作用是将 CDP 响应中的 `localhost` 替换为 `chrome`，确保 api 容器能通过容器名寻址回连。该端点通过环境变量 `OPENCLI_CDP_ENDPOINT=http://chrome:19222` 注入到 api 和 worker 容器。

**停止**

```bash
docker-compose down
```

---

### 登录采集账号（opencli 渠道必须）

opencli 渠道依赖浏览器登录态，首次使用需手动登录各平台账号。登录后状态持久保存，后续无需重复操作。

| 启动方式 | 操作 |
|----------|------|
| 原生 Shell | 脚本启动后 Chrome 窗口自动打开，在其中访问平台网址登录即可。登录态保存在 `~/.opencli-admin/chrome-profile/` |
| Docker | 打开 http://localhost:3010（noVNC），在浏览器界面中访问平台网址登录 |

> **需要登录的平台**：小红书、Bilibili、知乎、微博、Twitter/X、LinkedIn、YouTube 等。Hacker News、BBC、Reuters、RSS 等公开内容无需登录。

## 服务端口

两种模式共用同一套端口配置，在 `.env` 中修改即可：

| 服务 | 默认端口 | `.env` 变量 |
|------|----------|-------------|
| 管理界面 | 8030 | `FRONTEND_PORT` |
| API | 8031 | `API_PORT` |
| Chrome noVNC | 3010 | `NOVNC_PORT`（仅 Docker） |
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

# AI 增强（可选）
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
docker-compose --profile celery up -d
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（默认）/ PostgreSQL |
| 任务队列 | asyncio（单机）/ Celery + Redis（分布式） |
| 浏览器 | Chrome + CDP（供 opencli 登录态采集） |
| 部署 | 原生 Shell / Docker Compose |

## 采集流水线

```
数据源配置
    ↓
渠道采集（opencli / RSS / API / Web Scraper / CLI）
    ↓
数据归一化（title / url / content / author / published_at）
    ↓
去重存储（SHA-256 内容哈希）
    ↓
AI 增强（可选，Anthropic / OpenAI / Ollama）
    ↓
通知推送（可选，按规则触发）
```

## 项目结构

```
├── backend/
│   ├── api/v1/          # FastAPI 路由
│   ├── channels/        # 渠道实现（opencli / rss / api / web_scraper / cli）
│   ├── executor/        # 任务执行器（local / celery）
│   ├── pipeline/        # 采集流水线（collect → normalize → store → ai → notify）
│   ├── models/          # SQLAlchemy 模型
│   ├── scheduler.py     # 本地异步调度器
│   └── worker/          # Celery 任务定义
├── frontend/
│   └── src/
│       ├── pages/       # 页面组件
│       ├── components/  # 公共组件
│       └── api/         # API 客户端
├── chrome/              # Chrome 容器（noVNC + CDP，Docker 模式使用）
├── docker-compose.yml
├── start.sh             # 原生 shell 启动脚本
└── .env.example
```

## License

[Apache License 2.0](LICENSE)
