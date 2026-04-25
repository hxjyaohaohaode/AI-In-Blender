# AI Modeling Assistant for Blender

> AI 驱动的 3D 建模助手 — 让 AI 成为你的建模搭档，而不是只会堆方块的实习生。

## 这是什么？

一个 Blender 插件，让你用自然语言描述想要的模型，AI 自动生成高质量的 Python 建模代码并执行。支持任何 OpenAI 兼容 API（OpenAI、DeepSeek、Qwen、Ollama 本地模型等）。

## 核心特性

### 🧠 智能建模（不是堆方块）

AI 会经过 **5 阶段思考** 后再写代码：

1. **设计分析** — 拆解为独立部件，规划每个部件的几何形状
2. **比例规划** — 基于真实世界尺寸（米），确保比例正确
3. **拓扑策略** — 选择最合适的建模技法（挤出/旋转/细分/布尔/曲线…）
4. **材质策略** — 为每个部件分配 PBR 材质，匹配真实物理属性
5. **质量自检** — 面数、法线、孤立顶点，自动检查

系统提示词内置 **8 种建模技法**（含完整代码示例）：
- 挤出建模（硬表面）
- 旋转/车削（花瓶、柱子）
- 细分曲面（有机体）
- 布尔运算（复杂切割）
- 曲线+倒角（管道、装饰）
- 阵列+曲线（链条、栅栏）
- 比例编辑（有机变形）
- 骨架+蒙皮（树枝、珊瑚）

### 🔄 多阶段生成

复杂模型一次生成质量不够？用 **3 轮 AI 生成**：

| 阶段 | 做什么 |
|------|--------|
| 第 1 轮 | 基础形状 — 搭建正确的大比例几何体 |
| 第 2 轮 | 几何细节 — 添加倒角、内插、装饰元素 |
| 第 3 轮 | 材质抛光 — PBR 材质、表面纹理、最终清理 |

### ✏️ AI 精修

选中已有的模型 → 描述想怎么改 → AI 用 bmesh **在原模型上修改**，不会重新创建。

### 🛡️ 安全机制

- SSL 验证始终启用
- 代码沙箱：AI 生成的代码不能访问 `os`、`subprocess`、文件系统
- 危险操作自动拦截（`eval`、`exec`、`open`、`__import__` 等）
- 白名单机制：只允许 `bpy`、`bmesh`、`math`、`mathutils`、`random`

---

## 安装

### 方法 1：直接安装 .py 文件

1. 下载 `ai_modeling_assistant.py`
2. 打开 Blender → Edit → Preferences → Add-ons
3. 点击 `Install...` → 选择下载的 .py 文件
4. 勾选启用 "AI Modeling Assistant"

### 方法 2：手动放入插件目录

