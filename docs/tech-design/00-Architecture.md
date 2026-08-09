# 整体架构设计文档（00-Architecture）

**产品**：地道英语纠错 · 智能笔记本
**版本**：V0.9 | **状态**：草稿 | **日期**：2026年8月
**对应 PRD**：`PRD/Overview.md`（总纲）、`PRD/pages/01-Login.md`、`PRD/pages/02-Correction.md`

> 本文档为技术设计总纲，回答「系统如何搭建」，定义**顶层契约**（技术选型、项目结构、数据契约、接口约定、AI 接入契约、部署）。功能级详细设计（页面组件、业务流程、场景矩阵）见各功能设计文档：
>
> - `01-Login.md` —— 登录功能详细设计
> - `02-Correction.md` —— 纠错功能详细设计
>
> **契约约定**：本文件定义的内容为顶层契约，各功能文档**引用不重复**；契约变更需联动更新引用方并记录变更记录。

## 〇、文档说明

- **范围**：全栈系统（前端、后端、数据存储、AI 集成、部署、认证）
- **读者**：前后端工程师、运维、产品（理解技术可行性）
- **与 PRD 的关系**：PRD 定义 what（功能与验收），本文档定义 how（实现与契约）
- **版本约定**：技术设计文档独立版本号，不纳入 PRD 版本约束；各文档末尾维护变更记录

## 一、技术选型

| 层 | 选型 | 版本 | 决策理由 |
|----|------|------|----------|
| 前端框架 | React SPA | 19 | 登录后交互型应用，无 SEO 需求，SPA 足够 |
| 前端构建 | Vite + TypeScript | — | 启动/构建快，TS 类型保障 |
| 样式 | TailwindCSS + shadcn/ui | — | Tailwind 主题 token 直接映射 `Visual-Style.md` 色板/圆角/间距/阴影；shadcn/ui 提供 Button/Input/Card 等基础组件 |
| 后端 | Python FastAPI + SQLAlchemy(async) + Pydantic | — | AI 生态成熟（openai sdk）、异步高性能、Pydantic 天然契合结构化输出校验 |
| 数据库 | PostgreSQL | 16 | 关系型建模会话/消息/纠错报告清晰，支持 JSONB 存报告结构 |
| LLM | OpenAI 兼容 API | — | `base_url`/`api_key`/`model` 可配置，未来可无缝切国内模型（通义/DeepSeek）或 BYOK |
| 部署 | Docker Compose | — | 本地/单机一键部署，db/api/web 三服务编排 |
| 反向代理 | nginx | — | 托管 SPA 构建产物 + 反代 `/api`，未来可加 TLS/限流 |

## 二、总体架构

### 2.1 系统组件图

```
                ┌─────────────┐
 Browser ──────▶│  nginx      │
 (桌面/手机)      │  (web 服务)  │
                └──────┬──────┘
                       │  /api 反代
                ┌──────▼──────┐         ┌──────────────┐
                │  FastAPI    │────────▶│  PostgreSQL  │
                │  (api 服务)  │         └──────────────┘
                └──────┬──────┘
                       │  OpenAI 兼容 HTTP
                ┌──────▼──────┐
                │  LLM API    │
                │(base_url 可配)│
                └─────────────┘
```

### 2.2 模块划分

| 模块 | 位置 | 职责 |
|------|------|------|
| `web` 前端 | `backend/` 之外独立工程 | 登录页、纠错主页；状态管理、组件、API 客户端 |
| `api` 后端 | `backend/` | 认证、会话/消息 CRUD、AI 编排（意图判定/纠错报告/追问）、错误处理 |
| `db` 数据库 | PostgreSQL | users/sessions/messages/reports 持久化 |
| `llm` 外部服务 | OpenAI 兼容 | 文本纠错与问答生成 |

### 2.3 请求链路

**登录**：浏览器 → nginx → FastAPI `/api/v1/auth/login` → 校验固定账号 → 签发 token → 返回 → 前端持久化 localStorage → 跳转纠错主页

**纠错**：浏览器 → FastAPI `/api/v1/messages` → 组装上下文（最近 N 条）→ LLM 意图判定 → 纠错则请求结构化报告 → 解析/校验 → 入库 → 返回前端

**追问**：同上链路，意图判定为追问 → LLM 纯文本讲解 → 入库 → 返回

