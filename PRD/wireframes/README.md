# PRD 线框图约定（Excalidraw）

页面结构图统一使用 **Excalidraw** 绘制，源文件为 `.excalidraw` 格式（JSON），存放在本目录。

## 目录约定

| 文件 | 说明 |
|------|------|
| `01-login-desktop.excalidraw` | 登录页·桌面版线框**源文件**（对应 `pages/01-Login.md` §4.3，可编辑） |
| `01-login-desktop.excalidraw.svg` | 由源文件**自动生成**的 SVG，供 markdown/GitHub 渲染展示 |
| `01-login-mobile.excalidraw` | 登录页·移动版线框**源文件**（对应 §4.3，可编辑） |
| `01-login-mobile.excalidraw.svg` | 由源文件**自动生成**的 SVG |
| `convert.mjs` | 批量转换脚本：`.excalidraw` → `.excalidraw.svg` |
| `NN-<feature>-{desktop,mobile}.excalidraw` | 后续页面线框，命名与 `pages/NN-<feature>.md` 对应，每页含桌面/移动双形态 |

## 使用方式

- **编辑**：VS Code 中直接打开 `.excalidraw` 源文件进入画布编辑（需安装 `pomdtr.excalidraw-editor` 扩展）
- **生成渲染图**：修改源文件后运行 `node PRD/wireframes/convert.mjs`，重新生成对应 `.excalidraw.svg`
- **Markdown 引用**：引用**生成的 SVG**（而不是 `.excalidraw` 源文件），例如 `![登录页线框 · 桌面端](../wireframes/01-login-desktop.excalidraw.svg)`，GitHub 与 VS Code 预览均可原生渲染
- **双形态**：每页同时产出桌面版 + 移动版线框（移动优先策略，见 `pages/01-Login.md` §8）

## 规范

- **唯一事实源**：`.excalidraw` 源文件；SVG 是转换产物，不手工修改
- 每个页面一张线框图，作为页面结构（§ 页面结构）的唯一事实源
- 交互细节、状态与文案不在线框中体现，写于对应页面文档
- 修改源文件后，运行 `convert.mjs` 同步重新生成 SVG
