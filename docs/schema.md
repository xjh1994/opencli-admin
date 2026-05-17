# 数据模型

本文档描述 opencli-admin 写入数据库的核心表 `collected_records` 的实际结构与字段语义。

由于历史/兼容原因，标准字段（标题/正文/作者/链接/发布时间）**不是顶层列**，而是嵌在 `normalized_data` JSON 列里。任何下游消费者（AI 处理、自定义查询、外部 worker）都需要从 JSON 中提取而不是直接 `SELECT title`。

## `collected_records` 表

SQLAlchemy 模型：[`backend/models/record.py`](../backend/models/record.py)

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 主键 |
| `task_id` | TEXT (UUID) | 外键 → `collection_tasks.id`，级联删除 |
| `source_id` | TEXT (UUID) | 数据源 ID（不是平台名；下游若需要平台名走 `collection_sources` join） |
| `raw_data` | JSON | 渠道原样返回的 dict，未做字段对齐 |
| `normalized_data` | JSON | **下游应消费的标准字段**，详见下表 |
| `ai_enrichment` | JSON / NULL | AI processor 写回的 enrichment；schema 由 processor + prompt 决定，无强制契约 |
| `content_hash` | TEXT (sha256) | `(source_id, content_hash)` 唯一约束用于去重 |
| `status` | TEXT | `raw` → `normalized` → `ai_processed` → `notified`；失败为 `error` |
| `error_message` | TEXT / NULL | `status='error'` 时填错误描述 |
| `created_at` | DATETIME | 入库时间 |
| `updated_at` | DATETIME | 末次更新（含 AI 回填） |

唯一约束：`uq_source_content (source_id, content_hash)`。

## `normalized_data` JSON 内的标准字段

归一逻辑在 [`backend/pipeline/normalizer.py`](../backend/pipeline/normalizer.py) — 来自各渠道的字段被映射到统一 key。

| Key | 类型 | 含义 | 渠道侧别名（择优取首个非空） |
|---|---|---|---|
| `title` | str | 标题 | `title` / `name` / `word` / `topic` / `headline` / `subject` |
| `url` | str | 原文链接 | `url` / `link` / `href` / `permalink` |
| `content` | str | 正文 / 描述 | `content` / `text` / `body` / `summary` / `description` |
| `author` | str | 作者 / 频道 / 用户 | `author` / `channel` / `creator` / `by` / `user` |
| `published_at` | str | 发布时间（原始格式） | `created_at` / `published_at` / `published` / `date` / `time` / `listed` / `updated` / `timestamp` |
| `source_id` | str | 来源 ID（与列复制） | — |
| `extra_*` | any | 渠道独有字段，保留为 `extra_<原 key>` | — |

**注意**：

- 字段值类型当前都是 `str`（normalizer 跳过非 str），即使原始是数字 / 时间戳。
- `published_at` 是 raw 字符串（"2 hours ago"、ISO8601、unix epoch 字符串等都可能出现）；下游需要标准化时间需自行解析。
- 缺字段会写空串 `""`，不是 `null` —— 查询时用 `LIKE '%...%'` 或 `!=''` 而非 `IS NOT NULL`。

## 从 SQLite 查询的正确姿势

下游消费 `normalized_data` 字段必须走 `json_extract`：

```sql
-- ✗ 错：title 不是列
SELECT id, title FROM collected_records WHERE title LIKE '%X%';

-- ✓ 对：从 JSON 字段提取
SELECT id,
       json_extract(normalized_data, '$.title')        AS title,
       json_extract(normalized_data, '$.author')       AS author,
       source_id,
       json_extract(normalized_data, '$.published_at') AS published_at
FROM collected_records
WHERE json_extract(normalized_data, '$.title')   LIKE ?
   OR json_extract(normalized_data, '$.content') LIKE ?
ORDER BY created_at DESC
LIMIT ?;
```

Postgres 用 `normalized_data->>'title'`（等价）。

## `status` 状态机

记录从入库到完成的转移：

```
        normalize         AI processor
raw ─────────────► normalized ─────────────► ai_processed
                       │                          │
                       │                          ▼
                       │                      notified
                       ▼
                     error  (处理失败时任意阶段都可能进入)
```

- `raw` —— 仅当 normalize 还没跑过；正常情况看不到这个 status，存在仅为 schema 兜底
- `normalized` —— normalize 写入后、AI 处理前
- `ai_processed` —— `ai_enrichment` 已经填好
- `notified` —— 已推送到通知通道
- `error` —— 错误详情在 `error_message`

## `ai_enrichment` 内容

由 AI processor 写入，**当前无 schema 校验**。各 processor 的行为：

- `claude_processor` / `openai_processor`：尝试 `json.loads(response)`；失败 fallback 到 `{"analysis": <raw text>}`；processor 异常写 `{"error": <message>}`
- `local_processor`：同上模式
- `external_http`（如启用）：若配置带 `response_schema` 则做 JSON Schema 校验，否则同上

prompt 模板由用户在「AI 智能体」界面配置，决定输出形状。常见 key：

| Key | 含义 |
|---|---|
| `summary` | 摘要 |
| `tags` | 标签数组 |
| `sentiment` | 情感 |
| `priority` | 优先级（1-5） |
| `analysis` | 自由文本（json 解析失败时的 fallback 槽） |
| `error` | processor 抛错时的错误消息 |

下游若要稳定消费 `ai_enrichment`，需在 prompt 里固定 JSON 结构并由消费者做防御性 `.get(...)` 访问。

## 并发写注意

SQLite 默认配置下，AI 回填 + 多 task 并发采集容易触发 `database is locked`。生产场景建议：

- 启 WAL 模式（`PRAGMA journal_mode=WAL`）
- 多节点 / 多写入器场景切到 Postgres profile（`.env.example` 中的 `DATABASE_URL` 注释）
