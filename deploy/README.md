# 部署指南（阿里云 ECS · 单机 Docker Compose + ACR + Caddy）

**线上地址**：`https://echo.hootooa.com`

**目标**：`git push origin v0.2` → GitHub Actions 自动构建镜像、推送到阿里云 ACR、SSH 到服务器完成部署。

## 架构

```
开发者 ── git push v0.2 ─▶ GitHub Actions
                             │ ① build api/web 镜像 → push 阿里云 ACR
                             │ ② SSH 服务器: 自动装工具 → clone/pull → 写 .env → pull 镜像 → up -d
ECS 2C2G: 80/443 ─▶ caddy(自动 HTTPS) ─▶ web:80(nginx) ─▶ api:8000 ─▶ db:5432
```

镜像仓库：阿里云 ACR 个人版 `crpi-euvhe8kkdkzzannx.cn-hangzhou.personal.cr.aliyuncs.com`，命名空间 `echo-rep`，镜像 `api`/`web`。

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
cat /etc/os-release        # alinux2→CentOS7；alinux3/alinux4(OpenAnolis)→CentOS8
yum install -y yum-utils
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
# alinux3/alinux4 → sed 用 8；alinux2 → sed 用 7
sed -i 's/\$releasever/8/g' /etc/yum.repos.d/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
docker version && docker compose version   # 两个都有输出即就绪

# ② swap（2G 内存兜底；部分镜像自带 swap，用 swapon --show 确认后跳过）
sudo fallocate -l 2G /swapfile || true
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# ③ SSH 建议改为密钥登录并禁用密码（可选但推荐）
```

要求：Docker Engine + Docker Compose 插件（`docker compose version` 可用即可；`git` 若缺失，CI 部署时会在服务器自动安装）。

**大陆服务器 Docker Hub 镜像说明**：`db`（postgres）与 `proxy`（caddy）镜像来自 Docker Hub，
大陆 ECS 直连 Docker Hub 常被重置。两种处理：
- 服务器配置镜像加速器 `/etc/docker/daemon.json`（`{"registry-mirrors": [...]}`）后 `systemctl restart docker`；或
- 手动拉取缓存：`docker pull postgres:15-alpine && docker pull caddy:2-alpine`（一次即可，Compose 检测到本地已有则不再拉）

### 2. DNS 解析

在阿里云控制台为域名添加 A 记录：

| 主机记录 | 类型 | 值 |
|----------|------|----|
| `echo` | A | 服务器公网 IP |

### 3. 安全组

放行入方向：`22`（SSH）、`80`（HTTP）、`443`（HTTPS）。**不要**放行 `5432`/`8000`。

### 4. GitHub Deploy Key（服务器 clone 私有仓库用）

workflow 会**优先使用服务器上的 key 文件**（`~/.ssh/echo_deploy_key`），不存在时才回退用 secret。

**方式 A（推荐，手动放置一次，最可靠）**：
```bash
# 本机生成一对只读密钥
ssh-keygen -t ed25519 -C "echo-deploy" -f ~/.ssh/echo_deploy -N ""
cat ~/.ssh/echo_deploy.pub     # ① 公钥加到 GitHub：Settings → Deploy keys（只读，不勾 write）
# ② 私钥传到服务器并校验
scp ~/.ssh/echo_deploy root@<服务器IP>:~/.ssh/echo_deploy_key
ssh root@<服务器IP> "chmod 600 ~/.ssh/echo_deploy_key && ssh-keygen -y -f ~/.ssh/echo_deploy_key"
```

**方式 B（secret 兜底）**：私钥 base64 后作为 secret `REPO_DEPLOY_KEY`：
```bash
base64 < ~/.ssh/echo_deploy | pbcopy   # macOS 进剪贴板；Linux 用 base64 ~/.ssh/echo_deploy
```

> 多行私钥经 Actions 环境变量传递曾出现损坏（`error in libcrypto`），故推荐方式 A 手动放置，一次配置永久有效。

### 5. GitHub 仓库 Secrets

**位置**：仓库 `Settings → Environments → prod → Environment secrets`（workflow 已声明 `environment: prod`）。

| Secret | 说明 |
|--------|------|
| `SSH_HOST` | 服务器公网 IP |
| `SSH_USER` | SSH 用户（当前为 `root`） |
| `SSH_KEY` | 连接服务器用的 SSH 私钥（完整内容，含首尾） |
| `REPO_DEPLOY_KEY` | Deploy Key 私钥 base64（方式 A 放置后仍建议配置作兜底） |
| `DB_PASSWORD` | 随机生成：`openssl rand -hex 16` |
| `LLM_BASE_URL` | 百炼 compatible-mode 地址 |
| `LLM_API_KEY` | 百炼 API Key |
| `LLM_MODEL` | 如 `glm-5.2` |
| `ACR_USER` | ACR 登录用户名（阿里云账号，如 `夏明湖畔的大雨荷`） |
| `ACR_PASSWORD` | ACR **固定密码**（容器镜像服务 → 访问凭证 → 固定密码） |

> 技术要点：`appleboy/ssh-action` 的 `envs` 必须配合步骤级 `env:` 映射才能把 secret 转发到服务器（已在 deploy.yml 配置），否则服务器上变量为空。

## 二、首次部署

```bash
git push origin v0.2
```

Actions（`deploy.yml`）自动执行：
1. 构建 api/web 镜像 → 推阿里云 ACR（`echo-rep/api`、`echo-rep/web`）
2. SSH 服务器，幂等脚本 [0/6]~[5/6]：确保 git/compose → 准备 deploy key → 校验 GitHub 认证 → clone/pull 仓库 → 写 `.env` → 登录 ACR 拉镜像 → `up -d`

## 三、验证

```bash
curl https://echo.hootooa.com/api/v1/health
# {"status":"ok","db":"connected"}
```

浏览器打开 `https://echo.hootooa.com` → 登录（内置账号 `shawn`，密码见仓库 `backend/app/core/config.py` 的 `SEED_PASSWORD`）→ 发一条英文纠错验证真实 LLM 链路。
## 四、日常更新

```bash
git add . && git commit -m "..." && git push origin v0.2   # 全自动部署
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

- **服务器不构建代码**：镜像由 CI 在 GitHub 构建推 ACR，服务器只 `pull`，2G 内存无 OOM 风险
- **ACR 推送**：buildx 需关闭 `provenance`/`sbom` 附件清单，否则 ACR 报 `denied: unknown manifest class for application/vnd.oci.empty.v1+json`（已在 workflow 处理）
- **生产 compose 自包含**：`deploy/docker-compose.prod.yml` 独立定义 db/api/web/proxy，不合并本地开发用的 `docker-compose.yml`；db/api 均不对公网暴露端口，只有 proxy 映射 80/443
- **前端 API 指向**：构建时注入 `VITE_API_BASE_URL=/api/v1`（同源），由 nginx `/api/` 反代到后端
- **LLM 密钥不进 GitHub**：只在服务器 `.env`（CI 从 Secrets 自动生成），镜像内无密钥
- **GitHub 网络**：大陆访问 GitHub 可能不稳定，push 失败重试即可；workflow 触发后可到 Actions 查看
- 若服务器 SSH_USER 非 root：需保证该用户对 `$HOME/echo` 有写权限、已加入 docker 组
