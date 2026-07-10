# AssetVault API 设计说明

本文档用于说明 AssetVault 后端 API 的领域划分、鉴权方式、核心接口和典型业务流程。它不是 OpenAPI 自动导出的字段全集，而是面向开发和面试讲解的设计文档。

## 1. API 总体原则

AssetVault 后端采用 FastAPI 提供 REST API，统一前缀为：

```text
/api/v1
```

设计原则：

- 按业务领域拆分路由，而不是按前端页面拆分。
- 所有用户数据都通过 JWT 绑定当前用户，避免跨用户访问。
- 文件本体不上传、不移动、不删除，API 只维护数据库索引和元数据。
- 扫描、检测、备份、AI 分析等能力都围绕素材管理闭环展开。
- 当前使用 SQLite 便于本地演示，接口边界保持为以后迁移 PostgreSQL、Celery、pgvector 留空间。

## 2. 鉴权方式

登录成功后，后端返回 JWT：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

前端后续请求统一携带：

```http
Authorization: Bearer <token>
```

需要鉴权的接口会通过 `get_current_user` 解析 token，并把查询限制在当前用户的 `user_id` 下。

## 3. 用户与登录

### 注册

```http
POST /api/v1/auth/register
```

用途：

- 创建用户账号。
- 当前演示环境支持 `demo / assetvault` 开发账号。

### 登录

```http
POST /api/v1/auth/login
```

用途：

- 校验用户名和密码。
- 返回 JWT。

### 当前用户

```http
GET /api/v1/auth/me
```

用途：

- 获取当前登录用户信息。
- 前端可用于判断 token 是否有效。

### 退出登录

当前版本的 JWT 是无状态 token，退出登录由前端清理本地 token 完成：

```text
localStorage.removeItem("assetvault_token")
```

说明：

- 退出后前端会跳转到登录页。
- 后续如果需要服务端强制失效 token，可以增加 token blacklist 或 refresh token 机制。

### 更新用户资料

```http
PATCH /api/v1/users/me
```

字段：

```json
{
  "display_name": "AssetVault Demo",
  "email": "demo@example.com"
}
```

说明：

- 用户名不可直接修改，避免影响登录标识。
- 邮箱需要保持唯一。
- 邮箱可以为空，适合本地单机演示场景。

### 修改密码

```http
PATCH /api/v1/users/me/password
```

字段：

```json
{
  "current_password": "old-password",
  "new_password": "new-password"
}
```

说明：

- 必须校验当前密码。
- 新密码会重新哈希后保存。
- 修改成功返回 `204 No Content`。

## 4. 素材目录

### 获取目录列表

```http
GET /api/v1/folders
```

用途：

- 查看当前用户配置的素材目录。

### 添加目录

```http
POST /api/v1/folders
```

关键字段：

```json
{
  "path": "E:/Assets/MMD",
  "name": "MMD 素材"
}
```

设计说明：

- 后端会校验目录是否存在。
- 系统只记录目录路径，不复制目录中的文件。

### 扫描目录

```http
POST /api/v1/folders/{folder_id}/scan
```

用途：

- 创建扫描任务。
- 后端扫描目录，识别支持的文件类型，写入 `assets` 表。
- 图片会生成缩略图，视频在安装 FFmpeg 时生成缩略图。
- 重新扫描会同步该目录的索引状态：导入新增文件、更新已有文件、恢复重新出现的文件，并标记该目录下已经消失的文件。

返回：

```json
{
  "id": "...",
  "type": "scan",
  "status": "pending",
  "progress": 0
}
```

扫描任务完成后，`result` 会记录：

- `imported`：新增导入数量。
- `updated`：已存在素材更新数量。
- `restored`：原本标记缺失、重新扫描后恢复存在的数量。
- `missing_marked`：本次扫描发现已经从目录中消失的数量。
- `total`：本次扫描到的支持文件数量。

### 删除目录

```http
DELETE /api/v1/folders/{folder_id}
```

说明：

- 删除的是目录配置，不删除磁盘文件。
- 已经建立的素材索引会保留，`folder_id` 会置空。
- 如果后续需要重新同步该目录，需要重新添加目录后再扫描。

