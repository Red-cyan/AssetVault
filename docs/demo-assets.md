# 演示数据使用说明

AssetVault 不应该把大量真实素材提交到 Git 仓库。为了方便面试演示，本项目提供了一个演示素材生成脚本：

```bash
uv run python scripts/create_demo_assets.py
```

默认会在项目根目录生成：

```text
demo-assets/
```

目录中包含：

- 人物图片：`anime_blue_hair_twin_tail_jk.png`
- MMD 模型占位：`mmd_character_sample.pmx`
- 舞台图片：`concert_stage_led_screen.png`
- OBJ 舞台模型：`white_performance_stage.obj`
- VMD 动作占位：`dance_motion_pop.vmd`
- 贴图图片：`fabric_blue_pattern.png`
- HDR 占位：`concert_hall_light_probe.hdr`
- UE5 资源占位：`ue5_stage_prop.uasset`
- Blender 文件占位：`lighting_setup.blend`

## 重新生成

如果要覆盖已有演示文件：

```bash
uv run python scripts/create_demo_assets.py --force
```

如果要生成到其他目录：

```bash
uv run python scripts/create_demo_assets.py --output E:\AssetVaultDemo
```

## 前端演示流程

1. 启动后端：

   ```bash
   uv run uvicorn backend.app.main:app --reload
   ```

2. 启动前端：

   ```bash
   cd frontend
   npm run dev
   ```

3. 浏览器打开：

   ```text
   http://localhost:3000
   ```

4. 使用开发账号登录：

   ```text
   username: demo
   password: assetvault
   ```

5. 进入设置页或素材库页，添加素材目录：

   ```text
   E:\PythonLearning\AssetVault\demo-assets
   ```

6. 执行扫描，进入素材库查看导入结果。

## Docker 演示流程

Docker Compose 默认会把 `.env` 里的 `ASSETVAULT_ASSET_ROOT` 挂载到容器内 `/assets`。

建议先生成演示素材：

```bash
uv run python scripts/create_demo_assets.py
copy .env.example .env
docker compose up --build
```

然后在前端添加素材目录：

```text
/assets
```

## 面试讲解口径

可以这样说明：

> 演示素材不是手工放进数据库的，而是通过脚本生成到本地目录，再由 AssetVault 的扫描功能建立索引。这样可以证明系统的真实工作流是“扫描文件系统 -> 建立数据库索引 -> 生成缩略图 -> 搜索和管理”，不是预置假数据。

## 注意事项

- 占位的 PMX、VMD、UAsset、Blend 文件只用于扫描和元数据演示，不代表真实可打开素材。
- 图片文件是真实 PNG，可以生成缩略图。
- OBJ 文件是简单文本模型，可以用于验证模型格式识别。
- `demo-assets/` 是本地演示产物，不建议提交到 Git。
