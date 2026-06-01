# Dramatica-Flow 项目设计文档

## 文档信息

| 属性 | 内容 |
|------|------|
| 项目名称 | Dramatica-Flow |
| 文档类型 | 项目设计文档 |
| 文档版本 | v1.0 |
| 编写日期 | 2025年1月 |
| 文档作者 | AI Assistant |
| 审核状态 | 初稿 |

---

## 一、项目背景与目标

### 1.1 项目背景

Dramatica-Flow 是一款面向网络文学作者和专业写作者的 **AI 辅助长篇小说创作平台**。该项目源于对现有AI写作工具的深刻反思：传统AI写作工具往往只能逐段生成文本，缺乏全局叙事逻辑，导致生成内容存在因果断裂、角色性格崩塌、前后矛盾等问题。

本项目的核心理念是 **"让AI理解故事，而不是只会写文字"**。系统基于 **Dramatica叙事理论**，将小说创作从感性的艺术创作过程抽象为可量化、可追踪、可审计的工程化流程。

### 1.2 核心问题与解决方案

#### 1.2.1 现有AI写作工具的痛点

| 问题类型 | 具体表现 | Dramatica-Flow的解决方案 |
|---------|---------|------------------------|
| 叙事逻辑缺失 | 逐段生成，缺乏全局因果关联 | **因果链引擎**：强制建模"因→果→决"结构 |
| 角色一致性 | 容易出现OOC（Out-Of-Character） | **信息边界系统**：角色只知道亲眼所见/亲耳所闻 |
| 长篇连贯性 | 前后矛盾频发 | **世界状态快照 + 真相文件**：章节间状态累积 |
| 伏笔管理 | 无系统管理，容易"挖坑不填" | **伏笔生命周期**：埋设→追踪→预警→回收 |
| 质量控制 | 无审计机制 | **三层审计**：规则验证→叙事审计→修订闭环 |
| 多线叙事 | 不支持 | **全局时间轴**：多线程调度、跨线程感知 |

### 1.3 项目目标

Dramatica-Flow 的设计目标包括：

1. **叙事逻辑强一致性**：确保每个事件都源于因果链，杜绝"事件堆砌"式的写作
2. **角色行为可追溯**：通过信息边界系统，确保角色行为符合其性格设定
3. **伏笔管理自动化**：自动追踪伏笔生命周期，超期自动预警
4. **多线叙事支持**：支持主线、支线、并行线、闪回线四种叙事线程
5. **质量审计自动化**：通过三层审计机制，确保生成内容的叙事质量
6. **创作过程可视化**：提供Web UI，实现创作全流程的可视化管理

---

## 二、系统总体架构

### 2.1 架构设计原则

Dramatica-Flow 采用 **分层架构** 设计，遵循以下核心原则：

1. **关注点分离（Separation of Concerns）**：各层职责明确，层间通过定义良好的接口交互
2. **依赖倒置（Dependency Inversion）**：高层模块不依赖低层模块，依赖抽象
3. **单一职责（Single Responsibility）**：每个模块只负责一类功能
4. **开闭原则（Open-Closed）**：对扩展开放，对修改封闭

### 2.2 五层技术架构

```
┌──────────────────────────────────────────────────┐
│                   Web UI 层                       │
│   现代化 SPA · 7 大功能模块 · 时间线泳道图        │
├──────────────────────────────────────────────────┤
│                 REST API 层                       │
│   FastAPI · 50+ 端点 · Pydantic 数据校验          │
├──────────────────────────────────────────────────┤
│               Agent 管线层                        │
│   建筑师 · 写手 · 审计员 · 修订者 · 摘要生成      │
├──────────────────────────────────────────────────┤
│               叙事引擎层                          │
│   因果链 · 伏笔系统 · 情感弧线 · 关系网络         │
│   多线叙事 · 信息边界 · 世界状态                   │
├──────────────────────────────────────────────────┤
│               LLM 抽象层                          │
│   DeepSeek API · Ollama 本地模型 · OpenAI 兼容    │
└──────────────────────────────────────────────────┘
```

### 2.3 模块划分与组件结构

#### 2.3.1 核心模块结构

```
dramatica-flow/
├── core/                           # 核心引擎
│   ├── agents/                     # AI Agent 模块
│   │   └── __init__.py            # 建筑师、写手、审计员、修订者、摘要Agent
│   ├── llm/                        # LLM 抽象层
│   │   └── __init__.py            # Provider工厂、JSON解析、重试机制
│   ├── narrative/                  # 叙事引擎
│   │   └── __init__.py            # 大纲生成、因果链提取
│   ├── state/                      # 状态管理
│   │   └── __init__.py            # 世界状态、真相文件、快照管理
│   ├── types/                       # 数据类型定义
│   │   ├── narrative.py           # 叙事相关类型（角色、地点、事件等）
│   │   └── state.py               # 状态相关类型（关系、伏笔、因果链等）
│   ├── validators/                 # 内容验证器
│   │   └── __init__.py            # 零LLM硬规则检测
│   ├── pipeline.py                 # 五层写作管线
│   ├── server.py                   # FastAPI服务（Web UI后端）
│   └── setup.py                    # 配置加载器
├── cli/                            # 命令行工具
│   └── main.py                     # CLI入口（Typer）
├── templates/                      # 配置模板
├── docs/                           # 文档
├── tests/                          # 测试套件
└── pyproject.toml                  # 项目配置
```

#### 2.3.2 各层职责说明

| 层次 | 模块 | 核心职责 | 关键类/函数 |
|------|------|---------|------------|
| **LLM抽象层** | llm | 多Provider路由、JSON解析、重试机制 | `create_provider()`, `parse_llm_json()`, `with_retry()` |
| **叙事引擎层** | narrative | 大纲生成、因果链提取 | `NarrativeEngine.generate_outline()`, `extract_causal_links()` |
| **Agent管线层** | agents | 建筑师规划、写手创作、审计员审计、修订者修订 | `ArchitectAgent`, `WriterAgent`, `AuditorAgent`, `ReviserAgent`, `SummaryAgent` |
| **状态管理层** | state | 世界状态持久化、真相文件管理、快照回滚 | `StateManager`, `WorldState` |
| **验证层** | validators | 硬规则检测（AI标记词、禁止句式等） | `PostWriteValidator` |
| **REST API层** | server | 50+端点、请求校验、响应格式化 | FastAPI路由 |
| **CLI层** | cli | 命令行交互、状态查询 | Typer命令 |
| **配置层** | setup | JSON配置加载、数据验证 | `SetupLoader`, `load_character()` |