## 5. 素材库

### 素材列表

```http
GET /api/v1/assets
```

常用查询参数：

```text
page=1
page_size=60
q=stage
scope=primary
directory_path=E:/Assets/MMD/miku
type=model
tag_id=<tag_id>
favorite=true
exists_on_disk=true
sort_by=file_modified_at
sort_order=desc
```

支持排序字段：

- `name`
- `size_bytes`
- `file_modified_at`
- `asset_type`
- `last_opened_at`

展示范围：

- `scope=primary`：默认值，只展示模型、动作、UE 资产，适合作为素材库首页，避免一个工程里的贴图和辅助文件一股脑铺满列表。
- `scope=support`：只展示图片、视频等贴图/辅助文件，适合专门整理贴图、参考图和视频素材。
- `scope=all`：展示全部索引，适合审计、清理和批量维护。
- 如果同时传入 `type=image` 这类具体类型筛选，具体类型优先。

工程目录：

- `GET /api/v1/assets/folder-groups` 会按扫描根目录下的一级子目录生成工程/素材包分组。
- `directory_path=<path>` 用于只查看某个工程目录下的素材，包含该目录的所有子目录。
- 例如 `miku/miku.pmx` 和 `miku/textures/body.png` 会归到同一个 `miku` 工程目录中。

设计说明：

- 查询数据库索引，不实时遍历磁盘。
- 默认过滤回收站素材。
- 搜索范围包含名称、路径、扩展名、作者、描述，以及格式提取器返回的对象名、材质名、骨骼名、插件名和依赖文件名。
- 系统仍然完整索引所有支持文件，但素材库浏览先按工程目录分组，再默认按“主素材”展示，避免贴图、视频等支持文件干扰日常浏览。

### 素材详情

```http
GET /api/v1/assets/{asset_id}
```

用途：

- 获取素材元数据、标签、缩略图地址、备注、评分、收藏状态等。

### 更新素材

```http
PATCH /api/v1/assets/{asset_id}
```

可更新字段包括：

- `description`
- `author`
- `rating`
- `is_favorite`

### 标记最近打开

```http
POST /api/v1/assets/{asset_id}/open
```

用途：

- 更新 `last_opened_at`。
- 支持前端“最近打开”排序。

### 更新素材标签

```http
POST /api/v1/assets/{asset_id}/tags
```

支持两种方式：

- 传入已有 `tag_ids`。
- 传入 `tag_names`，不存在的标签由后端创建。

### 批量更新素材

```http
PATCH /api/v1/assets/batch
```

请求示例：

```json
{
  "asset_ids": ["asset-a", "asset-b"],
  "is_favorite": true,
  "tag_names": ["舞台", "演唱会"],
  "move_to_trash": false
}
```

用途：

- 批量收藏或取消收藏。
- 批量添加标签。
- 批量移入回收站。

设计说明：

- 只会操作当前用户、未删除的素材。
- 批量打标签会复用已有标签，不存在的标签由后端创建。
- 批量移入回收站仍然只是软删除数据库索引，不删除磁盘文件。

### 移入回收站

```http
DELETE /api/v1/assets/{asset_id}
```

设计说明：

- 只把数据库索引标记为 `is_deleted=true`。
- 不删除用户磁盘上的真实文件。

## 6. 标签

### 标签列表

```http
GET /api/v1/tags
```

用途：

- 获取当前用户所有标签。
- 用于素材筛选和详情编辑。

### 创建标签

```http
POST /api/v1/tags
```

字段：

```json
{
  "name": "舞台",
  "color": "#60a5fa"
}
```

### 更新标签

```http
PATCH /api/v1/tags/{tag_id}
```

字段：

```json
{
  "name": "演出舞台",
  "color": "#2563eb"
}
```

说明：

- 标签名称在同一用户下保持唯一。
- 可用于集中整理 AI 标签和手动标签。

### 删除标签

```http
DELETE /api/v1/tags/{tag_id}
```

说明：

- 删除标签会移除素材和标签的关联。
- 不影响素材本身。

## 7. 搜索

