# AssetVault 部署说明

本文档用于说明 AssetVault 的本地开发启动、Docker Compose 启动、目录挂载和验证流程。

## 1. 本地开发启动

### 1.1 后端

```bash
uv sync
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认使用 SQLite：

```text
assetvault.db
```

默认 API 地址：

```text
http://127.0.0.1:8000
```

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

Compose 使用三个 volume：

```text
assetvault-data      SQLite 数据库
assetvault-cache     缩略图缓存
assetvault-backups   数据库备份
```

默认数据库路径：

```text
/app/data/assetvault.db
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

当前版本为了方便本地演示，默认使用 SQLite。后续可以升级为 PostgreSQL + pgvector，并将自然语言搜索替换为真实 Embedding 检索。
