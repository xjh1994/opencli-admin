# OpenCLI Admin

多渠道数据采集管理平台。通过可视化界面统一管理数据源、定时计划、采集任务和通知规则，底层接入 [opencli](https://github.com/jackwener/opencli) CLI 工具采集国内外主流平台内容。

## 功能概览

- **数据源管理** — 支持 opencli、RSS、API、Web 爬虫、CLI 五种渠道类型，可视化配置、一键触发
- **定时计划** — 结构化频率设置（每 N 分钟 / 每小时 / 每天 / 每周 / 每月 / 指定时间），支持时区和一次性执行
- **采集任务** — 实时查看任务状态、执行历史、错误信息
- **采集记录** — 归一化展示所有采集到的数据，支持状态筛选
- **通知规则** — 采集完成后按条件推送通知
- **工作节点** — 分布式模式下查看 Celery Worker 状态

### 支持平台（opencli 渠道）

| 分类 | 平台 |
|------|------|
| 🇨🇳 国内 | 小红书、Bilibili、知乎、微博、V2EX、雪球、什么值得买、Boss直聘、携程、小宇宙 |
| 🌐 Public | Hacker News、BBC、Reuters |
| 🌍 Global | Twitter/X、Reddit、YouTube、LinkedIn、Yahoo Finance、Barchart |

## 快速开始

两种启动方式，按需选择：

### 方式一：Docker（推荐）

**前置要求**：Docker & Docker Compose

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 按需修改 .env（最少只需改 SECRET_KEY）

# 3. 启动服务
docker-compose up -d

# 访问管理界面
open http://localhost:8030

# API 文档
open http://localhost:8031/docs
```

**登录采集账号**（opencli 渠道必须）

opencli 渠道依赖浏览器登录态，首次使用需通过内置 Chrome 手动登录各平台：

```bash
# 打开浏览器远程操作界面（noVNC）
open http://localhost:3010
```

在 noVNC 界面中打开对应平台网址并完成登录。登录态持久保存在 Chrome 容器 Profile 中，后续无需重复登录。

> **需要登录**：小红书、Bilibili、知乎、微博、Twitter/X、LinkedIn、YouTube 等。Hacker News、BBC、Reuters、RSS 等公开内容无需登录。

**停止**

```bash
docker-compose down
```

---

### 方式二：原生 Shell（无需 Docker）

直接复用宿主机已安装的 opencli 和 Chrome，适合本地开发或不想安装 Docker 的场景。

**前置要求**：Python 3.11+、Node.js 18+

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 一键启动（自动创建 venv、安装依赖，首次启动自动建表）
./start.sh
```

启动后访问：
- 管理界面：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`

**可选参数**

```bash
./start.sh --no-chrome      # 不启动 Chrome（RSS/API 渠道不需要）
./start.sh --no-frontend    # 仅启动后端 API
./start.sh --cdp-port 9223  # 自定义 Chrome CDP 端口
```

**登录采集账号**（opencli 渠道必须）

脚本会在后台启动系统 Chrome 并挂载独立 Profile，直接在弹出的 Chrome 窗口中打开对应平台网址并登录即可。登录态持久保存在 `~/.opencli-admin/chrome-profile/`，重启后无需重复登录。

如果系统未安装 Chrome，脚本会跳过并给出提示，RSS / API / Web 爬虫等渠道仍可正常使用。

**停止**：按 `Ctrl+C`，脚本自动关闭所有服务。

## 配置说明

编辑 `.env` 文件：

```bash
# 应用密钥（生产环境必须修改）
SECRET_KEY=your-random-secret-key

# 任务执行模式（见下方说明）
TASK_EXECUTOR=local

# Docker 镜像源（docker.io 访问受限时设置）
# 华为云：swr.cn-north-4.myhuaweicloud.com/
# 腾讯云：mirror.ccs.tencentyun.com/
# 阿里云：<your-id>.mirror.aliyuncs.com/
# DaoCloud：docker.m.daocloud.io/
DOCKER_REGISTRY=

# AI 增强（可选）
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

完整配置项参见 [.env.example](.env.example)。

## 任务执行模式

### 单机模式（默认）

任务在 API 进程内 asyncio 执行，无需额外依赖，适合单机部署。

```bash
# .env
TASK_EXECUTOR=local

docker-compose up -d   # 只启动 api + frontend + chrome
```

### 分布式模式

任务通过 Celery + Redis 分发到 Worker 节点，适合高并发或多机部署。

```bash
# .env
TASK_EXECUTOR=celery

docker-compose --profile celery up -d   # 额外启动 redis + worker + beat
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 管理界面 | 8030 | React 前端 |
| API | 8031 | FastAPI，含 `/docs` Swagger |
| Chrome noVNC | 3010 | 浏览器远程操作界面 |
| Chrome CDP | 19222 | Chrome DevTools Protocol |

## 开发

### 启动开发环境

```bash
# 后端代码已通过 volume mount 挂载，修改后 restart 即生效
docker-compose up -d

# 前端使用 Vite dev server（HMR，改动即时生效，无需重建）
docker-compose --profile dev up -d frontend-dev
```

### 修改后端代码

```bash
# 改完代码后重启 API
docker-compose restart api

# 需要同步给 worker/beat 时
docker-compose restart worker beat
```

### 修改前端代码

直接编辑 `frontend/src/` 下的文件，浏览器自动热更新（HMR），无需任何重启。

### 数据库

默认使用 SQLite（`/data/opencli_admin.db`，挂载在 `db_data` volume）。

生产环境切换 PostgreSQL：

```bash
# .env
DATABASE_URL=postgresql+asyncpg://opencli:password@localhost:5432/opencli_admin
```

并启动 postgres profile：

```bash
docker-compose --profile postgres up -d
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | SQLite（默认）/ PostgreSQL |
| 任务队列 | asyncio（单机）/ Celery + Redis（分布式） |
| 浏览器 | Chromium + CDP（供 opencli 登录态采集） |
| 部署 | Docker Compose |

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
├── chrome/              # Chrome 容器（noVNC + CDP）
├── docker-compose.yml
├── start.sh             # 原生 shell 启动脚本（无需 Docker）
└── .env.example
```
