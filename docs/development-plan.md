# AssetVault 开发计划

## 1. 项目定位

**AssetVault** 是一个面向数字内容创作者的本地 AI 素材管理平台，主要服务于 UE5、Blender、MMD 等创作工作流。

它不会移动用户原有素材文件，而是通过扫描本地目录建立数据库索引，提供高速搜索、标签管理、缩略图预览、智能分类、AI 自动标签和自然语言检索能力，帮助创作者管理海量数字资产。

一句话介绍：

> AssetVault is an AI Digital Asset Manager for UE5, Blender & MMD.

项目目标不是复刻 Eagle、Billfish、PureRef 的全部能力，而是在 3 到 5 周内完成一个可每天使用的 MVP，再用 1 到 2 周进行体验打磨和工程补强。

## 2. 项目价值

AssetVault 适合作为秋招项目，因为它能同时体现以下能力：

- 企业级全栈开发：登录、权限、数据库建模、任务队列、缓存、文件扫描、部署。
- 真实产品能力：素材导入、浏览、搜索、标签、详情、缩略图、设置等完整闭环。
- AI 应用落地：AI 自动标签、自动描述、Embedding 自然语言搜索、相似素材推荐。
- 工程设计能力：不移动用户文件，只做索引；扫描任务异步化；缩略图缓存；可扩展的资产类型体系。
- 与 PitWallAgent 形成差异：PitWallAgent 偏 Agent/RAG/LangGraph，AssetVault 偏企业级全栈与 AI 产品。

## 3. MVP 范围控制

第一版只做 8 个核心模块：

1. 用户系统
2. 素材库
3. 文件浏览
4. 标签系统
5. 搜索
6. 文件详情
7. 缩略图
8. 设置

暂不在 MVP 中实现：

- 完整的 3D 模型实时预览
- 复杂的素材编辑器
- 云同步
- 团队协作
- 权限系统细分
- 全量 Eagle/Billfish/PureRef 功能
- 大规模分布式检索

## 4. 技术栈

### 4.1 前端

- Next.js
- TypeScript
- TailwindCSS
- shadcn/ui
- TanStack Query
- Zustand 或 Jotai：用于轻量前端状态
- React Hook Form + Zod：用于表单和校验

### 4.2 后端

- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery
- Pydantic v2
- python-jose 或 PyJWT
- Passlib / bcrypt

### 4.3 AI

- OpenAI Compatible API
- Embedding
- pgvector 或 SQLite Vector
- CLIP，可作为第二阶段增强能力

### 4.4 本地工具

- FFmpeg：视频缩略图
- Pillow：图片缩略图
- OpenCV：视频帧处理，可选
- Watchdog：文件监听
- python-magic 或 mimetypes：文件类型识别

### 4.5 部署

- Docker
- Docker Compose
- Nginx，可选
- 本地开发优先支持 Windows

## 5. 推荐目录结构

```text
AssetVault/
  backend/
    app/
      api/
        v1/
          auth.py
          users.py
          assets.py
          folders.py
          tags.py
          search.py
          settings.py
          tasks.py
          ai.py
      core/
        config.py
        security.py
        logging.py
      db/
        session.py
        base.py
      models/
        user.py
        asset.py
        folder.py
        tag.py
        project.py
        setting.py
        task.py
      schemas/
        auth.py
        user.py
        asset.py
        tag.py
        search.py
        setting.py
      services/
        asset_scanner.py
        thumbnail_service.py
        search_service.py
        ai_tag_service.py
        embedding_service.py
        file_type_service.py
      workers/
        celery_app.py
        tasks.py
      main.py
    alembic/
    tests/
    pyproject.toml

  frontend/
    app/
      login/
      library/
      settings/
      projects/
    components/
      asset/
      layout/
      search/
      tag/
      ui/
    lib/
      api.ts
      auth.ts
      query.ts
      types.ts
    store/
    package.json

  docs/
    development-plan.md
    api-design.md
    database-design.md
    deployment.md

  docker-compose.yml
  README.md
```

