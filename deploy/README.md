# 部署指南（阿里云 ECS · 单机 Docker Compose + GHCR + Caddy）

**目标**：`git push origin v0.1` → GitHub Actions 自动构建镜像、推送到 GHCR、SSH 到服务器完成部署。

## 架构

```
开发者 ── git push v0.1 ─▶ GitHub Actions
                             │ ① build api/web 镜像 → push GHCR
                             │ ② SSH 服务器: clone/pull → 写 .env → pull 镜像 → up -d
ECS 2C2G: 80/443 ─▶ caddy(自动 HTTPS) ─▶ web:80(nginx) ─▶ api:8000 ─▶ db:5432
```

服务器使用自包含生产编排文件 `deploy/docker-compose.prod.yml`（db/api/web/proxy），
db/api 不对公网暴露端口，仅 proxy 映射 80/443。

## 一、一次性设置

> 以下均在**首次部署前**手动执行一次，之后完全自动化。

### 1. 服务器初始化（SSH 登录服务器执行）

```bash
# ① 安装 Docker Engine + compose 插件

## Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 当前用户加入 docker 组（root 可跳过）

## 阿里云服务器（Aliyun Linux / alinux）——get.docker.com 不支持，改用阿里云镜像源
cat /etc/os-release        # 确认 alinux2(对应 CentOS7) 或 alinux3(对应 CentOS8)
yum install -y yum-utils
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
# alinux3 → sed 用 8；alinux2 → sed 用 7
sed -i 's/\$releasever/8/g' /etc/yum.repos.d/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
docker version && docker compose version   # 两个都有输出即就绪

# ② 加 2G swap（2G 内存兜底）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# ③ SSH 建议改为密钥登录并禁用密码（可选但推荐）
```

要求：Docker Engine + Docker Compose 插件（`docker compose version` 可用即可；`git` 若缺失，CI 部署时会在服务器自动安装）。

### 2. DNS 解析

在阿里云控制台为域名添加 A 记录：

| 主机记录 | 类型 | 值 |
|----------|------|----|
| `echo` | A | 服务器公网 IP |

### 3. 安全组

放行入方向：`22`（SSH）、`80`（HTTP）、`443`（HTTPS）。**不要**放行 `5432`/`8000`。

### 4. GitHub Deploy Key（服务器 clone 私有仓库用）

本地生成一对只读密钥，公钥加入仓库：

```bash
ssh-keygen -t ed25519 -C "echo-deploy" -f ~/.ssh/echo_deploy -N ""
cat ~/.ssh/echo_deploy.pub
```

- GitHub 仓库 → `Settings → Deploy keys → Add deploy key`：粘贴公钥，勾选 **Allow write access 不勾选**（只读）
- 私钥内容作为 secret `REPO_DEPLOY_KEY`，**推荐先 base64 编码**（多行私钥经 Actions 环境变量传递易损坏）：

```bash
base64 < ~/.ssh/echo_deploy | pbcopy   # macOS 进剪贴板；Linux 用 base64 ~/.ssh/echo_deploy
```

> 也支持直接粘贴私钥原样内容（脚本会自动兼容），但 base64 单行传递最可靠。

### 5. GitHub 仓库 Secrets

仓库 `Settings → Secrets and variables → Actions → New repository secret`：

| Secret | 说明 |
|--------|------|
| `SSH_HOST` | 服务器公网 IP |
| `SSH_USER` | SSH 用户（建议 root，或已加入 docker 组的用户） |
| `SSH_KEY` | 连接服务器用的 SSH 私钥（完整内容，含首尾） |
| `REPO_DEPLOY_KEY` | 上一步生成的 Deploy Key 私钥（完整内容，含首尾） |
| `DB_PASSWORD` | 随机生成：`openssl rand -hex 16` |
| `LLM_BASE_URL` | 百炼 compatible-mode 地址 |
| `LLM_API_KEY` | 百炼 API Key |
| `LLM_MODEL` | 如 `glm-5.2` |
| `GHCR_USER` | GitHub 用户名（推送/拉取 GHCR 用） |
| `GHCR_PAT` | GitHub PAT，需 `read:packages` 权限（服务器拉取私有镜像） |

`GHCR_PAT` 创建：GitHub → `Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token`，选仓库 `shawn-ann/echo`，权限勾选 `Packages → Read packages` 和 `Metadata → Read`，生成后复制为 secret。

> 说明：secrets 配在 `prod` **环境**中（workflow 已 `environment: prod`）。`appleboy/ssh-action` 的 `envs` 需要配合步骤级 `env:` 映射才能把变量转发到服务器，已在 deploy.yml 中配置。

## 二、首次部署

```bash
git push origin v0.1
```

Actions 自动：构建 api/web 镜像 → 推 GHCR → SSH 服务器（首次自动 clone）→ 写 `.env` → `pull + up -d`。

## 三、验证

```bash
curl https://echo.hootooa.com/api/v1/health
# {"status":"ok","db":"connected"}
```

浏览器打开 `https://echo.hootooa.com` → `demo / demo1234` 登录 → 发一条英文纠错验证真实 LLM 链路。

## 四、日常更新

```bash
git add . && git commit -m "..." && git push origin v0.1   # 全自动部署
```

## 五、数据库备份

服务器上配置每日备份（crontab）：

```bash
crontab -e
# 添加：
0 3 * * * /root/echo/deploy/backup.sh >> /var/log/echo-backup.log 2>&1
```

备份到 `/var/backups/echo/`，保留 14 天。手动恢复：

```bash
gunzip -c /var/backups/echo/echo-YYYYMMDD-HHMMSS.sql.gz | docker exec -i echo-db-1 psql -U echo -d echo
```

## 六、本地生产镜像自检（可选）

```bash
# 校验生产 compose 文件语法（无需镜像即可验证解析）
docker compose -f deploy/docker-compose.prod.yml config
```

## 七、注意事项

- **服务器不构建代码**：镜像由 CI 在 GitHub 构建推送 GHCR，服务器只 `pull`，2G 内存无 OOM 风险
- **生产 compose 自包含**：`deploy/docker-compose.prod.yml` 独立定义 db/api/web/proxy，不合并本地开发用的 `docker-compose.yml`；db/api 均不对公网暴露端口，只有 proxy 映射 80/443
- **前端 API 指向**：构建时注入 `VITE_API_BASE_URL=/api/v1`（同源），由 nginx `/api/` 反代到后端
- **LLM 密钥不进 GitHub**：只在服务器 `.env`（CI 从 Secrets 自动生成），镜像内无密钥
- 若服务器 SSH_USER 非 root：需保证该用户对 `$HOME/echo` 有写权限、已加入 docker 组
