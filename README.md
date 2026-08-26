# Echo · 地道英语纠错 · 智能笔记本

基于大模型的英语学习工具：会话式纠错 + 追问，定位「会帮你记住每一个错误的 AI 英语教练」。

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 19 + Vite + TypeScript + TailwindCSS + shadcn/ui |
| 后端 | Python FastAPI + SQLAlchemy(async) + Pydantic |
| 数据库 | PostgreSQL 16 |
| LLM | OpenAI 兼容 API（可配置，登录阶段未使用） |
| 部署 | Docker Compose（db / api / web） |

> 详细设计见 `PRD/` 与 `docs/tech-design/`。

## 本地开发

### 1. 启动数据库

```bash
docker compose up -d db
```

### 2. 后端

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head      # 建表（首次或迁移后）
uvicorn app.main:app --reload --port 8000
```

服务启动后自动种子化内置固定账号 `demo / demo1234`。

### 3. 前端

```bash
cd web
npm install
npm run dev               # 默认 http://localhost:5173，/api 直连 http://localhost:8000（CORS 已放行）
```

### 4. 接口测试（API 契约验收）

```bash
cd backend
pytest -v
```

### 5. 前端自动验证（E2E + Playwright MCP）

**E2E 测试**（覆盖登录 U-L-01~09 验收，使用系统 Chrome，免下载浏览器）：

```bash
docker compose up -d db          # 前置：数据库
cd web
source ~/.nvm/nvm.sh && nvm use 24   # Vite 8 需要 Node ≥22
npm run test:e2e                  # 自动起后端+前端并运行 tests/e2e/login.spec.ts
```

**Playwright MCP**（opencode 中 agent 驱动浏览器走查）：配置见 `opencode.json`，重启 opencode 后生效；在会话中执行 `/frontend-check` 命令按 U-L-01~09 走查。

## API 概览（前缀 `/api/v1`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | 无 | 健康检查 |
| POST | `/auth/login` | 无 | 登录，返回 token |
| POST | `/auth/logout` | Bearer | 退出登录 |
| GET | `/auth/me` | Bearer | 当前用户信息 |

统一错误响应：`{ "code": "...", "message": "...", "details": {} }`。

## 部署

**本地开发（一键编排）**：
```bash
docker compose up -d --build   # db + api + web 三服务编排，web 映射 80
```

**生产环境（阿里云 ECS）**：`git push origin v0.1` 即自动构建镜像到阿里云 ACR 并部署到服务器，线上 `https://echo.hootooa.com`。详见 [`deploy/README.md`](deploy/README.md)。