### 普通搜索

```http
GET /api/v1/search?q=concert
```

说明：

- 内部复用素材列表查询。
- 适合名称、路径、备注等关键词搜索。

### 自然语言搜索

```http
POST /api/v1/search/natural-language
```

请求示例：

```json
{
  "query": "找一个适合演唱会的大舞台",
  "limit": 10
}
```

当前实现：

- 使用本地语义规则解析关键词。
- 按素材名称、路径、描述、类型等字段评分。

可扩展方向：

- 替换为 Embedding 检索。
- 使用 PostgreSQL + pgvector 存储向量。
- 接入 OpenAI Compatible API 生成查询向量。

## 8. AI 分析

### 分析素材

```http
POST /api/v1/ai/assets/{asset_id}/analyze
```

用途：

- 为素材生成标签。
- 为素材生成描述。
- 写回数据库。

当前实现：

- 如果设置页配置了 AI Base URL、API Key 和 Chat 模型，后端会调用 OpenAI Compatible `/chat/completions` 生成标签和描述。
- 调用失败、返回格式不合法或未配置 Key 时，会自动回退到本地启发式规则，保证离线和面试演示稳定。
- 响应中的 `source` 会标明来源：`openai-compatible` 或 `local-heuristic`。

后续增强方向：

- 图片使用多模态模型生成标签。
- 模型文件可以先生成预览图，再送入视觉模型。
- 文本描述和标签写入后参与自然语言搜索。

## 9. 项目管理

### 项目列表

```http
GET /api/v1/projects
```

返回项目和引用素材数量。

### 创建项目

```http
POST /api/v1/projects
```

字段：

```json
{
  "name": "演唱会 Demo",
  "description": "包含人物、舞台、动作和音乐"
}
```

### 项目详情

```http
GET /api/v1/projects/{project_id}
```

返回：

- 项目基本信息。
- 项目引用的素材。
- 每个引用素材的角色，例如 `character`、`stage`、`motion`、`music`。

### 更新项目

```http
PATCH /api/v1/projects/{project_id}
```

字段：

```json
{
  "name": "演唱会 Demo",
  "description": "更新后的项目说明"
}
```

说明：

- 用于维护作品项目名称、说明和封面素材。
- 前端项目页可直接编辑名称和说明。

### 添加项目素材

```http
POST /api/v1/projects/{project_id}/assets
```

请求：

```json
{
  "asset_id": "...",
  "role": "stage"
}
```

### 批量添加项目素材

```http
POST /api/v1/projects/{project_id}/assets/batch
```

请求：

```json
{
  "asset_ids": ["asset-a", "asset-b"],
  "role": "stage"
}
```

说明：

- 只会添加当前用户、未删除的素材。
- 如果素材已经在项目中，会更新它在项目中的角色。
- 适合在素材库多选后，把一组人物、舞台、动作或贴图素材一次性加入作品项目。

### 移除项目素材

```http
DELETE /api/v1/projects/{project_id}/assets/{asset_id}
```

说明：

- 只删除项目引用关系。
- 不删除素材索引。
- 不删除磁盘文件。

### 导出项目清单

```http
GET /api/v1/projects/{project_id}/export?format=json
GET /api/v1/projects/{project_id}/export?format=csv
```

用途：

- 导出项目引用的素材清单。
- 适合面试演示“一个作品用了哪些素材”。
- 也适合未来对接 UE5/Blender 打包流程。

导出字段包括：

- 项目名称
- 素材角色
- 素材名称
- 类型
- 扩展名
- 文件大小
- 原始路径
- 文件指纹
- 是否仍存在于磁盘

## 10. 重复检测

### 获取重复素材组

```http
GET /api/v1/assets/duplicates
```

实现说明：

- 对缺少指纹的素材补算快速文件指纹。
- 按 `file_hash + size_bytes` 聚合。
- 返回重复组、重复素材数量、已计算指纹素材数量。

设计取舍：

- 当前优先使用快速指纹，适合 MVP 阶段和大文件场景。
- 后续可以增加精确 hash 模式。

## 11. 失效素材检查

### 扫描失效素材