## 6. 核心业务流程

### 6.1 素材扫描流程

```text
用户添加素材目录
  -> 后端保存 folders 记录
  -> 创建扫描任务 tasks
  -> Celery 执行目录递归扫描
  -> 识别支持的文件类型
  -> 读取文件元数据
  -> assets 表 upsert
  -> 图片/视频生成缩略图
  -> 写入任务进度
  -> 前端轮询或订阅任务状态
```

设计原则：

- 不移动用户文件。
- 数据库只保存文件索引和业务元数据。
- 同一路径重复扫描时做 upsert。
- 文件路径、大小、修改时间、hash 可用于判断是否需要重新处理。
- 扫描任务必须异步执行，避免阻塞 API。

### 6.2 素材浏览流程

```text
前端进入素材库
  -> 请求 /assets
  -> 携带分页、排序、过滤参数
  -> 后端返回素材列表
  -> 前端展示网格或列表
  -> 用户点击素材
  -> 请求 /assets/{id}
  -> 展示详情面板
```

### 6.3 标签流程

```text
用户选择一个或多个素材
  -> 添加标签
  -> 如果标签不存在则创建
  -> 写入 asset_tags
  -> 更新素材列表和详情
```

### 6.4 AI 自动标签流程

```text
用户选择素材或扫描任务触发
  -> 创建 AI 分析任务
  -> 读取缩略图或文件基础信息
  -> 调用 OpenAI Compatible API
  -> 返回标签、分类、描述
  -> 写入 tags、asset_tags、assets.description
  -> 保存 AI 任务结果
```

### 6.5 自然语言搜索流程

```text
用户输入自然语言
  -> 后端生成 query embedding
  -> 向量检索 assets embedding
  -> 结合关键词搜索结果
  -> 返回混合排序结果
```

MVP 可以先做关键词搜索，第二阶段再加入 Embedding。

## 7. 数据库设计

控制在 10 张表以内：

```text
users
assets
folders
tags
asset_tags
favorites
projects
project_assets
settings
tasks
```

### 7.1 users

保存用户账号和基础信息。

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| username | varchar | 用户名，唯一 |
| email | varchar | 邮箱，唯一，可选 |
| password_hash | varchar | 密码哈希 |
| display_name | varchar | 展示名称 |
| avatar_url | varchar | 头像，可选 |
| is_active | boolean | 是否启用 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

### 7.2 folders

保存用户添加的素材目录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 所属用户 |
| name | varchar | 目录名称 |
| path | text | 本地绝对路径 |
| is_active | boolean | 是否启用扫描 |
| last_scanned_at | timestamp | 上次扫描时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

### 7.3 assets

保存素材索引。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 所属用户 |
| folder_id | uuid | 所属素材目录 |
| name | varchar | 文件名 |
| stem | varchar | 不含扩展名的文件名 |
| extension | varchar | 扩展名 |
| asset_type | varchar | image/video/model/motion/audio/other |
| path | text | 本地绝对路径 |
| size_bytes | bigint | 文件大小 |
| mime_type | varchar | MIME 类型 |
| file_hash | varchar | 文件 hash，可延后实现 |
| thumbnail_path | text | 缩略图缓存路径 |
| description | text | 描述，可由 AI 生成 |
| author | varchar | 作者，可手动填写 |
| rating | integer | 星级，0 到 5 |
| is_favorite | boolean | 是否收藏 |
| last_opened_at | timestamp | 最近打开时间 |
| file_created_at | timestamp | 文件创建时间 |
| file_modified_at | timestamp | 文件修改时间 |
| indexed_at | timestamp | 入库时间 |
| created_at | timestamp | 记录创建时间 |
| updated_at | timestamp | 记录更新时间 |

建议索引：

- `user_id`
- `folder_id`
- `asset_type`
- `extension`
- `name`
- `path`
- `file_modified_at`
- `last_opened_at`

### 7.4 tags