### 2.4 模块间关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI / Web UI                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          REST API (server.py)                            │
│   书籍管理 | 故事配置 | AI创作 | 故事追踪 | 系统设置 | 导出              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
        ┌───────────────────┐ ┌───────────────┐ ┌───────────────┐
        │   SetupLoader     │ │  Pipeline     │ │  StateManager │
        │   (配置加载)       │ │  (写作管线)    │ │  (状态管理)   │
        └───────────────────┘ └───────────────┘ └───────────────┘
                    │               │               │
                    ▼               ▼               ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                         Agents                                │
        │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
        │  │ 建筑师   │  │  写手    │  │  审计员  │  │  修订者  │       │
        │  │ Agent    │  │  Agent   │  │  Agent   │  │  Agent   │       │
        │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
        │  ┌──────────┐                                                       │
        │  │ 摘要Agent│                                                       │
        │  └──────────┘                                                       │
        └───────────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                      LLM 抽象层                                │
        │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
        │  │ DeepSeek    │  │  Ollama     │  │  OpenAI     │            │
        │  │ Provider    │  │  Provider   │  │  Compatible │            │
        │  └─────────────┘  └─────────────┘  └─────────────┘            │
        └───────────────────────────────────────────────────────────────┘
```

---

## 三、核心功能模块设计

### 3.1 五层Agent写作管线

五层Agent写作管线是Dramatica-Flow的核心创新，它将AI写作从简单的文本生成升级为工程化的创作流程。

#### 3.1.1 管线流程

```
快照备份
    ↓
① 建筑师 Agent ── 规划蓝图（因果链上下文 + 前情摘要 + 伏笔状态）
    ↓
② 写手 Agent ── 生成正文 + 写后结算表
    ↓
③ 写后验证器 ── 零 LLM 硬规则检测（字数、禁忌词、格式）
    ↓ error → spot-fix
④ 审计员 Agent ── 叙事质量审计（temperature=0，确保客观）
    ↓ critical → 修订者 Agent → 再审（最多 2 轮闭环）
⑤ 因果链提取 ── 从正文中提取因果关系 → 写入世界状态
    ↓
摘要生成 ── 章节摘要注入真相文件
    ↓
状态结算 ── 位置/情感/关系/伏笔 → world_state.json
```

#### 3.1.2 各Agent详细设计

##### (1) 建筑师Agent (ArchitectAgent)

**职责**：在写作前规划本章的蓝图，包括核心冲突、伏笔推进、情感旅程等。

**输入**：
- 章纲（章节号、标题、摘要、节拍序列）
- 世界状态上下文
- 未闭合伏笔列表
- 前情摘要（最近3章）
- POV角色信息（多线叙事）
- 跨线程上下文（多线叙事）

**输出**：`ArchitectBlueprint` 数据结构，包含：
- `core_conflict`: 本章核心冲突
- `hooks_to_advance`: 需要推进的伏笔列表
- `hooks_to_plant`: 需要埋下的新伏笔
- `emotional_journey`: 情感旅程（start → end）
- `chapter_end_hook`: 章节结尾钩子
- `pace_notes`: 节奏建议
- `pre_write_checklist`: 写前检查清单
- `pov_character_id`: 视角角色ID（多线叙事）
- `thread_id`: 所属线程ID（多线叙事）

**关键代码位置**：[core/agents/__init__.py#L91-193](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py#L91-193)

##### (2) 写手Agent (WriterAgent)

**职责**：根据建筑师蓝图生成章节正文，并在正文末尾输出写后结算表。

**创作铁律**：
1. 只写动作、感知、对话——不替读者下结论
2. 冲突必须源于角色目标与障碍的碰撞
3. 每个场景必须推进叙事 OR 揭示角色
4. 场景结尾状态必须比开始更极端
5. 对话要有潜台词

**输出**：
- `content`: 章节正文
- `settlement`: 写后结算表（PostWriteSettlement）

**结算表数据结构**：
```python
@dataclass
class PostWriteSettlement:
    resource_changes: list[str]           # 资源变化
    new_hooks: list[str]                 # 新开伏笔
    resolved_hooks: list[str]             # 回收伏笔
    relationship_changes: list[str]       # 关系变化
    info_revealed: list[dict]             # 信息揭示
    character_position_changes: list[dict] # 位置变化
    emotional_changes: list[dict]          # 情感变化
```

**关键代码位置**：[core/agents/__init__.py#L242-393](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py#L242-393)

##### (3) 审计员Agent (AuditorAgent)

**职责**：从叙事质量角度审计章节内容，检查因果一致性、角色OOC、伏笔遗漏等问题。

**审计维度**（12个）：
1. OOC（角色行为是否符合性格锁定）
2. 信息边界（角色是否知道了他不应知道的信息）
3. 因果一致性（事件是否有前因，是否靠巧合推进）
4. 情感弧线（是否符合章纲目标）
5. 大纲偏离（是否完成mandatory_tasks）
6. 节奏（快慢场景分配）
7. 伏笔管理（新开/回收是否落地）
8. 去AI味（AI标记词、套话、元叙事）
9. 连续性（角色位置、道具、时间线）
10. 冲突质量（冲突是否源于目标与障碍张力）
11. 结尾钩子（是否有效实现）
12. 跨线程一致性（多线叙事时间线冲突）

**输出**：`AuditReport`，包含：
- `passed`: 是否通过（critical问题为0则通过）
- `issues`: 问题列表（critical/warning/info三级）
- `overall_note`: 整体评价

**关键代码位置**：[core/agents/__init__.py#L459-585](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py#L459-585)

##### (4) 修订者Agent (ReviserAgent)

**职责**：根据审计报告修订章节内容。

**修订模式**：
- `spot-fix`: 只修改问题句子/段落，其余不变
- `rewrite-section`: 重写包含问题的段落
- `polish`: 提升文笔流畅度，不改情节

**关键代码位置**：[core/agents/__init__.py#L614-680](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py#L614-680)

##### (5) 摘要Agent (SummaryAgent)

**职责**：生成章节摘要，注入chapter_summaries.md，为后续章节提供上下文。

**输出数据结构**：
```python
class _SummarySchema(BaseModel):
    chapter_number: int
    title: str
    summary: str                    # 200字以内情节摘要
    key_events: list[str]          # 关键事件
    characters_appeared: list[str] # 出场角色
    state_changes: list[str]       # 世界状态变化
    hook_updates: list[str]        # 伏笔动态
    emotional_note: str             # 情感轨迹一句话