## 三、项目结构

```
echo/
├── backend/                 FastAPI 工程
│   ├── app/
│   │   ├── main.py          应用入口
│   │   ├── core/            配置、安全、LLM 客户端
│   │   ├── models/          SQLAlchemy 模型
│   │   ├── schemas/         Pydantic 模型
│   │   ├── routers/         API 路由（auth / messages）
│   │   └── services/        业务逻辑（意图判定、报告解析、上下文组装）
│   ├── alembic/             DB 迁移
│   ├── Dockerfile
│   └── pyproject.toml / requirements.txt
├── web/                     React SPA 工程
│   ├── src/
│   │   ├── components/      组件（Button/Input/Card 等 + 业务组件）
│   │   ├── pages/           页面（Login / Correction）
│   │   ├── api/             API 客户端（fetch 封装、鉴权头注入）
│   │   ├── store/           状态管理
│   │   └── styles/          Tailwind 主题 token（映射 Visual-Style.md）
│   ├── nginx.conf           托管 SPA + 反代 /api
│   ├── Dockerfile
│   └── package.json / vite.config.ts
├── miniapp/                  （预留）后期小程序子项目，本期不创建实际工程
├── docker-compose.yml        db / api / web 三服务编排
├── docs/                     PRD / tech-design / superpowers
└── README.md
```

> **预留说明**：`miniapp/` 本期仅占位，后期新增小程序子项目时在此目录独立工程，复用 `backend` API 与顶层契约。

## 四、顶层数据契约

### 4.1 实体总览

> **命名约定**：本文档中「会话」指登录会话（`sessions`，认证令牌），「对话」指会话流（`session_conversations`，纠错历史）；二者为独立概念，勿混淆。**登录会话存储于数据库（`sessions` 表）**（详见 `01-Login.md` §2.2）。

| 实体 | 说明 | 归属文档 |
|------|------|----------|
| `users` | 账号（MVP 固定种子账号，含 `username`/`password_hash`/`status`） | `01-Login.md` 细化 |
| `sessions` | 登录会话（认证令牌，**DB 持久化**，含 token 哈希/有效期） | `01-Login.md` 细化 |
| `session_conversations` | 对话（会话流，DB 持久化） | `02-Correction.md` 细化 |
| `messages` | 消息（含消息 ID，DB 持久化） | `02-Correction.md` 细化 |
| `correction_reports` | 纠错报告（独立对象，自带 ID，DB 持久化） | `02-Correction.md` 细化 |

### 4.2 会话与消息（顶层约定）

- 按 `session_conversations → messages` 建模，`messages` 含唯一 `id`
- **纠错报告为独立数据对象**（自带 `report_id`），便于追问指代与后续错题提取（F-03）
- MVP 界面仅一个大会话，数据层预留对话维度，后期多对话管理为增量 UI 工作
- 登录会话 `sessions` 与对话 `session_conversations` 相互独立（见 §4.1 命名约定）；均持久化于 DB（登录会话存 `sessions` 表，对话/消息/报告存各自表），服务重启/多 worker 下登录态不丢失

#### 4.2.1 对话示例（`session_conversations` 是什么）

登录用户进入纠错主页后，**整个会话流就是一条对话记录**，其下挂一串消息（含纠错报告）：

```
session_conversations（对话表，DB 持久化）
┌──────────────────────────────────────────────────────┐
│ id: "conv_001"                                        │
│ user_id: "u_1"                                        │
│ created_at: 2026-08-08T10:00:00Z                     │
└──────────────────────────────────────────────────────┘
        │  1:N（按时间正序，每条含 id）
        ▼
messages（消息表，DB 持久化）
┌───────┬────────┬────────────┬───────────────────────────┐
│ id    │ role   │ 类型        │ content                    │
├───────┼────────┼────────────┼───────────────────────────┤
│ msg_1 │ user   │ correction │ "Yesterday I go to the..." │
│ msg_2 │ ai     │ report     │ report_id: "rep_001"       │
│ msg_3 │ user   │ follow-up  │ "为什么不能加 very？"       │
│ msg_4 │ ai     │ plain_text │ "delicious 是极限形容词…"   │
└───────┴────────┴────────────┴───────────────────────────┘
        │  1:1（报告为独立对象，便于追问指代/错题提取）
        ▼
correction_reports（纠错报告表，DB 持久化）
┌──────────────────────────────────────────────────────┐
│ report_id: "rep_001"                                  │
│ message_id: "msg_2"                                   │
│ structure: {错误分析: [...], 改写: {...}, 学到的规则: [...]}（JSONB）      │
└──────────────────────────────────────────────────────┘
```