保存标签。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 所属用户 |
| name | varchar | 标签名 |
| color | varchar | 标签颜色 |
| source | varchar | manual/ai/system |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

约束：

- 同一用户下 `name` 唯一。

### 7.5 asset_tags

素材和标签的多对多关系。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| asset_id | uuid | 素材 ID |
| tag_id | uuid | 标签 ID |
| created_at | timestamp | 创建时间 |

约束：

- `(asset_id, tag_id)` 唯一。

### 7.6 favorites

如果 `assets.is_favorite` 已满足 MVP，可以第二阶段再独立此表。若保留该表，可用于支持收藏夹。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 用户 ID |
| asset_id | uuid | 素材 ID |
| created_at | timestamp | 收藏时间 |

### 7.7 projects

保存项目集合，例如一个 MMD/UE5/Blender 作品。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 所属用户 |
| name | varchar | 项目名称 |
| description | text | 项目说明 |
| cover_asset_id | uuid | 封面素材 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

### 7.8 project_assets

项目和素材的多对多关系。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| project_id | uuid | 项目 ID |
| asset_id | uuid | 素材 ID |
| role | varchar | character/stage/motion/music/texture/other |
| created_at | timestamp | 创建时间 |

### 7.9 settings

用户设置。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 用户 ID |
| key | varchar | 设置键 |
| value | jsonb | 设置值 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

示例 key：

- `cache_dir`
- `theme`
- `ai_provider`
- `ai_base_url`
- `ai_model`
- `embedding_model`
- `thumbnail_quality`

敏感信息如 AI Key 不建议明文保存。开发阶段可以先存在本地环境变量，正式版本再做加密存储。

### 7.10 tasks

保存扫描、缩略图、AI 分析等异步任务。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| user_id | uuid | 用户 ID |
| type | varchar | scan/thumbnail/ai_tag/embedding |
| status | varchar | pending/running/success/failed/canceled |
| progress | integer | 0 到 100 |
| total | integer | 总数量 |
| processed | integer | 已处理数量 |
| message | text | 当前状态说明 |
| error | text | 错误信息 |
| payload | jsonb | 任务参数 |
| result | jsonb | 任务结果 |
| created_at | timestamp | 创建时间 |
| started_at | timestamp | 开始时间 |
| finished_at | timestamp | 结束时间 |

## 8. 支持的素材类型

### 8.1 MVP 支持

| 类型 | 扩展名 | 处理方式 |
| --- | --- | --- |
| 图片 | jpg/jpeg/png/webp/gif/bmp/tiff | 读取元数据，生成缩略图 |
| 视频 | mp4/mov/mkv/avi/webm | FFmpeg 截帧生成缩略图 |
| MMD 模型 | pmx/pmd | 先记录索引，第二阶段预览 |
| MMD 动作 | vmd/vpd | 先记录索引 |
| 3D 模型 | fbx/obj/glb/gltf | 先记录索引 |
| Blender | blend | 先记录索引 |
| UE 资产 | uasset | 仅记录索引 |

### 8.2 类型归类

```text
image: jpg, jpeg, png, webp, gif, bmp, tiff
video: mp4, mov, mkv, avi, webm
model: pmx, pmd, fbx, obj, glb, gltf, blend
motion: vmd, vpd
ue: uasset
other: 其他可配置类型
```

## 9. 后端 API 设计

### 9.1 Auth

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

### 9.2 Users

```http
GET   /api/v1/users/me
PATCH /api/v1/users/me
PATCH /api/v1/users/me/password
```

### 9.3 Folders

```http
GET    /api/v1/folders
POST   /api/v1/folders
GET    /api/v1/folders/{folder_id}
PATCH  /api/v1/folders/{folder_id}
DELETE /api/v1/folders/{folder_id}
POST   /api/v1/folders/{folder_id}/scan
```

### 9.4 Assets

