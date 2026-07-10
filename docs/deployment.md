# AssetVault 部署说明

本文档用于说明 AssetVault 的本地开发启动、Docker Compose 启动、目录挂载和验证流程。

## 1. 本地开发启动

### 1.1 后端

```bash
uv sync
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认连接本机 PostgreSQL：

```text
postgresql+psycopg://assetvault:assetvault@127.0.0.1:5432/assetvault
```

默认 API 地址：

```text
http://127.0.0.1:8000
```

后端启动时会同时启动 PostgreSQL 持久化任务 Worker。扫描和 Embedding API 只创建任务，
Worker 随后原子领取并执行；服务中断时任务记录不会丢失。可按需要调整：

```text
ASSETVAULT_TASK_WORKER_ENABLED=true
ASSETVAULT_TASK_WORKER_POLL_SECONDS=1
ASSETVAULT_TASK_STALE_AFTER_SECONDS=900
ASSETVAULT_TASK_RETRY_DELAY_SECONDS=5
```

`TASK_STALE_AFTER_SECONDS` 应大于单批 Embedding 或扫描进度提交的最长间隔，避免仍在工作的
任务被误判为僵尸任务。仅运行 API、不执行后台任务的实例可以关闭 Worker。

### 1.2 前端

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：

```text
http://localhost:3000
```

如果 3000 端口被占用，Next.js 会自动切换到 3001 或其他可用端口。

## 2. Docker Compose 启动

复制环境变量示例：

```bash
copy .env.example .env
```

按需要修改 `.env`：

```text
ASSETVAULT_SECRET_KEY=replace-with-a-long-random-secret
ASSETVAULT_AUTH_MODE=local
ASSETVAULT_ASSET_ROOT=./demo-assets
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

启动：

```bash
docker compose up --build
```

访问：

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

## 3. 素材目录挂载

### 3.1 认证模式与网络边界

`local` 是默认模式，无需登录，仅适合受信任的单机环境。Docker Compose 的前后端端口
默认绑定到 `127.0.0.1`，不要将免登录后端直接暴露到局域网或公网。

远程访问必须设置 `ASSETVAULT_AUTH_MODE=password` 并配置高强度
`ASSETVAULT_SECRET_KEY`。密码模式保留注册、JWT 登录和按用户隔离数据库记录的能力，
但这种隔离不等同于操作系统级文件权限隔离；后端进程能够读取的挂载目录仍属于同一主机权限边界。

如果本地数据库已有多个用户，必须通过 `ASSETVAULT_LOCAL_USER_ID` 明确选择工作区用户。

Docker Compose 默认将：

```text
${ASSETVAULT_ASSET_ROOT:-./demo-assets}
```

挂载到容器内：

```text
/assets
```

因此，在 Docker 运行模式下，前端添加素材目录时应填写容器内路径，例如：

```text
/assets
```

如果你的素材在 Windows 的 `E:\Assets`，可以在 `.env` 中设置：

```text
ASSETVAULT_ASSET_ROOT=E:\Assets
```

然后在 AssetVault 中添加：

```text
/assets
```

## 4. 数据持久化

Compose 使用四个 volume：

```text
assetvault-postgres  PostgreSQL 数据
assetvault-cache     缩略图缓存
assetvault-backups   数据库备份
assetvault-models    BGE-M3 模型缓存
```

默认数据库服务：

```text
postgres:5432/assetvault
```

默认缩略图目录：

```text
/app/cache/thumbnails
```

## 5. 验证命令

后端：

```bash
uv run ruff check backend
uv run pytest
```

前端：

```bash
cd frontend
npm run build
```

Docker 配置：

```bash
docker compose config
```

## 6. 面试演示流程

推荐演示顺序：

1. 登录系统。
2. 添加素材目录并扫描。
3. 在素材库中切换网格/列表视图。
4. 使用关键词搜索、类型筛选和标签筛选。
5. 打开素材详情，添加标签、备注、评分和收藏。
6. 点击“智能分析”，自动生成标签和描述。
7. 使用 AI 搜索：`找一个适合演唱会的大舞台`。
8. 创建项目，将人物、舞台、动作等素材加入项目。
9. 打开统计页展示素材规模和类型分布。
10. 打开重复检测页展示文件指纹检测。
11. 打开失效素材页检查磁盘文件是否仍存在。
12. 将素材移入回收站，再恢复。
13. 在设置页创建数据库备份。

## 7. 说明

当前版本使用 PostgreSQL 17 + pgvector，基于 BAAI/bge-m3 生成 1024 维素材向量，并提供混合检索和相似素材接口。首次构建语义索引会下载模型到持久化缓存。
