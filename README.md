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

### 前置要求

- Docker & Docker Compose
- [opencli](https://github.com/jackwener/opencli) 已安装在宿主机（用于 opencli 渠道）

### 启动

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

### 停止

```bash
docker-compose down
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
└── .env.example
```