```http
GET    /api/v1/assets
GET    /api/v1/assets/{asset_id}
PATCH  /api/v1/assets/{asset_id}
DELETE /api/v1/assets/{asset_id}
POST   /api/v1/assets/batch-import
POST   /api/v1/assets/{asset_id}/open
POST   /api/v1/assets/{asset_id}/favorite
DELETE /api/v1/assets/{asset_id}/favorite
POST   /api/v1/assets/{asset_id}/thumbnail
```

`GET /assets` 查询参数：

| 参数 | 说明 |
| --- | --- |
| page | 页码 |
| page_size | 每页数量 |
| q | 关键词 |
| type | 素材类型 |
| tag_ids | 标签 ID 列表 |
| favorite | 是否收藏 |
| sort_by | name/size/file_modified_at/asset_type/last_opened_at |
| sort_order | asc/desc |

### 9.5 Tags

```http
GET    /api/v1/tags
POST   /api/v1/tags
PATCH  /api/v1/tags/{tag_id}
DELETE /api/v1/tags/{tag_id}
POST   /api/v1/assets/{asset_id}/tags
DELETE /api/v1/assets/{asset_id}/tags/{tag_id}
POST   /api/v1/assets/batch-tags
```

### 9.6 Search

```http
GET  /api/v1/search
POST /api/v1/search/natural-language
```

第一阶段：

- `GET /search` 做关键词搜索。

第二阶段：

- `POST /search/natural-language` 做 Embedding 搜索。

### 9.7 AI

```http
POST /api/v1/ai/assets/{asset_id}/tag
POST /api/v1/ai/assets/{asset_id}/describe
POST /api/v1/ai/assets/{asset_id}/embed
POST /api/v1/ai/assets/batch-tag
GET  /api/v1/ai/tasks/{task_id}
```

### 9.8 Settings

```http
GET   /api/v1/settings
PATCH /api/v1/settings
POST  /api/v1/settings/test-ai
POST  /api/v1/settings/backup-database
```

### 9.9 Tasks

```http
GET  /api/v1/tasks
GET  /api/v1/tasks/{task_id}
POST /api/v1/tasks/{task_id}/cancel
```

## 10. 前端页面设计

### 10.1 登录页

功能：

- 用户名/邮箱登录
- 密码登录
- 登录态保存
- 登录失败提示

MVP 可默认创建一个本地用户，但仍保留完整登录结构。

### 10.2 主布局

建议结构：

```text
左侧导航
  - 素材库
  - 收藏
  - 最近打开
  - 项目
  - 任务
  - 设置

顶部工具栏
  - 搜索框
  - 导入按钮
  - 视图切换
  - 排序
  - 用户菜单

主内容区
  - 网格/列表

右侧详情栏
  - 选中素材详情
```

### 10.3 素材库页面

核心控件：

- 拖拽导入区域
- 网格/列表切换
- 类型过滤
- 标签过滤
- 排序
- 批量选择
- 批量打标签
- 批量 AI 分析，第二阶段

网格卡片展示：

- 缩略图
- 文件名
- 类型角标
- 收藏状态
- 标签简略展示

列表展示：

- 文件名
- 类型
- 大小
- 修改时间
- 路径
- 标签

### 10.4 详情面板

展示字段：

- 预览图
- 文件名
- 文件大小
- 格式
- 路径
- 创建时间
- 修改时间
- 标签
- 备注
- 作者
- 星级
- 收藏
- 最近打开时间

操作：

- 打开文件
- 打开所在目录
- 添加标签
- 编辑备注
- 收藏
- 重新生成缩略图
- AI 自动标签，第二阶段
- AI 自动描述，第二阶段

### 10.5 设置页

模块：

- 素材目录
- 缓存目录
- AI 设置
- 主题
- 数据库备份
- 缩略图设置

AI 设置包括：

- API Base URL
- API Key
- Chat Model
- Embedding Model
- 连接测试

API Key 前端只负责输入，不应在日志中输出。

## 11. 搜索设计

### 11.1 第一阶段关键词搜索

搜索范围：

- 文件名
- 标签
- 作者
- 文件类型
- 路径
- 备注

实现建议：

