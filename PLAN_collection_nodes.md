# 采集节点页面重构计划

> **状态：已完成** (2026-03-21)
>
> 最终实现与原计划略有差异：没有使用三个 Tab，而是采用"采集模式"卡片切换（本地模式 / Agent 模式），
> 本地模式展示本地 Chrome 端点（Bridge/CDP 切换），Agent 模式展示节点列表 + 新增节点向导。
> Docker Chrome 实例区已从 UI 移除。`/browsers` 重定向到 `/nodes`，`BrowsersPage.tsx` 不再使用。

## 背景

当前路由/页面混乱：
- `/browsers` 路由名称来自早期只有浏览器实例的时候，现在有了 agent 节点概念后显得模糊
- 我把 `/browsers` 映射回 `BrowsersPage` 后，`NodesPage`（管理 EdgeNode/agent 注册）失去路由入口，导致"添加 agent"入口丢失
- 浏览器（Browser）是归属于节点（Node）的，应该是节点包含浏览器，不是并列

## 目标架构

### 路由改动

| 旧路由 | 新路由 | 说明 |
|--------|--------|------|
| `/browsers` | `/nodes` | 重命名，语义更准确 |

### 新"采集节点"页面（`/nodes`）— 三个 Tab

**Tab 1：本地直连**
- 适用场景：shell 部署，中心直连本地 Chrome，不经过 agent
- 内容：`BrowsersPage` 里"本地浏览器"卡片区（`instanceIndex === null` 的端点）
- 功能：Bridge/CDP 模式切换、站点绑定

**Tab 2：本地 Agent**
- 适用场景：本地运行 agent_server.py，中心通过 localhost agent 采集
- 内容：`NodesPage` 里 `agent_url` 为 localhost 的节点
- 功能：查看状态、切换模式、查看事件

**Tab 3：远端 Agent**
- 适用场景：多机分布式部署，远端 agent 注册到中心
- 内容：`NodesPage` 里 `agent_url` 为非 localhost 的节点
- 功能：查看状态、添加 agent（安装脚本/手动注册）、删除、查看事件

**保留**：Docker 实例卡片（`instanceIndex !== null` 的端点，即 agent-N 容器）放在"远端 Agent" tab 里或单独的 Docker tab

### Docker 实例去向
Docker Chrome 容器（`agent-1:19222` 格式）是 Docker 模式下的"本地 agent"，放在 Tab 2 或单独 Tab 4"Docker 实例"均可。优先简单，先合并到 Tab 2。

## 文件改动清单

1. **`frontend/src/App.tsx`**
   - 删除 `BrowsersPage` import（或保留）
   - 新增统一页面（或直接复用 NodesPage + 新 tab）
   - 路由：`"browsers"` → `"nodes"`，element 改为新页面

2. **`frontend/src/components/Layout.tsx`**
   - nav 链接：`/browsers` → `/nodes`
   - ROUTE_LABELS 更新

3. **`frontend/src/pages/NodesPage.tsx`**（主力页面）
   - 加入 Tab 切换（本地直连 / 本地 Agent / 远端 Agent）
   - Tab 1 内容：从 BrowsersPage 抽取本地端点卡片 + 模式切换
   - Tab 2/3 内容：现有 NodesPage 内容按 localhost 过滤分组

4. **`frontend/src/pages/BrowsersPage.tsx`**
   - 可能保留 Docker 实例管理部分，或将 Docker 实例卡片也迁移到 NodesPage
   - 若迁移完毕可废弃此文件

## 执行顺序

1. 先在 Layout.tsx 和 App.tsx 改路由 `/browsers` → `/nodes`，同时把 element 改为 NodesPage（先恢复"添加 agent"功能）
2. 在 NodesPage 里加 Tab 切换
3. 把 BrowsersPage 的"本地直连"内容（本地端点卡片 + 模式切换）移植到 NodesPage Tab 1
4. 处理 Docker 实例的归属（暂时放 Tab 1 或 Tab 2）
5. 更新 i18n、文档注释

## 注意事项

- `BrowsersPage` 的 `ModeToggle`、`InstanceCard`、`SiteDropdown` 等子组件可能需要提取到独立文件复用
- `NodesPage` 里已经有 `collection_mode` 切换（local/agent），确保 Tab 切换不与此冲突
- Docker 实例的"新增实例"/"重启 API"功能要保留入口