```

**关键代码位置**：[core/agents/__init__.py#L698-764](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py#L698-764)

### 3.2 叙事引擎模块 (NarrativeEngine)

**职责**：生成故事大纲和章节大纲，提取因果链。

#### 3.2.1 故事大纲生成

**输入**：
- 种子事件（激励事件）
- 主角信息
- 世界背景
- 目标章节数
- 题材类型

**输出**：`StoryOutlineSchema`，包含：
- `id`, `title`, `logline`, `genre`
- `sequences`: 序列列表（每个序列约8-15章）
- `emotional_roadmap`: 全书情感路线图

**序列数据结构**：
```python
class SequenceSchema(BaseModel):
    id: str
    number: int
    act: int                        # 属于第几幕（1/2/3）
    summary: str                    # 序列摘要
    narrative_goal: str             # 叙事任务
    dramatic_function: DramaticFunction  # 戏剧功能
    key_events: list[str]           # 关键事件
    estimated_scenes: int           # 预计章节数
    end_hook: str                   # 结尾钩子
```

**关键代码位置**：[core/narrative/__init__.py#L99-217](file:///d:/owned/ai/dramatica-flow/core/narrative/__init__.py#L99-217)

#### 3.2.2 章节大纲生成

**职责**：将序列展开为具体章节的章纲。

**特点**：
- 每批最多生成5章，防止JSON过长被截断
- 自动修正AI输出的非法dramatic_function
- 填充缺失字段

**关键代码位置**：[core/narrative/__init__.py#L220-350](file:///d:/owned/ai/dramatica-flow/core/narrative/__init__.py#L220-350)

#### 3.2.3 因果链提取

**输入**：章节正文

**输出**：因果链节点列表（CausalLinkSchema）

**因果链格式**：
```
因为 [cause] → 发生了 [event] → 导致 [consequence]
角色 [character] 决定 [decision]
触发下游事件 [triggered_events]
```

**关键代码位置**：[core/narrative/__init__.py#L353-395](file:///d:/owned/ai/dramatica-flow/core/narrative/__init__.py#L353-395)

### 3.3 状态管理模块 (StateManager)

**职责**：管理世界状态的持久化，包括真相文件、快照、章节正文等。

#### 3.3.1 目录结构

```
books/{book_id}/
    state/
        config.json              # 书籍配置
        world_state.json         # 世界状态（JSON）
        current_state.md         # 当前世界状态（Markdown）
        story_bible.md           # 世界观圣经
        chapter_summaries.md     # 章节摘要
        pending_hooks.md         # 未闭合伏笔
        emotional_arcs.md        # 情感弧线
        character_matrix.md      # 角色交互矩阵
        causal_chain.md          # 因果链日志
        thread_status.md         # 叙事线程状态
        setup_state.json         # 角色/世界/事件配置
        outline.json             # 故事大纲
        chapter_outlines.json    # 全书章纲
    snapshots/
        ch0001.json             # 章节快照
        ...
    chapters/
        ch0001_draft.md         # 草稿
        ch0001_final.md         # 最终稿
        ...
```

#### 3.3.2 真相文件系统

系统维护8个真相文件，构成"单一真相源"：

| 文件 | 用途 | 关键数据 |
|------|------|---------|
| `current_state.md` | 当前世界状态 | 角色位置、情感、关系、伏笔 |
| `story_bible.md` | 世界观圣经 | 地点、势力、规则、事件 |
| `chapter_summaries.md` | 章节摘要 | 每章情节、关键事件、状态变化 |
| `pending_hooks.md` | 伏笔追踪 | 伏笔ID、类型、植入章、预计回收 |
| `emotional_arcs.md` | 情感弧线 | 角色情绪变化轨迹 |
| `character_matrix.md` | 信息边界 | 角色知道什么、何时知道 |
| `causal_chain.md` | 因果链 | 事件因果关系 |
| `thread_status.md` | 线程状态 | 叙事线程进度、掉线预警 |

#### 3.3.3 快照与回滚

**快照时机**：每章写作前自动创建快照

**快照内容**：
- world_state.json
- 所有真相文件内容
- 创建时间戳

**回滚机制**：可回滚到任意章节的快照状态

**关键代码位置**：[core/state/__init__.py#L565-592](file:///d:/owned/ai/dramatica-flow/core/state/__init__.py#L565-592)

### 3.4 验证器模块 (PostWriteValidator)

**职责**：零LLM成本的硬规则检测。

#### 3.4.1 规则清单

| 规则ID | 规则描述 | 严重度 | 检测方式 |
|--------|---------|--------|---------|
| `AI_MARKER_DENSITY` | AI标记词密度（每3000字≤1次） | warning | 正则匹配 |
| `FORBIDDEN_PHRASE` | 禁止句式 | error | 字符串包含 |
| `META_NARRATIVE` | 元叙事/作者说教 | warning | 正则匹配 |
| `REPORT_STYLE` | 报告式语言 | warning | 正则匹配 |
| `COLLECTIVE_REACTION` | 集体反应套话 | warning | 正则匹配 |
| `CONSECUTIVE_LE` | 连续6句以上含"了"字 | warning | 句子分割统计 |
| `LONG_PARAGRAPH` | 段落超过300字 | warning | 段落长度统计 |
| `WORD_COUNT_DEVIATION` | 字数偏差超过20% | warning | 数值比较 |
| `CUSTOM_FORBIDDEN_WORD` | 自定义禁止词 | warning | 正则匹配 |

#### 3.4.2 AI标记词清单

```python
AI_MARKER_WORDS = [
    "仿佛", "忽然", "竟然", "不禁", "宛如",
    "猛地", "顿时", "霎时", "不由得",
]
```

**关键代码位置**：[core/validators/__init__.py](file:///d:/owned/ai/dramatica-flow/core/validators/__init__.py)

### 3.5 LLM抽象层

**职责**：统一多Provider接口，提供JSON解析和重试机制。

#### 3.5.1 Provider架构

```
LLMProvider (抽象基类)
    │
    ├── DeepSeekProvider
    │   └── 使用OpenAI SDK，兼容接口
    │
    └── OllamaProvider
        └── 本地模型，OpenAI兼容接口
