# AssetVault

AssetVault is an AI Digital Asset Manager for UE5, Blender & MMD.

当前版本是按 `docs/development-plan.md` 启动的 MVP 骨架，已经包含：

- FastAPI 后端
- SQLite 开发数据库
- JWT 登录
- 本地素材目录扫描
- 素材索引、列表、详情、搜索
- 标签绑定
- 图片缩略图生成服务
- Next.js 前端基础界面

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

## 开发账号

前端登录页默认使用：

```text
username: demo
password: assetvault
```

如果账号不存在，前端会自动注册该开发账号再登录。
