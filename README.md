# AssetVault

AssetVault is an AI Digital Asset Manager for UE5, Blender & MMD.

当前版本是按 `docs/development-plan.md` 启动的 MVP，已经包含：

- FastAPI 后端
- PostgreSQL 17 + pgvector 数据库
- 默认免登录的本地工作区，可选 JWT 密码认证
- 本地素材目录扫描
- 素材索引、列表、详情、搜索
- 标签绑定
- 图片缩略图生成服务
- Next.js 前端界面

## 项目定位

AssetVault 面向 UE5、Blender、MMD 等数字内容创作者。它不会移动用户原始素材文件，而是扫描本地目录建立索引，提供搜索、标签、缩略图、项目引用、统计、重复检测、失效检查、回收站和 AI 辅助管理能力。

## Backend

```bash
uv sync
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn backend.app.main:app --reload
```

默认 API 地址：

```text
http://localhost:8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：

```text
http://localhost:3000
```

如果 3000 端口已被占用，Next.js 会自动切换到 3001 或其他可用端口。以终端输出的
`Local:` 地址为准。

## Docker Compose

```bash
copy .env.example .env
docker compose up --build
```

Docker 模式下默认将 `.env` 中的 `ASSETVAULT_ASSET_ROOT` 挂载到容器内 `/assets`。在前端添加素材目录时填写：

```text
/assets
```

详细说明见：

```text
docs/deployment.md
```

## 演示数据

面试或本地演示前，可以生成一组可扫描的素材样例：

```bash
uv run python scripts/create_demo_assets.py
```

默认生成到 `demo-assets/`，随后在前端添加该目录并执行扫描。详细说明见：

```text
docs/demo-assets.md
```

## 运行模式

默认 `ASSETVAULT_AUTH_MODE=local`，启动后直接进入本地工作区。系统会优先使用
`local` 用户；如果数据库中只有一个已有用户，则复用该用户，保证历史素材和设置可见。

需要从其他设备远程访问时，必须启用密码模式：

```text
ASSETVAULT_AUTH_MODE=password
```

密码模式下，前端登录页默认使用：

```text
username: demo
password: assetvault
```

如果账号不存在，前端会自动注册该开发账号再登录。

本地模式没有认证安全边界，只适用于受信任的单机环境。Compose 默认只监听
`127.0.0.1`。JWT 用户隔离仅约束数据库业务数据，不提供操作系统级文件权限隔离。

## 当前能力

- 素材目录扫描：索引图片、视频、模型、动作、UE 工程和专有容器，重新扫描会同步新增、恢复和缺失状态，移除目录配置不会删除原始文件。
- 格式感知解析：通过可扩展 Extractor 提取 PMX、VMD、OBJ、FBX、glTF/GLB、Blend 和 UProject 的可靠结构化元数据，并明确标记解析来源、状态和错误。
- 依赖检查：OBJ/MTL 和 glTF/GLB 会记录贴图、材质库与外部 Buffer 引用，并在详情中标出缺失依赖。
- 素材管理：网格/列表视图、分页浏览、搜索、类型筛选、标签筛选、收藏、评分、备注。
- 标签管理：集中创建、改名、设置颜色和删除标签，删除标签不会删除素材。
- 批量操作：素材库支持多选，批量收藏、取消收藏、打标签、加入项目和移入回收站。
- 项目管理：创建和编辑作品项目，并按人物、舞台、动作、音乐等角色引用素材，支持导出项目素材清单。
- 持久化任务队列：扫描和 Embedding 任务写入 PostgreSQL，由 Worker 原子领取，支持尝试次数、心跳、自动重试、取消和服务重启恢复。
- 任务中心：查看任务等待、领取、执行、重试、心跳、结果和错误信息。
- 统计页：展示素材总数、容量、类型分布、扩展名分布、收藏数和近 7 天新增。
- 设置系统：保存缓存目录、主题、缩略图质量和 OpenAI Compatible 分析配置，支持 PostgreSQL 自定义格式备份。
- 智能分析：生成带来源信息的标签和描述建议，用户确认后才写入；远端调用失败不会静默伪装成本地 AI 结果。
- 检索分层：格式内对象名、材质名、骨骼名、插件名和依赖名参与关键词检索；只有人工描述、正式标签、作者信息或可靠语义描述才生成 `BAAI/bge-m3` 向量。
- 重复检测：计算文件快速指纹，按指纹和大小发现重复素材，适合清理重复 PMX、PNG、视频等文件。
- 回收站：删除素材时默认只移入数据库回收站，不删除磁盘文件，支持恢复和永久删除索引。
- 失效素材检查：检测数据库索引对应的原始文件是否仍在磁盘上，发现被移动或删除的素材并集中处理。
- 缩略图：图片自动生成缩略图；如果本机安装了 FFmpeg，视频也会生成缩略图。
- 工程基础：本地免登录/JWT 密码认证双模式、PostgreSQL + pgvector、Alembic、数据库任务队列、FastAPI 分层结构、Next.js 前端和后端测试。

## 验证命令

```bash
uv run ruff check backend
uv run pytest
cd frontend
npm run build
```

Docker 配置校验：

```bash
docker compose config
```

## 面试展示重点

- 产品闭环：扫描素材、建立索引、浏览搜索、标签收藏、详情维护、项目引用。
- AI 应用：智能分析可调用 OpenAI Compatible API 生成标签和描述，自然语言搜索返回素材结果，而不是聊天。
- 工程设计：不移动原文件；扫描、缩略图、重复检测、失效检查都围绕索引实现。
- 数据安全：回收站只删除索引不删除磁盘文件；支持数据库备份。
- 检索能力：BGE-M3 与 pgvector 已落地；后续可增加离线 Recall@10 评测集和向量索引参数调优。