```

#### 3.5.2 核心功能

1. **多Provider路由**：通过环境变量或显式配置选择Provider
2. **JSON安全解析**：支持```json```包裹、截断修复、schema校验
3. **重试机制**：网络错误和解析失败自动重试（默认3次）

**关键代码位置**：[core/llm/__init__.py](file:///d:/owned/ai/dramatica-flow/core/llm/__init__.py)

### 3.6 配置加载模块 (SetupLoader)

**职责**：从JSON文件加载角色、世界、事件配置，生成story_bible.md。

#### 3.6.1 配置模板

- `characters.json`: 角色定义
- `world.json`: 地点、势力、世界规则
- `events.json`: 种子事件

#### 3.6.2 角色数据结构

```python
@dataclass
class Character:
    id: str
    name: str
    need: CharacterNeed           # 双层需求
        ├── external: str       # 外部目标
        └── internal: str       # 内在渴望
    obstacles: list[Obstacle]   # 障碍列表
    worldview: CharacterWorldview # 世界观
        ├── power: Literal["seeks", "rejects", "accepts"]
        ├── trust: Literal["trusting", "suspicious", "selective"]
        └── coping: Literal["fight", "flee", "freeze", "fawn"]
    arc: Literal["positive", "negative", "flat", "corrupt"]
    profile: str                # 角色简介
    behavior_lock: list[str]    # 性格锁定（绝对不会做的事）
```

**关键代码位置**：[core/setup.py](file:///d:/owned/ai/dramatica-flow/core/setup.py)

---

## 四、数据模型设计

### 4.1 核心实体关系图

```
┌─────────────────┐     1:n      ┌─────────────────┐
│   BookConfig    │◄────────────│    ProjectState  │
│   书籍配置       │             │   完整项目状态    │
└─────────────────┘             └─────────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
           ▼                            ▼                            ▼
┌─────────────────┐     1:n     ┌─────────────────┐     1:n     ┌─────────────────┐
│    Character    │◄────────────│    Location     │◄────────────│     Faction     │
│     角色         │             │     地点        │             │     势力        │
└─────────────────┘             └─────────────────┘             └─────────────────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │   WorldRule     │
                              │   世界规则       │
                              └─────────────────┘

┌─────────────────┐     1:n      ┌─────────────────┐     1:n      ┌─────────────────┐
│  NarrativeThread │◄────────────│   WorldState    │◄────────────│   TimelineEvent  │
│    叙事线程       │             │    世界状态      │             │    时间轴事件    │
└─────────────────┘             └─────────────────┘             └─────────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
           ▼                            ▼                            ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ RelationshipRecord│   │      Hook       │     │    CausalLink    │
│      关系记录     │     │      伏笔       │     │      因果链      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
           │
           ▼
┌─────────────────┐     ┌─────────────────┐
│  KnownInfoRecord │     │ EmotionalSnapshot│
│    信息边界记录   │     │    情感快照      │
└─────────────────┘     └─────────────────┘
```

### 4.2 核心数据模型

#### 4.2.1 叙事相关类型

**位置**：[core/types/narrative.py](file:///d:/owned/ai/dramatica-flow/core/types/narrative.py)

```python
# 戏剧功能枚举
class DramaticFunction(str, Enum):
    SETUP        = "setup"        # 建立
    INCITING     = "inciting"     # 激励事件
    TURNING      = "turning"      # 转折点
    MIDPOINT     = "midpoint"     # 中点
    CRISIS       = "crisis"       # 危机
    CLIMAX       = "climax"       # 高潮
    REVEAL       = "reveal"       # 揭示
    DECISION     = "decision"     # 决策
    CONSEQUENCE  = "consequence"   # 后果
    TRANSITION   = "transition"    # 过渡

# 角色职能枚举（Dramatica Roles）
class CharacterRole(str, Enum):
    PROTAGONIST   = "protagonist"    # 主角
    ANTAGONIST    = "antagonist"     # 反派
    IMPACT        = "impact"         # 冲击者
    GUARDIAN      = "guardian"       # 守护者
    CONTAGONIST   = "contagonist"    # 阻碍者
    SIDEKICK      = "sidekick"       # 伙伴
    SKEPTIC       = "skeptic"        # 怀疑者
    REASON        = "reason"         # 理性者
    EMOTION       = "emotion"        # 感性者
    LOVE_INTEREST = "love_interest"  # 恋人
    MENTOR        = "mentor"         # 导师
    SUPPORTING    = "supporting"     # 配角

# 叙事线程类型
class ThreadType(str, Enum):
    MAIN = "main"           # 主线
    SUBPLOT = "subplot"     # 支线
    PARALLEL = "parallel"   # 并行线
    FLASHBACK = "flashback" # 闪回线

@dataclass
class NarrativeThread:
    id: str
    name: str
    type: ThreadType = ThreadType.MAIN
    pov_character_id: str = ""
    character_ids: list[str] = field(default_factory=list)
    goal: str = ""
    growth_arc: str = ""
    start_chapter: int = 1
    last_active_chapter: int = 0
    weight: float = 1.0
    status: Literal["active", "dormant", "resolved", "merged"] = "active"
    merge_target_thread: str | None = None
    hook_score: int = 80
    merge_chapter: int | None = None
    end_hook: str = ""
```

#### 4.2.2 状态相关类型

**位置**：[core/types/state.py](file:///d:/owned/ai/dramatica-flow/core/types/state.py)

```python
# 伏笔类型
class HookType(str, Enum):
    FORESHADOW = "foreshadow"  # 伏笔
    PROMISE    = "promise"     # 承诺
    MYSTERY    = "mystery"     # 悬念
    CONFLICT   = "conflict"    # 冲突

# 伏笔状态
class HookStatus(str, Enum):
    OPEN      = "open"
    RESOLVED  = "resolved"
    ABANDONED = "abandoned"

@dataclass
class Hook:
    id: str
    type: HookType
    description: str
    planted_in_chapter: int
    expected_resolution_range: tuple[int, int]
    status: HookStatus = HookStatus.OPEN
    resolved_in_chapter: int | None = None

@dataclass
class CausalLink:
    """因果链节点"""
    id: str
    chapter: int
    cause: str                              # 触发原因
    event: str                              # 发生了什么
    consequence: str                        # 直接后果
    affected_decisions: list[AffectedDecision] = field(default_factory=list)
    triggered_events: list[str] = field(default_factory=list)
    thread_id: str = "thread_main"
    source_thread_id: str = ""

