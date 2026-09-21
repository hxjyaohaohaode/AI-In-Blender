# Agent Platform 3.2 使用指南

## 安装与第一条完整工作流

Blender 4.2+ 选择 `dist/ai-in-blender-3.2.0-extension.zip`，3.6 使用 legacy ZIP。两者安装一种，先停用旧版单文件插件。打开 3D View，按 N，进入 **AI Model**。本机已实测 Windows / Blender 5.1.1；其他版本见验证记录。

1. 在 Models & Settings 中添加 Chat Completions 模型，填写实际 Base URL、模型 ID 和密钥环境变量；密钥输入框只在当前会话保留。给不同提供商分配 planner、conversation、modeler、material、rigger、animator、reviewer 等角色。Vision 只有确实支持图片的模型才能启用。
2. 在 Conversation & Memory 中讨论目标，例如“做一个适合游戏引擎的机械无人机，左右旋翼为独立部件，保留可动画的接口”。继续补充“总宽 1.2 米、两侧锚点分别在 X=±0.45 米”，真实原文会逐条保存。
3. 点击 **Plan from Conversation**。规划会读取当前会话、已确认记忆、场景事实与附件。检查任务依赖、装配说明和合同，必要时用 Edit Plan 调整 JSON。
4. Run 执行；默认每份脚本先显示代码，Apply Code 才开始隔离分支。独立根部件有不同 `part_id` 时并行；公共材质、绑定、动画、装配、导出步骤串行。
5. 查看实时任务状态、Read Run Report 与 View Latest Preview；Reverse / Top 可以查看背面和顶面。通过结构门后，导出默认停在人工视觉验收。检视当前场景，再点击 Approve Visual Quality；如果对象在检查后变化，旧批准失效。

**聊天回复本身不会编辑场景**。按照讨论启动计划后，生产任务才会调用生成工具。这让讨论、修订和实际修改有明确边界。关闭逐份代码审阅或人工视觉批准是显式的产品设置；原生结构检查始终执行。

## 记忆：如何生成、使用和修订

完整对话和记忆数据库默认在 Blender 的 DATAFILES/AIInBlender/platform.sqlite3。Memory Audit 会显示实际路径。可在启动 Blender 前设置 `AI_IN_BLENDER_MEMORY_DB` 指向另一个本地文件。数据库只使用标准库 SQLite，无需服务器或 pip。

同一 `.blend` 中首次使用的新场景默认加入已有项目；已有项目 ID 随场景保存。另存文件沿用项目身份；需要独立项目时点击 Fork Memory Project。每个项目可创建多个会话、按页切换。长期个人记忆在本机同一用户配置间共享；关闭 Personal Memories 可禁止本轮读取或提议这种范围的记忆。

即使没有保存 `.blend`，原文仍在 SQLite 中。重新启动后点击 Local Projects 刷新本机项目目录，再选择原项目和会话。会话标题取第一条用户消息，列表支持分页。保存 `.blend` 则能直接保留当前项目/会话选择。

- **短期**：会话范围，默认一天后不再检索；过期不删除原文。
- **项目**：单位、风格、约束、决策、未决问题和明确的方法，只有这个项目可以检索。
- **长期个人**：明确的持续偏好和工作方式，用户确认后跨项目使用。
- **历史执行事实**：通过原生结构检查的任务可自动记录为历史检查点，包含输出指纹和报告位置。不能据此声称当前对象仍存在或艺术质量通过。

每轮回复后，启用 Memory Candidates 时模型会提议最多 8 条记忆。引用必须是本会话用户原文的真实子串，模型自述不能当作证据。候选、冲突、被拒绝和被替代的版本不会冒充已确认事实参与检索。

在列表点击候选，选择 Confirm / Reject / Restore / Forget，可修改正文后再确认。相同范围和 key 的冲突值不静默覆盖；确认新版本会把旧版本标为 superseded，历史修订可在 Memory Audit 查看。并发修订必须匹配打开时的版本。想马上锁定一条明确要求，可使用 Remember Latest Instruction；它把最近用户指令确认为项目约束。

记忆使用中文双字/词语、重要度和时间排序，先按用户/项目/会话隔离，再执行上下文预算。**这是本地词汇检索，未宣称具有向量数据库或全自动事实推理。** 模型辅助匹配已有语义 key、归纳原文和提出更新，人控制持久信念的升级。记忆是参考数据，本轮明确要求与当前场景观测优先。

Generate Candidates 与 Use Verified Memory 分开：可以停用额外提取调用，同时继续个性化检索。Backup Local Memory 生成一致的 SQLite 备份；恢复备份时先停用插件，再用备份替换数据库或改用环境变量指向备份副本。Erase Project Conversations & Memory 删除项目原文、摘要、事件和引用它们的个人记忆；独立备份、系统备份及产物文件不在这项删除的范围中。

## 压缩与调用预算

达到输入预算阈值时，自动摘要生成目标、约束、决定、进展、未决问题和资产引用，逐条引用来源 turn ID。只压缩模型本次需要读取的上下文，不删除数据库里的原始消息。摘要失败会保存有明确模式标记的抽取式检查点。

