# 集成测试

覆盖所有部署组合的 10 场景集成测试流程，用于验证系统核心采集链路。

## 场景总览

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

## 环境准备

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

## Shell 部署测试（Tests 1–4）

Shell 部署 = API 和 Agent 均以原生进程运行，不涉及 Docker。

### 准备：启动 Chrome

```bash
# 启动 Chrome，开启 CDP 调试端口
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 \
    --no-first-run --no-default-browser-check &

# 启动 Bridge Daemon（bridge 模式必须）
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &
```

### 准备：启动 Shell API（COLLECTION_MODE=local）

```bash
OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9222 \
COLLECTION_MODE=local \
    .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

API 启动后，pool 里会有 `http://127.0.0.1:9222`，默认 bridge 模式。

---

### Test 1 — Shell + 本地 + Bridge

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

### Test 2 — Shell + 本地 + CDP

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

### Test 3 — Shell + 边缘节点 + Bridge

```bash
# 1. 启动 shell 部署的 edge agent（bridge 模式），注册到中心 API
CENTRAL_API_URL=http://127.0.0.1:8000 \
AGENT_MODE=bridge \
AGENT_DEPLOY_TYPE=shell \
AGENT_PORT=8001 \
AGENT_LABEL="shell-edge-bridge" \
    .venv/bin/python -m uvicorn backend.agent_server:app --host 0.0.0.0 --port 8001 &

sleep 5
# 2. 确认节点已注册（node_type=shell, mode=bridge）
curl -s $BASE_SHELL/api/v1/nodes

# 3. 切换 API 为 agent 采集模式（重启 API 进程）
OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9222 \
COLLECTION_MODE=agent \
    .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# 4. 重启 agent 重新注册到新 API 实例，再触发采集
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

### Test 4 — Shell + 边缘节点 + CDP

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

## Docker 部署测试（Tests 5–8）

Docker 部署 = API 和 Agent 均以 Docker 容器运行。**Agent 镜像不含 Chrome**，连接宿主机 Chrome。

### 准备：启动宿主机 Chrome + 构建启动 Docker 服务

```bash
# ── 1. 宿主机启动 Chrome（监听所有网卡，容器可通过 host.docker.internal 访问）
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
    --no-first-run --no-default-browser-check &

# Bridge daemon（bridge 模式必须；cdp 模式可跳过）
node $(npm root -g)/@jackwener/opencli/dist/daemon.js &

# ── 2. 启动 API（COLLECTION_MODE=local，pool 预加载 agent-1）
COLLECTION_MODE=local docker compose up -d api

# ── 3. 启动 agent-1 sidecar（bridge 模式，连接宿主机 Chrome）
AGENT_MODE=bridge docker compose up -d agent-1

sleep 15
# 确认注册（node_type=docker, mode=bridge）
curl -s http://localhost:8031/api/v1/nodes
```

---

### Test 5 — Docker + 本地 + Bridge

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

### Test 6 — Docker + 本地 + CDP

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

### Test 7 — Docker + 边缘节点 + Bridge

```bash
# 1. 重启 API 为 agent 采集模式
export COLLECTION_MODE=agent
docker compose up -d --force-recreate api
sleep 8

# 2. 重启 agent-1 重新注册，切换 pool 到 bridge
docker compose restart agent-1
sleep 15

EP_B64=$(python3 -c "import base64; print(base64.urlsafe_b64encode(b'http://agent-1:19823').decode())")
curl -s -X PATCH $BASE_DOCKER/api/v1/workers/chrome-pool/$EP_B64/mode \
  -H "Content-Type: application/json" -d '{"mode":"bridge"}'

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

### Test 8 — Docker + 边缘节点 + CDP

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

## Docker 内置 Chrome 测试（Tests 9–10）

这两个 test 验证 `-chrome` 镜像变体（含 Chromium + Xvfb + Bridge Daemon）是否真正自包含，**不依赖宿主机 Chrome**。

### 准备：切换 agent-1 为 -chrome 镜像