- PostgreSQL `ILIKE` 可以先满足 MVP。
- 对 `name`、`path`、`extension`、`asset_type`、`author` 建索引。
- 标签搜索通过 join `asset_tags` 和 `tags`。
- 后续可升级 PostgreSQL Full Text Search。

### 11.2 第二阶段自然语言搜索

需要增加字段或扩展表：

方案 A：在 `assets` 表增加 `embedding vector` 字段。

方案 B：新增 `asset_embeddings` 表。

MVP 推荐方案 B，避免污染主表：

```text
asset_embeddings
  id
  asset_id
  provider
  model
  content
  embedding
  created_at
```

检索逻辑：

```text
query -> embedding -> vector search -> top_k assets -> 合并关键词结果 -> 返回
```

排序建议：

- 向量相似度
- 收藏权重
- 最近打开权重
- 文件修改时间权重

## 12. 缩略图设计

### 12.1 缩略图缓存目录

建议结构：

```text
cache/
  thumbnails/
    images/
      {asset_id}.webp
    videos/
      {asset_id}.webp
    models/
      {asset_id}.webp
```

### 12.2 图片缩略图

流程：

```text
读取图片
  -> 修正 EXIF 方向
  -> 等比缩放
  -> 转 webp
  -> 保存到缓存目录
  -> 写入 assets.thumbnail_path
```

### 12.3 视频缩略图

流程：

```text
ffmpeg 读取视频
  -> 截取第 1 秒或 10% 位置帧
  -> 转 webp
  -> 保存到缓存目录
  -> 写入 assets.thumbnail_path
```

### 12.4 失败处理

缩略图生成失败不能影响素材入库。

失败时：

- `assets.thumbnail_path` 为空。
- `tasks.error` 记录错误。
- 前端显示类型占位图。

## 13. AI 功能设计

第二阶段开始实现 AI，所有 AI 能力都围绕素材管理，不做泛聊天。

### 13.1 AI 自动标签

输入：

- 图片缩略图
- 视频关键帧
- 文件名
- 路径
- 已有标签

输出：

```json
{
  "tags": ["少女", "动漫", "蓝发", "双马尾", "JK", "校园"],
  "category": "人物",
  "confidence": 0.86
}
```

规则：

- 每个素材建议生成 5 到 10 个标签。
- 标签需要去重。
- 标签过长要过滤。
- 低置信度标签可以不自动写入，放入待确认队列，后续可实现。

### 13.2 AI 自动描述

输出示例：

```text
这是一个白色演出舞台，适合大型演唱会使用，包含 LED 背景和多层灯光结构。
```

要求：

- 描述要短，控制在 100 字以内。
- 避免编造版权、作者、来源。
- 如果信息不足，只描述可见内容。

### 13.3 AI 自然语言搜索

用户输入：

```text
找一个适合演唱会的大舞台
```

系统返回：

- 舞台图片
- 舞台模型
- HDR 演唱会背景
- 相关视频素材

关键点：

- 它是搜索，不是聊天。
- 返回结果必须是素材列表。
- 前端可以展示“AI 搜索”标签，但交互仍然是搜索结果页。

### 13.4 AI 相似素材推荐

打开素材 `Stage_A` 后：

```text
推荐 Stage_B、Stage_C、HDR_Concert
```

依据：

- 标签相似
- 类型相似
- 描述 embedding 相似
- 路径相似
- 文件名相似

### 13.5 AI 智能分类

自动分类：

```text
人物
动作
舞台
音乐
贴图
HDR
视频
模型
其他
```

分类建议写入 `assets.asset_type` 或单独的系统标签。

MVP 推荐：

- `asset_type` 保存技术类型：image/video/model/motion。
- 系统标签保存语义类型：人物/动作/舞台/音乐。

## 14. 第三阶段高级功能

### 14.1 项目管理

用途：

```text
一个作品项目
  -> 引用人物
  -> 引用动作
  -> 引用舞台
  -> 引用音乐
```

价值：