对话大模型并不能把任意长历史全塞进一次请求。Context Budget 控制估算输入量；模型 options 中可设置实际 `context_window`，插件扣除输出 token 配额与余量。估算不是该模型的精确 tokenizer。当前用户消息装不下时直接报告，不静默截断。压缩按完整原文分批，每轮最多三次模型调用；记忆提取另有一次调用，两者可分别关闭。图片输入通过 `vision_tokens_per_image` 预留预算，实际遗漏的历史会在审计和模型上下文中明确提示。

生产工作流有最大调用次数、每步修复次数和并发数上限。取消会终止本地 HTTP/Blender 进程；已提交远端任务的运行及计费由供应商控制。

## 草图、图片与精确编辑

Draw Sketch 创建原生 Grease Pencil 并进入绘制模式。用 Blender 原生画笔画参考，再点击 Use Viewport，生成 768×768 PNG 并添加为输入。截图功能需要可用的交互式 3D View；后台测试只验证原生绘制对象的创建，不声称测试了实际手绘体验。

文件输入支持图片、UTF-8 文本、3D、视频和音频。最多 8 个附件、每份最多 25 MB。视觉聊天当前最多发送合计 1 MB 的图片原始数据；大图请使用参考预览。附件带 SHA-256，磁盘文件改变后必须重新添加，避免错用旧引用。当前附件随场景保存为清单，不会自动复制或打包到 `.blend`。

普通聊天只真正解释文本和启用 Vision 的图像；音视频/3D 清单不会被当成已经理解。多模态生产通过 Bridge v2 上传真实字节。原生 Meshy Text-to-3D / Image Generations 是文本输入接口，携带二进制条件时明确拒绝，不能伪装成图生 3D 或图像编辑。详见 PROVIDERS.md。

精修流程：选择对象，进入 Edit Mode 选定顶点/面，点击 Capture Edit Region，再回 Object Mode 使用 Refine Selected。候选会核对对象 ID、输入指纹、顶点和面索引，拒绝外部顶点变化、拓扑变化、全对象变换、全局修改器或共享材质修改。需要重拓扑或全局材质替换时清除区域锚点并建立单独任务。它不是通用逐像素遮罩编辑器，也不保证任意复杂 Blender 数据块都能完整追踪。

## 并行协作与质量合同

```json
{
  "assembly": {"units":"meters","up":"Z","description":"Keep each component inside its allocated space"},
  "tasks": [
    {"id":"left","expert":"modeler","prompt":"Create the left mechanical part and an Empty named LeftAnchor at (-1,0,0)",
     "contract":{"part_id":"left","require_geometry":true,"bounds_min":[-2,-1,-1],"bounds_max":[0,1,1],"anchor_object":"LeftAnchor","anchor_position":[-1,0,0],"anchor_tolerance":0.001}},
    {"id":"right","expert":"modeler","prompt":"Create the matching right part in X from 0 to 2",
     "contract":{"part_id":"right","require_geometry":true,"bounds_min":[0,-1,-1],"bounds_max":[2,1,1]}},
    {"id":"check","expert":"inspector","prompt":"Verify both parts","depends_on":["left","right"]},
    {"id":"review","expert":"reviewer","prompt":"Assess assembled silhouette against the brief","depends_on":["check"]},
    {"id":"export","expert":"exporter","prompt":"Export the assembly","depends_on":["review"]}
  ]
}
```

每个流程最多 24 个节点，每流程 1–4 个独立分支；最多两个生产流程同时活跃。根部件有独立集合，依赖步骤接收实际前置结果。共享写入被串行安排，场景主线程串行提交。源数据在模型回复或分支计算时变化，会停止合并并保留 candidate.blend。人在 Edit Mode 中操作时先等待退出，再检查版本。

原生质量检查包括非空、有限坐标/变换、退化面、可选闭合性、材料、UV、顶点预算、空间范围与命名锚点。未指定闭合要求时，开放边作为提示而不是一律失败。结构失败可进行有次数上限的模型修复，失败仍阻断依赖任务。对于复杂 Geometry Nodes、外部图像变更、驱动等数据，当前指纹与结构分析不保证全覆盖；采用人工检视与文件版本管理补充。

Vision reviewer 使用真实 Workbench 图像看形状、比例与构图；该图不代表最终 PBR 光照或整段动画的质量。默认最终由用户确认当前版本的视觉质量。强制检验保证检查流程与失败阻断，不保证任何供应商的输出具有固定审美水平。

## 重试、恢复与主动建议

普通失败用 Retry Unfinished Tasks，成功节点不重做。需要冷启动恢复时，先打开保存过的 `.blend`，选择对应 run.json，再点击 Resume Saved Checkpoint。对象内容和集合成员必须与检查点匹配，成功产物的 SHA-256 必须相同；否则拒绝恢复。并行子任务在请求前同步主检查点，调用数和修复次数不会因重试清零。已知 Bridge / Meshy 任务 ID 通过 GET 查询继续；没有可信 ID 的超时提交明确阻止重发，请根据报告中的 remote-job.json 检查供应商记录。

场景变化后，本地建议定期检查所选对象的材料/UV、记忆冲突和待批准质量门。Check Next Actions 执行更详细的原生检查。这些主动功能不调用付费模型、不自行上传资产，也不自动修改场景。

部署模型凭据和真实供应商联调不包含在本次离线验收中。先用内置 HELIO 示例和项目自带测试确认 Blender 环境，再接入你自己的模型服务。