> **对比**：登录会话 `sessions`（DB，认证凭证）`token_hash → {user_id, expires_at}` 只回答「是否已登录」；对话 `session_conversations`（DB）回答「这个用户的纠错历史是什么」。二者无关联、生命周期不同，勿混淆。

### 4.3 推理上下文与触顶截断（顶层约定）

- **数据库始终存全量历史**
- LLM 上下文：取当前会话**最近 N 条消息**（N 具体值由 `02-Correction.md` 或实现配置定义），防止上下文窗口溢出
- 不牺牲历史完整性：展示仍加载全量，仅送入 LLM 的上下文做截断

## 五、顶层接口约定

### 5.1 风格

- REST，前缀 `/api/v1`
- 请求/响应均 JSON（`Content-Type: application/json`）
- 鉴权：`Authorization: Bearer <token>`（除 `/auth/login` 外均需鉴权）
- 未鉴权/令牌失效返回 `401`

### 5.2 统一错误响应

```json
{
  "code": "AUTH_INVALID_CREDENTIALS",
  "message": "用户名或密码错误",
  "details": {}
}
```

| HTTP | 常见场景 |
|------|----------|
| 400 | 请求参数校验失败 |
| 401 | 未登录 / 令牌失效 |
| 404 | 资源不存在 |
| 429 | 限流（LLM 成本控制预留） |
| 500 | 服务异常 |
| 502 | LLM 返回无效（纠错功能，详见 `02-Correction.md` §4.3） |
| 503 | 服务降级/不可用（如 db 异常时的健康检查、LLM 未配置） |
| 504 | LLM 调用超时（纠错功能，详见 `02-Correction.md` §4.3） |

**健康检查**：`GET /api/v1/health`（**无需鉴权**）

- 200：`{ "status": "ok", "db": "connected" }`
- 503：`{ "status": "degraded", "db": "unavailable" }`（db 连接异常）

### 5.3 版本化契约

- 纠错报告结构与错误分类为版本化契约，变更需联动前端解析
- 接口向后兼容变更记录于各功能文档

## 六、顶层 AI 接入契约

### 6.1 接入方式