- 以后能知道某个作品用了哪些素材。
- 适合展示产品闭环。

### 14.2 重复检测

实现方式：

- 小文件直接计算 hash。
- 大文件分块 hash。
- 图片可选感知 hash。
- 视频可选关键帧 hash。

第一版只做完全重复检测，不做相似重复。

### 14.3 文件监听

使用 Watchdog：

```text
新增文件 -> 自动入库
修改文件 -> 更新元数据
删除文件 -> 标记 missing
```

建议给 `assets` 增加：

```text
exists_on_disk boolean
missing_since timestamp
```

不要直接删除数据库记录，避免误删。

### 14.4 回收站

删除逻辑：

- 不删除本地文件。
- 只把数据库记录标记为 deleted。
- 支持恢复。

建议给 `assets` 增加：

```text
is_deleted boolean
deleted_at timestamp
```

### 14.5 统计页面

展示：

```text
总素材数
总容量
图片数量
视频数量
模型数量
动作数量
标签数量
收藏数量
最近 7 天新增
最大素材目录
```

## 15. 开发排期

### 第 1 周：后端基础和素材扫描

目标：

- 项目骨架搭建
- 数据库迁移
- 登录和 JWT
- 素材目录管理
- 目录扫描入库

任务：

- 初始化 FastAPI 项目。
- 配置 SQLAlchemy、Alembic、PostgreSQL。
- 创建 users、folders、assets、tasks 表。
- 实现注册、登录、当前用户接口。
- 实现素材目录新增、列表、删除。
- 实现目录扫描服务。
- 实现 Celery 和 Redis。
- 扫描任务写入 tasks 进度。

验收标准：

- 用户可以登录。
- 用户可以添加一个本地素材目录。
- 后端能扫描该目录下支持的素材文件。
- 扫描结果能写入数据库。
- 前端或 API 能看到扫描任务状态。

### 第 2 周：素材浏览、详情、标签、搜索、缩略图

目标：

- 做成一个可用的本地素材库。

任务：

- 初始化 Next.js 前端。
- 实现登录页和主布局。
- 实现素材网格视图。
- 实现素材列表视图。
- 实现素材详情面板。
- 实现标签增删改查。
- 实现素材打标签。
- 实现收藏、星级、最近打开。
- 实现关键词搜索。
- 实现图片缩略图。
- 实现视频缩略图。

验收标准：

- 可以浏览扫描出的素材。
- 可以按名称、时间、大小、类型排序。
- 可以按类型和标签过滤。
- 可以给素材添加多个标签。
- 可以收藏素材。
- 可以查看素材详情。
- 图片和视频能显示缩略图。
- 搜索速度明显优于手动翻文件夹。

### 第 3 周：AI 自动标签、AI 描述、自然语言搜索

目标：

- 让 AssetVault 具备 AI 应用亮点。

任务：

- 实现 AI Provider 配置。
- 实现 AI 连接测试。
- 实现单素材 AI 自动标签。
- 实现批量 AI 自动标签任务。
- 实现 AI 自动描述。
- 实现 embedding 生成。
- 接入 pgvector 或 SQLite Vector。
- 实现自然语言搜索。

验收标准：

- 对图片素材可以生成合理标签。
- 对素材可以生成简短描述。
- 用户输入自然语言后能返回相关素材。
- AI 功能失败时不影响基础素材管理。

### 第 4 周：文件监听、项目管理、统计、部署、README

目标：

- 补齐产品完整度和工程展示材料。

任务：

- 实现 Watchdog 文件监听。
- 实现项目 Project 功能。
- 实现 project_assets 引用。
- 实现统计页面。
- 编写 Docker Compose。
- 编写 README。
- 编写接口文档。
- 准备项目截图和演示流程。

验收标准：

- 新增文件能自动入库，或至少支持手动刷新。
- 可以创建项目并关联素材。
- 统计页能展示素材规模。
- 项目可以一键启动。
- README 能让面试官理解项目价值和技术亮点。

### 第 5 到 6 周：打磨

目标：