将 `ai_modeling_assistant.py` 复制到：
- **Windows:** `%APPDATA%\Blender Foundation\Blender\<版本>\scripts\addons\`
- **macOS:** `~/Library/Application Support/Blender/<版本>/scripts/addons/`
- **Linux:** `~/.config/blender/<版本>/scripts/addons/`

然后在 Blender 中启用。

### 兼容性

- Blender **3.6+** 和 **4.x** 均已测试兼容
- 3.x/4.x API 差异已自动处理（材质节点名称等）

---

## 使用方法

### 1. 配置 API

打开侧边栏（按 `N` 键）→ **AI Model** 标签页 → 展开 **API Settings**：

| 设置 | 说明 |
|------|------|
| **Preset** | 选择预设（OpenAI、DeepSeek、Qwen 等），或选 "Custom" |
| **API URL** | API 地址（预设会自动填入） |
| **API Key** | 你的 API 密钥 |
| **Model** | 模型名称 |
| **Temperature** | 创造性（0.0=精确，2.0=随机） |
| **Max Tokens** | 最大回复长度 |

#### 支持的 API 预设

| 预设 | API 地址 | 默认模型 |
|------|---------|---------|
| OpenAI | api.openai.com | gpt-4o-mini |
| DeepSeek | api.deepseek.com | deepseek-chat |
| Qwen (阿里) | dashscope.aliyuncs.com | qwen-plus |
| Zhipu (智谱) | open.bigmodel.cn | glm-4-flash |
| Moonshot | api.moonshot.cn | moonshot-v1-8k |
| SiliconFlow | api.siliconflow.cn | Qwen/Qwen2.5-7B |
| Groq | api.groq.com | llama-3.3-70b |
| Together AI | api.together.xyz | Llama-3.3-70B |
| OpenRouter | openrouter.ai | llama-3.3-70b |
| Ollama (本地) | localhost:11434 | llama3.1 |
| LM Studio (本地) | localhost:1234 | local-model |
| **Custom** | 自定义 | 自定义 |

> 💡 本地模型（Ollama/LM Studio）不需要 API Key。

### 2. AI 建模

1. 在文本框中描述你想要的模型（中英文均可）
2. 点击 **"Send to AI"**（发送给 AI）
3. AI 会显示思考过程和生成的代码
4. 点击 **"Execute Code"**（执行代码）在场景中创建模型

#### 示例提示词

```
一把中世纪长剑，刃长约80cm，有十字形护手和皮革包裹的握柄
```

```
一个药水瓶，玻璃瓶身里面有发光的蓝色液体，软木塞瓶盖
```

```
一棵橡树，树干有纹理，茂密的树冠，大约3米高
```

```
一套哥特式盔甲的胸甲部分，有铆钉装饰和曲面造型
```

### 3. AI 精修

1. 在 Blender 中选中一个已有的模型
2. 描述你想怎么改进它
3. 点击 **"AI Refine"**（AI 精修）
4. AI 会在原模型基础上修改，不会创建新对象

### 4. 多阶段生成

对于复杂模型，点击 **"Multi-Pass Gen"**（多阶段生成）：
- AI 会自动进行 3 轮生成
- 每轮在前一轮的基础上添加细节
- 最后自动进行后处理

---

## 功能模块

### ⚡ Quick Build（快速构建）

不需要 API，一键生成预设模型：

| 图标 | 名称 | 说明 |
|------|------|------|
| 🧑 | Human Male | 人类男性基础模型 |
| ⚔ | Sword | 长剑 |
| 🛡 | Shield | 盾牌 |
| 💊 | Potion | 药水瓶 |
| 🪑 | Table | 桌子 |
| 💺 | Chair | 椅子 |
| 🏠 | House | 房屋 |
| 🐉 | Dragon | 火龙幼崽 |
| 💎 | Crystal | 水晶簇 |
| 🌳 | Tree | 树木 |
| 🍄 | Mushroom | 蘑菇 |
| 💀 | Skeleton | 骷髅战士 |
| 👑 | Crown | 王冠 |
| 🏛 | Archway | 拱门 |
| 📦 | Chest | 宝箱 |
| 🔥 | Torch | 火把 |

### 🎨 Material Library（材质库）

29 种 PBR 材质预设，涵盖常见表面：

| 分类 | 材质 |
|------|------|
| **金属** | Steel、Gold、Copper、Bronze、Aluminum |
| **塑料** | White、Red、Blue、Green、Black |
| **木材** | Oak、Pine、Dark |
| **玻璃** | Clear、Tinted |
| **橡胶** | Black、White |
| **织物** | Cotton、Silk |
| **石材** | Granite、Marble、Concrete |
| **其他** | Ceramic、Leather(2)、Emissive(3)、Water、Skin |

### 🔧 Modifier Presets（修改器预设）

24 种常用修改器一键应用：Subdivision Surface、Mirror（X/XY/XYZ）、Array、Bevel、Solidify、Triangulate、Decimate、Boolean（Union/Intersect/Difference）、Smooth、Lattice、Shrinkwrap、Cast、Wave、Displace、Screw、Wireframe、Skin。

### 📐 Templates（参数化模板）

8 个可调参数的模板：Chair、Table、Sword、House、Tree、Humanoid、Pillar、Gear。选中模板后调整参数，一键发送给 AI 生成。

### 🦴 Rigging（骨骼绑定）

- **Humanoid** — 24 骨骼人形骨架（脊柱、四肢、手指）
- **Quadruped** — 20 骨骼四足骨架（马、狗、猫等）

### 🗺️ UV Tools（UV 展开）

5 种展开方式：Smart UV、Angle Based、Cube Projection、Cylinder、Sphere。

### 📊 Mesh Analysis（网格分析）

检测：面数、顶点数、非流形边、孤立顶点、N-gon、法线翻转、包围盒尺寸。

### ✅ Quality Check（质检）

自动扫描场景中所有网格对象，报告问题并提供一键修复。

### 🎬 Animation（动画）

- **Walk Cycle** — 行走循环动画
- **Breathing** — 呼吸动画
- **Camera Orbit** — 摄像机环绕动画

### 🌍 Procedural Generation（程序化生成）

- **Terrain** — 参数化地形（大小、细分、高度、种子）
- **Tree** — 程序化树木（树干、树冠参数）
- **Scatter** — 在表面上随机散布对象

### 📦 Batch Operations（批量操作）

- **Batch Rename** — 前缀/后缀/查找替换/序号重命名
- **Batch Export** — FBX/OBJ/glTF/STL 批量导出

### 🎮 Engine Export（引擎导出）

Unity、Unreal Engine、Godot 一键导出预设，自动处理坐标轴和缩放。

### 🗃️ Asset Manager（资产管理）

注册、搜索、分类管理场景中的资产。

### 📸 Version Control（版本控制）

保存场景快照，查看历史版本。

### 🔍 Smart Select（智能选择）

按材质、非流形几何体、孤立元素选择对象。

### 🧹 Cleanup（清理）

删除空对象、孤立网格/材质/图像数据。

---

## 高级功能

### 对话历史

AI 会记住之前的对话内容，可以连续迭代建模：
- "创建一把剑" → AI 生成
- "护手再宽一点" → AI 在上一个结果基础上修改
- "加一个宝石装饰" → 继续迭代

历史会自动压缩以避免超出 token 限制。

### 成本追踪

实时显示 token 用量和费用估算，支持重置计数器。

### 后处理

自动清理所有网格：移除重复顶点、修正法线、删除孤立几何体、确保每个对象都有材质。

---

## 常见问题

**Q: AI 生成的模型质量不好怎么办？**
- 使用更强的模型（GPT-4o、Claude 3.5 Sonnet）
- 用多阶段生成（Multi-Pass Gen）
- 用 AI 精修（AI Refine）逐步改进
- 提示词越具体越好（尺寸、材质、风格）

**Q: 本地模型能用吗？**
- 可以！安装 Ollama 或 LM Studio，选择对应预设即可
- 本地模型质量取决于模型大小，推荐 7B 以上

**Q: 支持 Blender 4.x 吗？**
- 支持。所有 3.x/4.x API 差异已自动处理。

**Q: 代码安全吗？**
- AI 生成的代码在沙箱中执行，不能访问文件系统
- 危险操作会被自动拦截

---

## 许可证

GPL-3.0

---

## 贡献

欢迎 Issue 和 Pull Request！
