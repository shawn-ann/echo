---
description: 用 Playwright MCP 对本地前端执行登录功能验收走查
agent: build
---

用 Playwright MCP 对运行中的前端执行登录功能验收。

前置：确保服务已启动
- db：`docker compose up -d db`
- 后端：`backend/.venv/bin/uvicorn app.main:app --port 8000`
- 前端：`cd web && npm run dev -- --port 5173`（Node 24：`source ~/.nvm/nvm.sh && nvm use 24`）

验收步骤（使用 Playwright MCP 的 browser_navigate / browser_snapshot / browser_fill_form / browser_click / browser_wait_for）：

1. 导航到 http://localhost:5173/login，快照确认登录表单（用户名 / 密码 / 登录按钮）渲染正常
2. 空用户名提交 → 应提示「请输入用户名」且不跳转
3. 空密码提交 → 应提示「请输入密码」
4. 错误密码（demo / wrong）→ 应提示「用户名或密码错误」，密码框清空、用户名保留
5. 正确账号（demo / demo1234）登录 → 应进入 /correction，导航栏显示 demo 与「退出」
6. 刷新页面应保持登录态；点「退出」应回到 /login
7. 未登录直接访问 /correction 应重定向到 /login
8. 手机宽度（375px）访问登录页应正常渲染

对照 PRD/pages/01-Login.md §7.2 的 U-L-01~09 逐条核验，报告每条通过/失败及证据（截图或快照）。