- 修复体验问题。
- 补测试。
- 做展示材料。

任务：

- 优化大目录扫描性能。
- 优化缩略图加载。
- 完善空状态、加载态、错误态。
- 增加后端单元测试。
- 增加关键接口集成测试。
- 优化 UI 细节。
- 补充演示数据。
- 准备面试讲解稿。

验收标准：

- 可以稳定管理至少 1 万个素材索引。
- 常用操作不卡顿。
- 核心接口有测试覆盖。
- 项目展示路径清晰。

## 16. 里程碑

### Milestone 1：可扫描

交付内容：

- 用户登录
- 添加素材目录
- 扫描素材
- 数据库存储索引

### Milestone 2：可管理

交付内容：

- 素材浏览
- 详情
- 标签
- 收藏
- 搜索
- 缩略图

### Milestone 3：可智能检索

交付内容：

- AI 自动标签
- AI 自动描述
- 自然语言搜索

### Milestone 4：可展示

交付内容：

- 项目管理
- 统计页
- Docker 部署
- README
- 截图和演示数据

## 17. 测试策略

### 17.1 后端测试

重点覆盖：

- 用户注册登录
- JWT 鉴权
- 素材扫描
- 文件类型识别
- 标签增删改查
- 搜索接口
- 缩略图生成
- AI 结果解析

建议使用：

- pytest
- pytest-asyncio
- httpx AsyncClient
- 临时测试数据库

### 17.2 前端测试

MVP 可以先不做大规模前端自动化测试，但至少保证：

- 登录流程可用
- 素材列表可加载
- 过滤和排序可用
- 详情面板可打开
- 标签操作可用

后续可加入：

- Playwright
- React Testing Library

### 17.3 手动验收数据集

准备一个本地测试目录：

```text
demo-assets/
  images/
  videos/
  models/
  motions/
  ue/
```

每类放 5 到 20 个样例文件，方便演示和回归。

## 18. 性能目标

MVP 目标：

- 1 万条素材索引可正常浏览。
- 普通关键词搜索在 300ms 到 800ms 内返回。
- 分页接口默认每页 50 到 100 条。
- 缩略图异步生成，不阻塞扫描。
- 大目录扫描可以显示进度。

优化方向：

- 数据库索引。
- 分页查询。
- 缩略图懒加载。
- 缓存常用标签。
- 扫描任务分批提交。
- 避免一次性把全部素材加载到前端。

## 19. 安全与边界

### 19.1 本地路径安全

- 后端要校验路径是否存在。
- 不允许通过 API 任意读取文件内容。
- 打开文件和打开目录应只针对已索引素材。
- 删除操作默认只删除数据库记录，不删除磁盘文件。

### 19.2 AI Key 安全

- 不在日志中打印 AI Key。
- 不把 AI Key 返回给前端。
- 开发阶段优先使用环境变量。
- 如果写入数据库，需要加密存储。

### 19.3 文件处理安全

- 缩略图生成失败要捕获异常。
- 不信任文件扩展名，尽量结合 MIME 或文件头判断。
- 对超大文件设置处理限制。
- FFmpeg 调用需要设置超时。

## 20. 面试展示重点

可以从以下角度讲项目：

### 20.1 产品设计

- 为什么不移动用户文件，只做索引。
- 为什么 AI 功能围绕素材管理，而不是做聊天机器人。
- 如何控制 MVP 范围。

### 20.2 后端工程

- FastAPI 分层设计。
- SQLAlchemy 数据建模。
- Celery 异步扫描和缩略图任务。
- PostgreSQL 索引优化。
- JWT 鉴权。

### 20.3 AI 应用

- AI 自动标签如何落库。
- 自然语言搜索如何用 Embedding 实现。
- 如何处理 AI 失败、限流、成本和结果质量。

### 20.4 前端体验

- 网格和列表两种视图。
- 详情面板。
- 搜索、过滤、排序。
- 批量操作。

### 20.5 工程权衡