```http
POST /api/v1/assets/missing/scan
```

用途：

- 检查数据库索引对应的磁盘路径是否仍存在。
- 如果文件被外部移动或删除，标记为失效。
- 如果文件恢复，自动恢复 `exists_on_disk` 状态。

### 获取失效素材列表

```http
GET /api/v1/assets/missing
```

用途：

- 集中处理已经失效的素材索引。

## 12. 回收站

### 回收站列表

```http
GET /api/v1/trash/assets
```

### 恢复素材

```http
POST /api/v1/trash/assets/{asset_id}/restore
```

### 永久删除索引

```http
DELETE /api/v1/trash/assets/{asset_id}
```

设计说明：

- 回收站中的“永久删除”仍然只删除数据库索引。
- 不删除磁盘真实文件。

## 13. 统计

### 统计概览

```http
GET /api/v1/stats/overview
```

返回内容：

- 素材总数
- 总容量
- 收藏数量
- 标签数量
- 素材目录数量
- 最近 7 天新增
- 类型分布
- 扩展名排行

用途：

- 支撑前端统计页。
- 面试时展示系统不是简单列表，而是有运营/管理视角。

## 14. 设置与备份

### 获取设置

```http
GET /api/v1/settings
```

### 更新设置

```http
PATCH /api/v1/settings
```

设置项包括：

- 缓存目录
- 主题
- AI Base URL
- AI API Key
- Chat 模型
- Embedding 模型
- 缩略图质量

### 测试 AI 配置

```http
POST /api/v1/settings/test-ai
```

当前用于检查 AI 配置是否填写完整。后续可以扩展为真实 API 连通性测试。

### 数据库备份

```http
POST /api/v1/settings/backup-database
```

用途：

- 复制 SQLite 数据库文件到备份目录。
- 返回备份路径、大小和创建时间。

## 15. 任务

### 任务详情

```http
GET /api/v1/tasks/{task_id}
```

用途：

- 查看扫描任务状态。
- 前端可以轮询展示进度。
- 任务中心页面会展示最近 50 条任务的状态、进度、结果和错误信息。

任务状态：

- `pending`
- `running`
- `success`
- `failed`
- `canceled`

## 16. 错误约定

常见状态码：

- `400`：请求参数或业务前置条件不满足，例如目录不存在、不支持的导出格式。
- `401`：未登录或 token 无效。
- `404`：资源不存在，或资源不属于当前用户。
- `422`：请求体字段校验失败。

设计说明：

- 对于跨用户访问，统一表现为资源不存在，避免暴露其他用户数据是否存在。
- 对于文件系统操作，优先返回明确的业务错误，例如目录不存在。

## 17. 典型业务流程

### 17.1 首次使用

1. 注册或登录。
2. 添加素材目录。
3. 执行目录扫描。
4. 轮询任务状态。
5. 进入素材库浏览和搜索。

### 17.2 整理素材

1. 在素材库筛选类型或关键词。
2. 打开素材详情。
3. 添加标签、收藏、评分、备注。
4. 对素材执行 AI 分析。
5. 使用自然语言搜索验证标签和描述效果。

### 17.3 组织作品项目

1. 创建项目。
2. 搜索素材。
3. 按角色加入项目，例如人物、舞台、动作、音乐。
4. 导出项目清单。
5. 根据清单检查素材路径和缺失状态。

### 17.4 维护素材库健康

1. 执行重复检测。
2. 执行失效素材检查。
3. 对不需要的索引移入回收站。
4. 必要时恢复或永久删除索引。
5. 执行数据库备份。

## 18. 后续演进

如果继续做企业级增强，API 层可以按以下方向扩展：

- 增加 Alembic 迁移脚本，替代运行时补 schema。
- 增加 Celery 任务接口，扫描和 AI 分析不阻塞请求。
- 增加 OpenAPI 导出文档和 Postman Collection。
- 增加批量操作接口，例如批量打标签、批量加入项目。
- 增加素材文件监听接口，用 Watchdog 同步新增、修改和删除。
- 增加项目导出包接口，为 UE5/Blender 工作流生成素材清单或打包目录。