- OpenAI 兼容 Chat Completions API
- 配置项：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`（环境变量注入，见 §七）
- **非流式**（纠错报告一次性返回，保证结构完整可读，匹配 PRD 刻意取舍）

### 6.2 结构化输出

- 纠错报告通过 JSON 结构化输出（system prompt 约束 JSON schema + Pydantic 校验）
- 意图判定、纠错报告生成等**具体机制属纠错功能行为**，细节见 `02-Correction.md`，本文档不展开

### 6.3 意图判定顶层规则

- **AI 判断为主**（结合会话上下文），产品层兜底规则见 PRD `02-Correction.md` §4.3
- 意图判定的具体判定流程与提示词测试矩阵见 `02-Correction.md`（§4.3、§八），本文档仅定义顶层约束

## 七、部署与运维

### 7.1 Docker Compose 拓扑

| 服务 | 镜像 | 端口 | 依赖 |
|------|------|------|------|
| `db` | postgres:16 | 5432（内部） | — |
| `api` | backend Dockerfile | 8000（内部） | db |
| `web` | nginx（托管 SPA + 反代） | 80 | api |

**nginx 配置要点**：

- `location / { try_files $uri /index.html; }` —— SPA 客户端路由回退，刷新深链不 404
- `location /api/ { proxy_pass http://api:8000; }` —— 反代后端 API（同源，无需 CORS）

> **开发环境（本地 Vite dev server）**：本地开发前端直连 `http://localhost:8000`（跨源），需 FastAPI 启用 CORS 中间件，仅放行开发源（如 `http://localhost:5173`）；生产经 nginx 同源反代，无需 CORS。

### 7.2 环境变量清单

| 变量 | 用途 |
|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | LLM 配置 |
| `SESSION_TTL_DAYS` | 会话有效期（默认 30） |
| `CONTEXT_LIMIT` | LLM 上下文最近 N 条（默认 **40**） |

### 7.3 日志与成本控制

- 结构化日志（请求 ID、耗时、token 用量）
- 成本控制：上下文触顶截断、错误分类契约化减少重复生成、预留限流（429）

## 八、跨模块 Scenario 总览

> 单模块详细场景见各功能文档的场景矩阵。此处仅列**跨模块**/全链路场景。

| 场景 | 前置 | 触发 | 预期 | 关联 |
|------|------|------|------|------|
| 全链路：登录→纠错→追问 | 未登录 | 登录成功后提交英文再追问 | 各步正常，历史持久化 | AC-L-01 / AC-C-01 / AC-C-13 |
| 会话过期时提交纠错 | 会话已过期 | 提交英文 | 401 → **保留当前页面**，提示「会话已过期，请重新登录」，输入内容保留不丢失 | AC-L-08 / AC-C-08 |
| token 失效后刷新页面 | 令牌失效 | 刷新页面 | 重定向登录页，重新登录后历史仍在 | AC-L-08 / AC-C-11 |
| LLM 服务异常 | LLM 不可用 | 提交纠错 | 返回 5xx 或超时 120s，前端提示重试，消息保留 | AC-C-08 / PRD §4.8 |
| 账号数据隔离 | 多账号（后期） | 不同账号访问 | 数据按账号隔离（本期单账号，模型已预留 user_id） | PRD §3.2 |

## 九、系统级验证（冒烟）

> 功能级验证（API 契约 + UI 走查）见各功能文档「验证方式」章节。此处为**系统级冒烟**，验证三服务编排与全链路连通。

| # | 检查项 | 操作 | 预期 |
|---|--------|------|------|
| S-01 | 服务编排 | `docker compose up -d` | db/api/web 三容器健康启动，web 映射 80 |
| S-02 | 数据库初始化 | 检查容器日志 | alembic 迁移成功，种子账号已创建 |
| S-03 | 健康检查 | `GET /api/v1/health` | 200，返回 db 连接状态 |
| S-04 | 静态资源 | 浏览器访问 `/` | 加载 SPA 登录页 |
| S-05 | 反代连通 | 浏览器访问 `/api/v1/...` | nginx 正确反代到 api 服务 |

> 验证顺序：S-01~S-05（系统就绪）→ 功能文档 API 验证 → 功能文档 UI 验证。纠错/追问等依赖纠错功能的验证项不在本总览中，见 `02-Correction.md`。

---

**变更记录**

- V0.9 · 2026-08 · §4.2.1 correction_reports.structure 示例补充「学到的规则」字段（learnings，同步 Correction V2.6 / 技术设计 02-Correction V0.3）

- V0.8 · 2026-08 · §5.2 补充 502/504 错误码（LLM 返回无效/超时，纠错功能使用）；§7.2 `CONTEXT_LIMIT` 默认值定为 40；§〇 功能文档指针更新（02-Correction 已完成）
- V0.7 · 2026-08 · §7.1 补充开发环境 CORS 说明（本地 Vite 直连 api 跨源需 FastAPI CORS 中间件；生产 nginx 同源无需）
- V0.6 · 2026-08 · 登录会话改回 DB 存储（`sessions` 表，服务重启/多 worker 不失效）；§6 意图判定细节收敛至 02-Correction；新增 health 契约与 nginx SPA 回退要点；删除 S-06 及「服务重启失效」场景（纠错/追问验证移出本总览）
- V0.5 · 2026-08 · 新增 §九 系统级验证（冒烟 S-01~S-06），明确「系统就绪→API→UI」验证顺序
- V0.4 · 2026-08 · `users` 实体注明字段（含 `status` 状态），与 Login V0.3 对齐
- V0.3 · 2026-08 · §4.2 新增对话示例（`session_conversations`/`messages`/`correction_reports` 关系图）与登录会话对比说明，消除命名歧义
- V0.2 · 2026-08 · 登录会话改为服务端内存存储（`sessions` 不落 DB）；会话过期提交纠错改为保留页面提示重登
- V0.1 · 2026-08 · 初稿：技术选型（React+FastAPI+PostgreSQL+OpenAI 兼容+Docker Compose）、项目结构、顶层数据/接口/AI 契约、部署与跨模块 Scenario

*本文档将随系统演进持续更新。*
