# AssetVault

AssetVault is an AI Digital Asset Manager for UE5, Blender & MMD.

当前版本是按 `docs/development-plan.md` 启动的 MVP，已经包含：

- FastAPI 后端
- SQLite 开发数据库
- JWT 登录
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

## 开发账号

前端登录页默认使用：

```text
username: demo
password: assetvault
```

如果账号不存在，前端会自动注册该开发账号再登录。

## 当前能力

- 素材目录扫描：索引图片、视频、模型、动作和 UE 资产。
- 素材管理：网格/列表视图、搜索、类型筛选、标签筛选、收藏、评分、备注。
- 批量操作：素材库支持多选，批量收藏、取消收藏、打标签、加入项目和移入回收站。
- 项目管理：创建作品项目，并按人物、舞台、动作、音乐等角色引用素材。
- 统计页：展示素材总数、容量、类型分布、扩展名分布、收藏数和近 7 天新增。
- 设置系统：保存缓存目录、主题、缩略图质量、OpenAI Compatible API 配置和模型名，支持 SQLite 数据库备份。
- 智能分析：在素材详情中一键生成标签和描述，当前使用稳定的本地规则引擎，接口可扩展为 OpenAI Compatible 调用。
- 自然语言搜索：支持“找一个适合演唱会的大舞台”这类查询，当前使用本地语义解析和评分，后续可替换为 Embedding 检索。
- 重复检测：计算文件快速指纹，按指纹和大小发现重复素材，适合清理重复 PMX、PNG、视频等文件。
- 回收站：删除素材时默认只移入数据库回收站，不删除磁盘文件，支持恢复和永久删除索引。
- 失效素材检查：检测数据库索引对应的原始文件是否仍在磁盘上，发现被移动或删除的素材并集中处理。
- 缩略图：图片自动生成缩略图；如果本机安装了 FFmpeg，视频也会生成缩略图。
- 工程基础：JWT 登录、SQLite 开发数据库、FastAPI 分层结构、Next.js 前端、后端测试。

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
- AI 应用：智能分析生成标签和描述，自然语言搜索返回素材结果，而不是聊天。
- 工程设计：不移动原文件；扫描、缩略图、重复检测、失效检查都围绕索引实现。
- 数据安全：回收站只删除索引不删除磁盘文件；支持数据库备份。
- 可扩展性：当前使用 SQLite 和本地语义规则，后续可替换为 PostgreSQL、pgvector 和真实 Embedding 检索。