> ⚠️ **注意**：手动 `docker stop/rm` 旧容器后，旧节点的 endpoint 仍残留在 API 的 in-memory pool 中，会导致 dispatch 报错（"Name or service not known"）。必须先通过 API 删除旧节点，再启动新容器。

```bash
# 1. 先删除旧 agent-1 节点（清理 pool 和 DB）
NODE_ID=$(curl -s http://localhost:8031/api/v1/nodes | \
  python3 -c "import sys,json; nodes=json.load(sys.stdin)['data']; \
              [print(n['id']) for n in nodes if n['label']=='agent-1']")
curl -s -X DELETE http://localhost:8031/api/v1/nodes/$NODE_ID

# 2. 停止并删除旧容器
docker stop agent-1 && docker rm agent-1

# 3. 用 -chrome 镜像启动（AGENT_MODE=bridge，内置 Chromium 和 daemon）
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

### Test 9 — Docker + 内置Chrome + Bridge

```bash
BASE=$BASE_DOCKER

# 1. 确认 COLLECTION_MODE=agent，pool 里有 agent-1-chrome 且 mode=bridge
curl -s $BASE/api/v1/system/config
curl -s $BASE/api/v1/workers/chrome-pool

# 2. 创建数据源并触发
SOURCE_ID=$(curl -s -X POST $BASE/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Test9-Docker-ChromeBuiltin-Bridge","channel_type":"opencli",
       "channel_config":{"site":"v2ex","command":"hot","args":{},"format":"json"},
       "enabled":true}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

TASK_ID=$(curl -s -X POST $BASE/api/v1/tasks/trigger \
  -H "Content-Type: application/json" \
  -d "{\"source_id\":\"$SOURCE_ID\",\"trigger_type\":\"manual\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")

sleep 25
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1 | python3 -m json.tool
```

**预期**：`status=completed`，`records_collected > 0`。容器日志显示内置 Chromium 启动，`bridge | daemon=127.0.0.1:19825`。宿主机可关闭 Chrome，采集仍成功。

```bash
docker logs agent-1-chrome --tail=30
```

---

### Test 10 — Docker + 内置Chrome + CDP

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

sleep 25
curl -s $BASE/api/v1/tasks/$TASK_ID/runs?limit=1 | python3 -m json.tool
```

**预期**：`status=completed`，容器日志显示 `cdp | cmd=opencli v2ex hot -f json cdp=http://localhost:9222`（连接容器内部 Chromium CDP）。

---

## 结果验证

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

## 已知行为

- **重复数据返回 0 条**：同一来源的数据通过 `content_hash` 去重，重复触发同一数据源时 `records_collected=0` 但 `status=completed` 是正常现象。
- **`browser: false` 的站点（v2ex hot、HN 等）不区分 bridge/cdp**：这类站点直接调用公开 HTTP API，不使用浏览器，两种模式效果相同。需要验证 bridge 与 CDP 真实差异请使用需要浏览器的站点（如 linux-do、zhihu 等）。
- **COLLECTION_MODE 切换需重启 API**：这是系统级配置，对应用户修改 `.env` 后执行 `docker compose up -d api` 的正常运维操作。bridge/cdp 模式切换则无需重启，通过 `PATCH /mode` 接口实时生效。
- **Docker 测试前需在宿主机启动 Chrome**：agent 镜像默认使用无 Chrome 变体（约 400 MB），Tests 5-8 依赖宿主机 Chrome 通过 `host.docker.internal` 提供浏览器能力。如需完全自包含，在 `.env` 中设置 `INSTALL_CHROME=true` 和 `CHROME_SUFFIX=-chrome`，重启后会拉取 `-chrome` 变体（约 1.2 GB）。
- **切换 agent 容器后需清理旧节点**：手动 `docker stop/rm` 旧 agent 后，旧 endpoint 仍残留在 in-memory pool 中（节点 DB 也未清理）。切换前需通过 `DELETE /api/v1/nodes/{id}` 主动删除旧节点，或重启 API 让新 agent 重新注册后再清理。Tests 9-10 中切换到 `-chrome` 镜像时需先删除旧 `agent-1` 节点。