@dataclass
class WorldState:
    book_id: str
    current_chapter: int = 0
    character_positions: dict[str, str] = field(default_factory=dict)
    relationships: list[RelationshipRecord] = field(default_factory=list)
    known_info: list[KnownInfoRecord] = field(default_factory=list)
    emotional_snapshots: list[EmotionalSnapshot] = field(default_factory=list)
    pending_hooks: list[Hook] = field(default_factory=list)
    causal_chain: list[CausalLink] = field(default_factory=list)
    threads: list[NarrativeThread] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
```

### 4.3 数据存储方案

#### 4.3.1 存储策略

| 数据类型 | 存储格式 | 存储位置 | 说明 |
|---------|---------|---------|------|
| 书籍配置 | JSON | `state/config.json` | 结构化数据 |
| 世界状态 | JSON | `state/world_state.json` | 结构化数据，内存友好 |
| 真相文件 | Markdown | `state/*.md` | 人类可读，Agent可读 |
| 章节正文 | Markdown | `chapters/chXXXX_final.md` | 最终稿 |
| 快照 | JSON | `snapshots/chXXXX.json` | 完整状态备份 |
| 设置模板 | JSON | `setup/*.json` | 用户配置模板 |

#### 4.3.2 JSON与Markdown的权衡

**选择JSON的理由**：
- 结构化数据（WorldState、Config）便于程序读写
- Pydantic校验保证数据完整性
- 序列化/反序列化高效

**选择Markdown的理由**：
- 真相文件需要Agent读取，Markdown是人类和AI都易读的格式
- 便于人类直接查看和编辑
- Markdown的表格格式适合列表类数据（伏笔、关系）

---

## 五、技术选型与架构决策

### 5.1 技术栈概览

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| **语言** | Python 3.11+ | 类型系统完善、生态丰富、AI领域首选 |
| **Web框架** | FastAPI | 高性能、自动文档、类型安全 |
| **LLM接口** | OpenAI SDK | 兼容DeepSeek、Ollama等多种Provider |
| **数据校验** | Pydantic v2 | 强大的类型校验和序列化 |
| **CLI框架** | Typer + Rich | 优雅的命令行界面 |
| **ASGI服务器** | Uvicorn | 异步高性能 |
| **测试框架** | pytest + pytest-asyncio | 成熟的异步测试支持 |

### 5.2 架构决策记录

#### ADR-001: 采用五层Agent管线而非单一LLM调用

**背景**：传统AI写作工具使用单一LLM调用生成文本，缺乏质量控制和状态管理。

**决策**：采用五层Agent管线，每层职责单一，通过状态管理器传递上下文。

**后果**：
- ✅ 质量可控，每层都可独立审计
- ✅ 状态管理清晰，因果链可追溯
- ❌ 延迟增加（多次LLM调用）
- ❌ 成本增加（多次LLM调用）

**替代方案考虑**：
- 单一大模型+few-shot：简单但质量不可控
- 强化学习微调：效果可能更好但成本高

#### ADR-002: 真相文件采用Markdown格式

**背景**：Agent需要读取大量上下文信息（世界状态、历史摘要等）。

**决策**：真相文件采用Markdown格式存储。

**后果**：
- ✅ Agent易于理解和生成
- ✅ 人类可读可编辑
- ✅ Markdown表格适合列表数据
- ❌ 解析和更新需要文本处理

#### ADR-003: 多Provider支持（DeepSeek/Ollama）

**背景**：用户可能有不同的LLM使用场景（在线API vs 本地模型）。

**决策**：通过Provider抽象层支持多Provider，用户可通过.env配置切换。

**后果**：
- ✅ 用户灵活性高
- ✅ 支持离线使用（Ollama）
- ✅ 成本可控（可使用免费模型）
- ❌ 需要处理Provider间的差异

### 5.3 Dramatica叙事理论集成

系统内置完整的Dramatica角色职能体系和戏剧功能节拍：

#### 5.3.1 角色职能体系

| 职能 | 英文 | 叙事作用 |
|------|------|---------|
| 主角 | Protagonist | 推动故事前进的核心力量 |
| 反派 | Antagonist | 与主角目标对立的对抗者 |
| 冲击者 | Impact Character | 改变主角认知的关键人物 |
| 守护者 | Guardian | 导师/引导者 |
| 阻碍者 | Contagonist | 表面帮助实则拖延 |
| 伙伴 | Sidekick | 忠诚的支持者 |

#### 5.3.2 戏剧功能节拍（11种）

1. **SETUP** - 建立角色/世界/规则
2. **INCITING** - 激励事件，打破平衡
3. **TURNING** - 转折点，方向改变
4. **MIDPOINT** - 中点，承诺升级或假胜利
5. **CRISIS** - 危机，最低点
6. **CLIMAX** - 高潮，终极对决
7. **REVEAL** - 信息揭示，改变认知
8. **DECISION** - 角色做出关键选择
9. **CONSEQUENCE** - 行动的后果落地
10. **TRANSITION** - 过渡，节奏调节

---

## 六、关键业务流程

### 6.1 创作流程总览

```
① 创建书籍        df book --title "我的小说" --genre "玄幻" --chapters 100
       ↓
② 初始化配置      df setup init-templates <book_id>
       ↓
③ 编辑配置        手动编辑 characters.json, world.json, events.json
       ↓
④ 加载配置        df setup load <book_id>
       ↓
⑤ 生成大纲        AI基于Dramatica理论自动生成三幕结构大纲
       ↓
⑥ 逐章创作        AI写作 → 规则验证 → 叙事审计 → 修订闭环
       ↓
⑦ 故事追踪        实时监控因果链、情感弧线、伏笔状态
       ↓
⑧ 导出成品        一键导出为 Markdown / 全文审阅
```

### 6.2 单章写作管线执行流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         单章写作管线                                     │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: 快照备份
│  创建当前状态的快照，支持回滚
▼

Step 2: 建筑师规划
│  输入：章纲、世界上下文、前情摘要、伏笔状态
│  输出：ArchitectBlueprint（核心冲突、情感旅程、伏笔计划等）
▼

Step 3: 写手创作
│  输入：蓝图、节拍序列、世界状态、前情摘要
│  输出：章节正文 + PostWriteSettlement（结算表）
▼

Step 4: 写后验证（零LLM）
│  检测：AI标记词密度、禁止句式、元叙事、字数偏差
│  结果：通过 → 继续；未通过 → spot-fix修订
▼

Step 5: 审计员审计
│  输入：正文、蓝图表、结算表、真相文件
│  输出：AuditReport（critical/warning/info问题列表）
│  结果：通过（critical=0）→ 继续；未通过 → Step 6
▼

Step 6: 修订者修订（最多2轮）
│  输入：问题列表
│  输出：修订后正文
│  → 返回Step 5重新审计
▼

Step 7: 保存最终稿
│  保存到 chapters/chXXXX_final.md
▼

Step 8: 因果链提取
│  从正文中提取因果关系
│  写入因果链真相文件和世界状态
▼

Step 9: 摘要生成
│  生成章节摘要
│  追加到 chapter_summaries.md
▼

Step 10: 状态结算
│  应用结算表：位置变化、情感变化、关系变化、伏笔更新
│  更新时间轴和线程状态
│  更新 current_state.md
▼

Step 11: 完成
```

### 6.3 伏笔生命周期管理

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         伏笔生命周期                                     │
└─────────────────────────────────────────────────────────────────────────┘

埋设阶段
│  来源1：写手Agent的结算表（new_hooks字段）
│  来源2：建筑师Agent的蓝图（hooks_to_plant字段）
│  信息：伏笔描述、植入章节、预计回收范围
│  状态：OPEN
▼

追踪阶段
│  每章审计时检查：伏笔是否被推进？
│  逾期预警：超过expected_resolution_range[1]仍未回收
▼

回收阶段
│  来源：写手Agent的结算表（resolved_hooks字段）
│  状态变更：OPEN → RESOLVED
│  记录：resolved_in_chapter
▼

关闭阶段
│  超期未回收可标记为：ABANDONED
│  或人工判断：伏笔是否有意义？
```

### 6.4 多线叙事调度

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         多线叙事架构                                    │
└─────────────────────────────────────────────────────────────────────────┘

线程类型：
├── 主线（MAIN）    weight=1.0    篇幅权重最高
├── 支线（SUBPLOT） weight=0.3-0.7  篇幅权重较低
├── 并行线（PARALLEL）weight=0.5-1.0  与主线并行，最终汇合
└── 闪回线（FLASHBACK）weight=0.3     用于补充背景

调度策略：
│  1. 根据线程weight调整字数分配
│  2. 跨线程感知：建筑师/写手获知其他线程状态
│  3. 跨线程审计：检测不同线程的时间线冲突
│  4. 掉线预警：线程超过5章未活跃自动提醒
▼

时间轴管理：
│  记录：谁（character）在何时（physical_time）
│        在何地（location）做了什么事（action）
│  用途：跨线程一致性检测、角色活动追踪
```

---

## 七、系统交互逻辑

### 7.1 REST API架构

系统提供50+ REST API端点，覆盖完整创作流程。

#### 7.1.1 API分组

| 分组 | 端点数 | 说明 |
|------|--------|------|
| 书籍管理 | 4 | 创建、查询、删除书籍 |
| 故事配置 | 5 | 初始化、加载、更新配置 |
| AI创作核心 | 10 | 大纲生成、章纲生成、内容生成、重写 |
| 故事追踪 | 6 | 因果链、情感弧线、伏笔、关系、线程、时间轴 |
| 故事分析 | 4 | 从小说提取、三层审计 |
| 系统设置 | 3 | 获取/更新配置、状态检测 |
| 执行动作 | 4 | 写作管线、审计、修订、导出 |

#### 7.1.2 核心API端点

**AI生成相关**：
```
POST /api/books/{id}/ai-generate/outline           # 生成故事大纲
POST /api/books/{id}/ai-generate/chapter-outlines  # 生成章纲
POST /api/books/{id}/ai-generate/chapter-content    # 生成章节内容
POST /api/books/{id}/continue-writing               # 续写章纲（联动大纲）
```

**追踪相关**：
```
GET /api/books/{id}/causal-chain          # 获取因果链
GET /api/books/{id}/emotional-arcs        # 获取情感弧线
GET /api/books/{id}/hooks                  # 获取伏笔列表
GET /api/books/{id}/relationships         # 获取关系网络
GET /api/books/{id}/threads               # 获取叙事线程
GET /api/books/{id}/timeline              # 获取全局时间轴
```

**执行动作**：
```
POST /api/action/write     # 执行写作管线
POST /api/action/audit     # 执行审计
POST /api/action/revise    # 执行修订
POST /api/action/export    # 导出全书
```

**关键代码位置**：[core/server.py](file:///d:/owned/ai/dramatica-flow/core/server.py)

### 7.2 Web UI交互

Web UI提供7大功能模块，通过Fetch API调用后端REST API。

#### 7.2.1 模块结构

| 模块 | 路由 | 功能 |
|------|------|------|
| 总览面板 | `/` | 书籍进度、章节统计、伏笔状态一览 |
| 故事配置 | `/` | 角色/势力/地点/世界规则的创建与编辑 |
| 大纲管理 | `/` | AI生成故事大纲、按幕筛选、序列规划 |
| 章节创作 | `/` | AI写作、人工修订、审计结果查看 |
| 故事追踪 | `/` | 因果链、情感弧线、伏笔、关系网络可视化 |
| 时间线 | `/timeline` | 多线叙事泳道图、角色活动追踪 |
| 系统设置 | `/` | LLM后端切换、模型配置 |

#### 7.2.2 关键前端交互流程

**1. 创建书籍流程**：
```
用户点击"创建书籍"
  → 弹出表单（标题、题材、目标章节数、每章字数）
  → POST /api/books
  → 创建state目录和config.json
  → 跳转到故事配置页面
```

**2. AI生成章节流程**：
```
用户点击"生成章节"
  → GET /api/books/{id}/chapter-outlines 获取当前章纲
  → POST /api/action/write
  → 后端执行五层管线
  → SSE流式返回进度
  → 前端实时更新状态
  → 完成时显示审计结果
```

**3. 时间线交互**：
```
GET /api/books/{id}/timeline
  → 返回全局时间轴数据
  → 泳道图渲染
  → 支持拖动滑块聚焦章节区间
  → 支持按事件类型筛选
```

### 7.3 CLI交互

CLI通过Typer框架提供命令行界面。

#### 7.3.1 命令结构

```
df --help

Commands:
  df init <name>                        # 初始化项目
  df book --title "我的小说" --genre "玄幻" --chapters 100  # 创建书籍
  df setup init-templates <book_id>     # 初始化配置模板
  df setup load <book_id>               # 加载配置
  df write <book_id>                    # AI写下一章
  df write <book_id> --count 5          # 连续写5章
  df audit <book_id> <chapter>           # 审计章节
  df revise <book_id> <chapter>         # 修订章节
  df status <book_id>                    # 查看书籍状态
  df export <book_id>                    # 导出全书
  df threads list <book_id>              # 查看叙事线程
  df threads create <book_id>            # 创建线程
  df doctor                              # 诊断配置问题
```

**关键代码位置**：[cli/main.py](file:///d:/owned/ai/dramatica-flow/cli/main.py)

---

## 八、潜在技术难点与解决方案

### 8.1 LLM输出不稳定性

#### 难点描述
LLM的输出具有不确定性，可能产生：
- JSON格式错误（截断、缺字段）
- 非法枚举值（如`"twist"`而非`"turning"`）
- 不符合schema的结构

#### 解决方案

**1. JSON解析容错**
```python
# core/llm/__init__.py
def parse_llm_json(raw: str, schema: type[T]) -> T:
    # 1. 剥离 ```json ... ``` 包裹
    # 2. 尝试修复截断的JSON（补全括号）
    # 3. Pydantic schema校验
    # 4. 失败时抛出LLMParseError，触发重试
```

**2. 枚举值别名映射**
```python
# dramatic_function 通用别名映射
_DF_FALLBACK_MAP = {
    "twist": "turning",
    "turn": "turning",
    "hook": "inciting",
    "conflict": "crisis",
    ...
}

def _fix_df(val: str) -> str:
    """将AI输出的dramatic_function修正为合法枚举值"""
```

**3. 自动修复patch_fn**
```python
def _patch_outline(data: dict) -> dict:
    """修复大纲中常见的AI输出问题"""
    for seq in data.get("sequences", []):
        # 补narrative_goal
        if not seq.get("narrative_goal"):
            seq["narrative_goal"] = seq.get("summary", "推进剧情")
        # 修正dramatic_function
        if seq.get("dramatic_function") not in _VALID_DF:
            seq["dramatic_function"] = _fix_df(seq["dramatic_function"])
        # estimated_scenes至少为1
        if seq.get("estimated_scenes", 0) < 1:
            seq["estimated_scenes"] = 1
    return data
```

### 8.2 长上下文导致的Token溢出

#### 难点描述
长篇小说创作需要大量上下文（世界状态、历史摘要、因果链等），可能超出LLM的context窗口。

#### 解决方案

**1. 上下文截断策略**
```python
# 只取最近3章摘要
lines = prior_summaries.strip().split("\n## ")
recent = lines[-3:] if len(lines) > 3 else lines

# 正文超长时截断（审计时）
if len(chapter_content) > 6000:
    content_for_audit = chapter_content[:3000] + "\n\n...[中间省略]...\n\n" + chapter_content[-2000:]
```

**2. 分批生成**
```python
# 章纲分批生成，每批最多5章
BATCH_SIZE = 5
for batch_start in range(0, n_chapters, BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE, n_chapters)
    # 调用LLM生成一批章纲
```

**3. 真相文件选择性读取**
```python
# 只读取必要的真相文件
world_context = self.sm.read_truth_bundle([
    TruthFileKey.CURRENT_STATE,
    TruthFileKey.CHARACTER_MATRIX,
])
```

### 8.3 多线叙事的一致性维护

#### 难点描述
多线叙事时，不同线程的角色位置、时间线、因果关系需要保持一致。

#### 解决方案

**1. 跨线程上下文注入**
```python
# 建筑师/写手获得其他线程状态
thread_context = self._build_thread_context(ws, thread_id, ch)

# 审计员获得跨线程一致性参照
cross_thread_audit_ctx = self._build_cross_thread_audit_context(...)
```

**2. 时间轴记录**
```python
# 每章结束后记录时间轴事件
self._record_timeline_events(ch, writer_output, blueprint, thread_id, ws)

# 用于跨线程冲突检测
```

**3. 掉线预警机制**
```python
def dormant_threads(self, current_chapter: int, threshold: int = 5) -> list[NarrativeThread]:
    """掉线预警：超过threshold章未活跃的线程"""
    return [
        t for t in self.get_active_threads()
        if current_chapter - t.last_active_chapter >= threshold
    ]
```

### 8.4 角色OOC（Out-Of-Character）检测

#### 难点描述
LLM可能在写作时不自觉地让角色做出与其性格设定不符的行为。

#### 解决方案

**1. 信息边界系统**
```python
@dataclass
class KnownInfoRecord:
    """角色只知道亲眼见过/亲耳听到的信息"""
    character_id: str
    info_key: str
    content: str
    learned_in_chapter: int
    source: Literal["witnessed", "hearsay", "deduced", "document"]
```

**2. 性格锁定字段**
```python
@dataclass
class Character:
    behavior_lock: list[str]  # 绝对不会做的事（性格锁定）
```

**3. 审计维度覆盖**
```
OOC（角色行为是否符合性格锁定，性格锁定的事绝对不能做）
信息边界（角色是否知道了他不应知道的信息，信息获取是否有合理来源）
```

### 8.5 伏笔管理的逾期问题

#### 难点描述
长篇创作中，伏笔数量众多，容易出现"挖坑不填"或遗忘回收时机的问题。

#### 解决方案

**1. 自动追踪与预警**
```python
@dataclass
class Hook:
    expected_resolution_range: tuple[int, int]  # 预计回收章节范围
    status: HookStatus
    resolved_in_chapter: int | None

def overdue_hooks(self, current_chapter: int) -> list[Hook]:
    """超过预期回收章节还未回收的伏笔"""
    return [
        h for h in self.open_hooks()
        if current_chapter > h.expected_resolution_range[1]
    ]
```

**2. 伏笔状态可视化**
```
# pending_hooks.md 表格格式
| ID | 类型 | 描述 | 植入章 | 预计回收 | 状态 |
|---|---|---|---|---|---|
| hook_xxx | foreshadow | 玉佩发热之谜 | Ch.3 | 10-20 | ⚠️ 逾期！ |
```

**3. 建筑师伏笔计划**
```python
# 建筑师输出中包含伏笔推进计划
hooks_to_advance: list[str]   # 需要推进的伏笔ID
hooks_to_plant: list[str]     # 需要埋下的新伏笔
```

---

## 九、可扩展性与维护性设计

### 9.1 模块化架构

#### 9.1.1 插件化Agent

当前系统支持自定义Agent，未来可扩展：

```python
# 预留的扩展点
class CustomAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
    
    def run(self, context: dict) -> Any:
        # 自定义处理逻辑
        pass

# 注册到管线
pipeline = WritingPipeline(
    ...
    custom_agents=[CustomAgent(llm)],
)
```

#### 9.1.2 Provider可扩展

添加新的LLM Provider只需：

```python
class CustomProvider(LLMProvider):
    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        # 实现自定义Provider
        pass
    
    def stream(self, messages, on_chunk):
        # 实现流式输出
        pass

# 在create_provider中注册
def create_provider(config=None, provider_type=None) -> LLMProvider:
    if provider_type == "custom":
        return CustomProvider(config)
    # ... 其他Provider
```

### 9.2 配置驱动

#### 9.2.1 环境变量配置

所有关键配置通过`.env`文件管理：

```env
# LLM配置
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Ollama配置（可选）
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1

# 系统配置
DEFAULT_TEMPERATURE=0.7
MAX_TOKENS=8192
```

#### 9.2.2 项目级配置

每本书的配置存储在`state/config.json`：

```json
{
  "id": "my_novel",
  "title": "我的小说",
  "genre": "玄幻",
  "target_chapters": 100,
  "target_words_per_chapter": 4000,
  "custom_forbidden_words": ["敏感词1", "敏感词2"],
  "style_guide": "文风要求..."
}
```

### 9.3 测试覆盖

#### 9.3.1 测试结构

```
tests/
├── __init__.py
├── test_integration.py      # 集成测试
├── test_llm.py             # LLM模块测试
├── test_server.py          # API测试
└── test_threads.py         # 线程管理测试
```

#### 9.3.2 测试策略

- **单元测试**：每个模块独立测试
- **集成测试**：测试完整的写作管线流程
- **Mock测试**：LLM调用使用mock，避免实际API调用

### 9.4 代码质量保证

#### 9.4.1 类型注解

全程使用Python类型注解，配合mypy严格模式：

```python
def parse_llm_json(
    raw: str,
    schema: type[T],
    context: str = "",
    patch_fn: Callable[[dict], dict] | None = None,
) -> T:
    ...
```

#### 9.4.2 代码格式化

使用ruff进行代码格式化：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

### 9.5 文档与注释

#### 9.5.1 文档字符串

核心模块均有详细文档字符串：

```python
class StateManager:
    """
    状态管理器
    文件驱动的单一真相源 + 快照回滚
    
    目录结构：
        books/{book_id}/
            state/
                config.json
                world_state.json
                current_state.md
                ...
    """
```

#### 9.5.2 架构决策记录

重要架构决策记录在代码注释中：

```python
# ADR-001: 采用五层Agent管线而非单一LLM调用
# 背景：传统AI写作工具使用单一LLM调用生成文本，缺乏质量控制
# 决策：采用五层Agent管线，每层职责单一
```

---

## 十、总结与展望

### 10.1 项目创新点

Dramatica-Flow 的核心创新包括：

1. **叙事理论驱动**：首次将完整的Dramatica叙事理论工程化，实现"让AI理解故事结构"
2. **因果链引擎**：强制建模每个事件的因果关系，确保叙事有机性
3. **五层Agent管线**：将AI写作工程化，每层都可审计、可控制
4. **多线叙事支持**：支持主线、支线、并行线、闪回线的统一调度
5. **信息边界系统**：通过角色"知识库"防止OOC和信息越界
6. **伏笔生命周期管理**：自动化追踪、预警、回收伏笔

### 10.2 技术亮点

1. **LLM抽象层设计**：通过Provider模式支持多Provider，JSON解析容错机制完善
2. **状态持久化策略**：JSON+Markdown的混合存储，兼顾程序友好和人类可读
3. **快照回滚机制**：支持任意章节状态回滚，保证创作过程可追溯
4. **零LLM验证器**：通过硬规则检测降低AI成本
5. **Web UI + CLI双入口**：满足不同用户习惯

### 10.3 未来展望

1. **协作功能**：支持多人协作创作
2. **版本控制**：引入git-like的章节版本管理
3. **实时预览**：网页端实时预览写作效果
4. **分析增强**：提供更多创作分析报告（节奏图、角色出场统计等）
5. **模型微调**：针对小说写作场景微调专属模型
6. **多语言支持**：扩展支持英文、日文等语言的小说创作

---

## 附录

### 附录A：文件路径速查

| 功能 | 文件路径 |
|------|---------|
| Agent实现 | [core/agents/__init__.py](file:///d:/owned/ai/dramatica-flow/core/agents/__init__.py) |
| LLM抽象 | [core/llm/__init__.py](file:///d:/owned/ai/dramatica-flow/core/llm/__init__.py) |
| 叙事引擎 | [core/narrative/__init__.py](file:///d:/owned/ai/dramatica-flow/core/narrative/__init__.py) |
| 状态管理 | [core/state/__init__.py](file:///d:/owned/ai/dramatica-flow/core/state/__init__.py) |
| 验证器 | [core/validators/__init__.py](file:///d:/owned/ai/dramatica-flow/core/validators/__init__.py) |
| 写作管线 | [core/pipeline.py](file:///d:/owned/ai/dramatica-flow/core/pipeline.py) |
| REST API | [core/server.py](file:///d:/owned/ai/dramatica-flow/core/server.py) |
| CLI | [cli/main.py](file:///d:/owned/ai/dramatica-flow/cli/main.py) |
| 类型定义 | [core/types/narrative.py](file:///d:/owned/ai/dramatica-flow/core/types/narrative.py), [core/types/state.py](file:///d:/owned/ai/dramatica-flow/core/types/state.py) |
| 配置加载 | [core/setup.py](file:///d:/owned/ai/dramatica-flow/core/setup.py) |

### 附录B：环境变量参考

```env
# 必需
LLM_PROVIDER=deepseek|ollama
DEEPSEEK_API_KEY=sk-xxx

# 可选（DeepSeek）
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 可选（Ollama）
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1

# 系统
DEFAULT_TEMPERATURE=0.7
MAX_TOKENS=8192
AUDITOR_MODEL=  # 审计专用模型（可选）
```

### 附录C：快速命令参考

```bash
# 初始化项目
df init my_project

# 创建书籍
df book --title "我的小说" --genre "玄幻" --chapters 100

# 初始化配置模板
df setup init-templates my_novel

# 加载配置
df setup load my_novel

# 写作（连续写5章）
df write my_novel --count 5

# 查看状态
df status my_novel

# 审计章节
df audit my_novel 5

# 导出全书
df export my_novel --output my_novel.md

# 诊断配置
df doctor
```

---

*文档结束*
