> 中文 | [English](README_EN.md)

# AI in Blender · Agent Platform 3.2

在 Blender 中运行带持久对话、可审计记忆、多模态输入和受检验执行分支的智能体工作平台。架构智能体规划装配与任务，专家分别生成部件、材质、绑定、动画和媒体，人可以在过程中继续编辑。

独立部件分支可以并行，共享场景提交串行且检查人工修改冲突。结构质量门不能省略，视觉验收默认需要人确认。插件提供可验证的执行机制，不承诺任意模型或提示词都能产出专家级作品。完整设计见 [平台设计](docs/PLATFORM_DESIGN.md)，实操见 [平台使用指南](docs/PLATFORM_GUIDE.md)。

## 3.2 工作流可靠性升级

3.2 修复 GitHub 上 Blender 3.6 材质回退失败，并补齐记忆、压缩、协作、恢复和质检的执行约束。完整状态转移、故障处理和验收边界见 [生产工作流规范](docs/WORKFLOW_LIFECYCLES.md)。

- **记忆演进**：重复证据合并、会话/项目/个人优先级、重要约束保护、遗忘后的重复提取抑制、带实际结果的任务情景记忆。
- **上下文预算**：按完整原文分批压缩；所有模型调用都扣除输出与图像预留；缺省历史显式可见。
- **任务恢复**：独立失败不取消其他分支；调用前持久化记录；有 ID 的生成任务通过 GET 恢复；产物以 SHA-256 校验。
- **质量闭环**：对求值后的修改器网格检查；继承部件质量合同；创作修复后必须再评审；导出前重新验收。
- **编辑保护**：新增权重、属性、NLA、UV 区域、单位/帧率冲突检查，以及媒体导入失败的清理。
- **安装验收**：CI 测试源码、传统 ZIP、真实扩展安装及扩展内的工作进程。对应提交的结果见 [Actions](https://github.com/hxjyaohaohaode/AI-In-Blender/actions)。

## 平台能力

- **真实多轮对话**：SQLite 保存项目、多个会话与逐条原文，重新打开文件后可继续。历史不是仅存在内存中的最近几条消息。
- **自动语义压缩**：到达预算阈值调用摘要模型，保存带来源编号的摘要检查点；原文保留。失败时明确使用抽取式降级摘要。
- **全层记忆**：短期会话、项目、长期个人、程序性经验分类；来源引用、状态、有效期、版本、去重、冲突、确认、拒绝、修订、恢复、遗忘和备份。
- **可信记忆演进**：模型只能提出带用户原文证据的候选；用户确认才用于个性化。原生验证结果自动记录为有限范围的事实，不能自动升级成审美结论。
- **协作编排**：最多 24 个依赖任务；独立根部件通过 `part_id` 获得并行分支，每流程并发 1–4，可同时运行两个工作流。共享部件、装配和导出按依赖串行。
- **可测量合同**：顶点数量、材料、UV、闭合要求、空间范围、命名锚点与容差；任务必须通过适用检查。
- **副本执行**：AI 代码在独立 Blender 后台进程处理副本，带超时、原生检查和 Workbench 预览。主线程合并前比对对象内容指纹，冲突时保留候选并停止覆盖。
- **人在回路中**：原生 Grease Pencil 草图、视口参考、输入附件、编辑区域锚点。顶点精修拒绝越界、拓扑和全对象变换修改；编辑模式结束前不合并候选。
- **多模态输入**：视觉模型实际接收图像字节；Bridge v2 上传图片/文本/3D/音视频输入并传递资产句柄。文本模型只收到不支持媒体的清单，不声称理解文件内容。
- **强制自检**：原生结构门、可选带真实几何预览的视觉评审、默认人工视觉批准、与当前指纹绑定的导出门。旧批准不能用于改过的对象。
- **主动服务**：本地监听变化并给出材料、UV、记忆冲突、待检验建议；不自动收费或改场景。
- **持续运行**：调用和修复预算、取消、失败阻断、保留成功任务重试、匹配已保存场景的显式检查点恢复。

## 保留的基础能力

- 模块化：独立的任务/协议核心、Blender 适配、创作工具、UI 和模型数据。
- 专家工作流：规划、建模、材质、绑定、动画、创作评审、几何检查、导出，以及外部 3D/图像/视频/语音/世界生成任务。
- 模型路由：按能力和专家匹配服务；缺少能力时明确停止。
- 独立 HTTP 子进程：等待模型时不阻塞 Blender，可取消；后台副本处理结束后在主线程合并。
- 可靠状态：失败阻断依赖步骤；重试保留成功步骤；代码自动修复次数有上限。
- 审阅与记录：默认逐步审阅生成的 Python；计划和代码均可编辑；保存产物与 `run.json`。
- 保留工具：16 个快速模型、30 种材质预设、修改器、UV、绑定、动画、程序化生成与批量操作。
- 导出保护：GLB/FBX/OBJ/STL 导出恢复选择状态，不预先破坏源对象缩放和修改器。
- 凭据管理：密钥只进入会话内存或指定环境变量；旧版密钥属性迁移到内存后移除。

## 模型接入范围

| 类型 | 实现 | 本次验证 |
|---|---|---|
| 大语言模型 | OpenAI 兼容 Chat Completions；远程服务、Ollama、LM Studio | 本地 HTTP 模拟服务 + 实际工作进程 |
| 3D 生成 | Meshy Text-to-3D preview/refine，或 Jobs Bridge | 协议模拟 + 实际 GLB 导入 |
| 图像 | OpenAI 兼容 Image Generations | 协议模拟 + 图像参考对象 |
| 语音合成 | OpenAI 兼容 Speech API | 协议模拟 + VSE 音轨 |
| 音频转写 | OpenAI 兼容 Transcriptions API | multipart 文件上传协议模拟 |
| 视频与世界模型 | 有明确契约的 Async Jobs Bridge | Bridge 协议模拟；实际服务需实现此契约 |
| 创作专家 | 生成、检查、执行 Blender Python | 真实 Blender 测试与离线示例 |

本次没有使用真实付费模型账号验收服务可用性或生成质量。配置服务时需填写该服务实际支持的模型与参数。Bridge 不是所有供应商的现成原生接口；ComfyUI、Runway 或特定世界模型需要实现对应适配服务，详见 [接入文档](docs/PROVIDERS.md)。

启用 Vision 能力的评审专家会收到真实 Workbench 几何预览；普通文本评审明确不具有视觉证据。几何预览不等于最终 PBR、灯光、动画逐帧或语义正确性验证。世界模型输出以 3D 场景资产导入，不是通用世界模拟运行时。

## Blender 兼容性

| 版本 | 状态 |
|---|---|
| Windows + Blender 5.1.1 | 本机实际验证，详见 [验证记录](docs/VALIDATION.md) |
| Linux + 3.6.23 | CI：源码、预设、流程与传统 ZIP 安装 |
| Linux + 4.2.0 / 4.5.3 / 5.1.1 | CI：源码、传统 ZIP、真实扩展安装及工作进程 |
| 其他 4.x/5.x、macOS | 未列入实测矩阵 |

最低版本为 **Blender 3.6**；不支持 2.x、3.0–3.5，也不保证未来版本无需适配。仓库包含 3.6.23 / 4.2.0 / 4.5.3 / 5.1.1 的 CI 矩阵，未运行的矩阵不视为通过证明。

## 安装

```shell
python tools/build.py
```

- `dist/ai-in-blender-3.2.0-extension.zip`：Blender 4.2+，Preferences → Get Extensions → Install from Disk。
- `dist/ai-in-blender-3.2.0-legacy.zip`：Blender 3.6+，Preferences → Add-ons → Install / Install from Disk。
- `dist/SHA256SUMS.txt`：安装包校验值。

两种包选择一种。升级前停用旧的单文件插件，避免 `ama.*` 操作符重复注册。新版不再单独分发 `.py`。运行时无需额外 pip 依赖。启用后在 3D View 按 **N**，打开 **AI Model**。

## 使用

### 不需要账号的示例

点击 **Offline Demo / 离线示例**，创建 HELIO 机械轨道装置，包含命名网格、PBR 材质、骨骼控制、120 帧动画、GLB 和几何报告。这是内置程序化示例，不是在线 AI 作品。原有 Quick Build 也不需要 API。

### 配置模型

在 **Models & Settings / 模型配置** 中，可使用 Basic Chat Provider 配置一个 LLM，也可添加多个 Provider，填写协议、Base URL、模型名和凭据来源。给模型选择专家；专家留空时作为该能力的默认候选。原生协议自动确定能力，Bridge 需选择服务实际具备的能力。

会话密钥在加载其他文件或停用插件时清除。持久配置建议通过 `Key environment variable` 指定环境变量，例如 `AI_IN_BLENDER_API_KEY`。旧 `.blend` 中的密钥会迁移到当前会话，并从新版属性中移除；已保存的旧文件仍需重新保存才能更新。

远程请求需要 Blender **Online Access**。HTTP 仅允许 loopback 地址，远程服务使用 HTTPS，证书验证保持开启。

### 运行专家团队

1. 在 **Brief / 目标** 写清成品，例如“制作一个带金属和发光材质的机械能量装置，添加旋转动画，检查后导出 GLB”。
2. 点击 **Plan / 规划**，查看任务、专家、依赖和具体指令。
3. 如需修改，点击 **Edit Plan**，在 Text Editor 编辑 JSON，回到侧栏点击 **Use Edited Plan**。
4. 点击 **Run / 执行**。默认在每份生成代码前暂停，审阅后点击 **Apply Code**。
5. 在 Text Editor 修改代码后使用 **Run Edited Code**；Apply Code 使用侧栏当前代码。
6. 查看输出目录与 **Read Run Report**。失败后调整配置，使用 **Retry Unfinished Tasks**。
7. 导出前检视当前模型和 **View Latest Preview**。默认点击 **Approve Visual Quality** 后才能导出；修改过模型会要求重新检验。

`Run after planning` 可衔接规划和执行。关闭 `Review each generated script` 后代码会自动执行，应使用你信任的模型。评审失败会阻断依赖的导出；需要修正计划或内容后再重试。

3D 产物进入当前工作流集合；图像创建参考对象，不会自动假装已成为模型贴图；视频和音频进入 VSE 空闲通道；转写文字进入任务结果和建模提示框。跨系统 3D 交换建议使用自包含 GLB，单独 OBJ 不会自动补齐外部 MTL/纹理。

## 执行边界

AST 检查、受限导入和独立 Blender 进程共同减少副作用，但**不是操作系统级沙箱**。模型代码不接收供应商密钥，场景进程有可终止期限。仍应使用可信的模型和审阅生成代码。

AI 工作流对副本执行。失败或内容指纹冲突不会把候选合并到原对象；通过后替换目标对象并重映射其引用。源集合与相关数据仍需正常保存 `.blend`。任意 Blender 数据块、外部插件、复杂驱动和全部节点系统不能因此被宣称具备完美事务与冲突覆盖；生产场景应保留版本备份。内置手工建模工具继续在当前场景直接操作。

区域精修是有拓扑约束的网格编辑，不是通用纹理画笔/视频遮罩编辑器。视频、世界和任意新供应商需要真实的适配服务；已提供桥接契约不等于已安装这些模型。长期记忆默认存于 Blender DATAFILES 下 `AIInBlender/platform.sqlite3`，可用 `AI_IN_BLENDER_MEMORY_DB` 指定路径。数据库没有应用层加密；项目遗忘不删除系统备份和单独生成的资产。

取消会终止本地工作进程并阻止迟到结果应用，已提交的远程任务仍可能继续执行和计费。POST 不自动重发，GET 查询有限重试。插件显示 token 用量，不以过期价格表估算费用。

## 开发

```shell
python -m unittest discover -s tests -v
blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
python tools/build.py
blender --background --factory-startup --python-exit-code 1 --python tools/render_demo.py
```

测试使用本地模型模拟服务，无需 API 凭据。示例构建输出 `.blend`、动画 `.glb`、PNG 与报告。设计见 [ADR](docs/adr/0001-expert-studio.md)，证据见 [验证记录](docs/VALIDATION.md)。

```text
ai_modeling_assistant/
  core/       # 记忆、上下文、附件、任务合同、协议和进程
  blender/    # 对话、主动建议、编排、冲突指纹、质量门、分支合并、UI
  data/       # 提示词、模型与材质预设、模板、翻译
  worker.py   # 独立网络工作进程
  scene_worker.py # 独立 Blender 分支执行和预览
tests/        # 核心、协议、打包和真实 Blender 回归
tools/        # 构建安装包与示例工程
docs/         # 架构、接入契约、验证证据
```

许可证：GPL-3.0，见 [LICENSE](LICENSE)。