- 为什么 PMX/FBX/GLB 第一阶段只索引不预览。
- 为什么缩略图异步生成。
- 为什么先关键词搜索，再向量搜索。
- 为什么项目表和回收站放到后续阶段。

## 21. README 建议结构

```markdown
# AssetVault

AI Digital Asset Manager for UE5, Blender & MMD.

## Features

## Tech Stack

## Architecture

## Screenshots

## Quick Start

## API Overview

## Database Design

## AI Workflow

## Roadmap

## Interview Highlights
```

## 22. 第一版优先级

必须完成：

- 登录
- 添加素材目录
- 扫描素材
- 素材浏览
- 素材详情
- 标签
- 收藏
- 搜索
- 图片/视频缩略图
- 设置页基础项

尽量完成：

- AI 自动标签
- AI 自动描述
- 自然语言搜索
- Docker Compose
- 统计页

可以延期：

- 3D 模型实时预览
- 重复检测
- 文件监听
- 回收站
- 项目管理高级能力
- 团队协作
- 云同步

## 23. MVP 完成定义

当满足以下条件时，AssetVault MVP 可以认为完成：

- 用户可以登录系统。
- 用户可以添加一个或多个本地素材目录。
- 系统可以扫描并索引图片、视频、模型、动作、UE 资产等文件。
- 用户可以用网格和列表两种方式浏览素材。
- 用户可以搜索、排序、过滤素材。
- 用户可以给素材添加标签、收藏、星级和备注。
- 用户可以查看素材详情。
- 图片和视频有缩略图。
- 基础设置可用。
- AI 至少完成自动标签或自然语言搜索中的一个。
- 项目有 README、启动方式、数据库说明和演示截图。

## 24. 建议开发顺序

实际编码时建议按以下顺序推进：

1. 后端项目骨架
2. 数据库模型和迁移
3. 登录和 JWT
4. 素材目录管理
5. 目录扫描
6. 素材列表 API
7. 前端登录和主布局
8. 素材网格/列表
9. 素材详情
10. 标签系统
11. 搜索和过滤
12. 缩略图
13. 设置页
14. AI 自动标签
15. AI 描述
16. 自然语言搜索
17. 项目管理和统计
18. Docker、README、演示数据

## 25. 风险控制

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| 功能范围过大 | 项目做不完 | 严格按 MVP 开发，第三阶段功能可延期 |
| 3D 文件预览复杂 | 进度失控 | 第一阶段只索引，不做实时预览 |
| AI 结果不稳定 | 体验下降 | AI 结果可编辑，低置信度不自动写入 |
| 大目录扫描慢 | 用户体验差 | 异步任务、进度展示、增量扫描 |
| 缩略图生成失败 | 浏览体验差 | 失败降级为类型占位图 |
| Windows 路径问题 | 文件无法打开 | 统一使用 pathlib，保存绝对路径 |
| API Key 泄露 | 安全问题 | 不打印、不返回、环境变量优先 |

## 26. 最小演示脚本

面试或展示时可以按这个流程演示：

1. 登录 AssetVault。
2. 添加一个素材目录。
3. 启动扫描任务。
4. 展示扫描进度。
5. 进入素材库，切换网格和列表视图。
6. 按类型过滤图片、视频、模型。
7. 搜索 `stage` 或 `girl`。
8. 打开一个素材详情。
9. 添加标签和收藏。
10. 生成 AI 标签或 AI 描述。
11. 使用自然语言搜索：`找一个适合演唱会的大舞台`。
12. 展示统计页或项目引用关系。

## 27. 总结

AssetVault 的关键不是功能数量，而是形成一个真实产品闭环：

```text
扫描本地素材
  -> 建立索引
  -> 浏览和搜索
  -> 标签和收藏
  -> 缩略图预览
  -> AI 自动理解素材
  -> 自然语言检索
```

只要这个闭环稳定，项目就已经具备很强的展示价值。后续的项目管理、重复检测、文件监听、回收站和 3D 预览都可以作为可扩展能力逐步加入。
