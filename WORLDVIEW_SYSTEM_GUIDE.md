# 世界观系统核心概念指导文档

---

## 目录

1. [角色 (Character)](#1-角色-character)
2. [世界 (World)](#2-世界-world)
3. [事件 (StoryEvent)](#3-事件-storyevent)
4. [线程 (NarrativeThread)](#4-线程-narrativethread)
5. [角色定位详解](#5-角色定位详解)
6. [元素生成机制](#6-元素生成机制)
7. [核心方法调用链](#7-核心方法调用链)
8. [功能场景应用](#8-功能场景应用)
9. [数据存储结构](#9-数据存储结构)

---

## 1. 角色 (Character)

### 1.1 定义

角色是故事的核心载体，承载着叙事动机、情感变化和成长弧线。每个角色都具备独特的需求系统、世界观倾向和性格特征。

### 1.2 属性构成

**代码定义**：[core/types/narrative.py#L163](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L163)

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 角色唯一标识符 |
| `name` | `str` | 角色名称 |
| `need` | `CharacterNeed` | 双层需求系统（外部目标 + 内在渴望） |
| `obstacles` | `list[Obstacle]` | 角色面临的障碍列表 |
| `worldview` | `CharacterWorldview` | 世界观倾向（权力态度、信任倾向、应对方式） |
| `arc` | `Literal` | 成长弧线类型 |
| `profile` | `str` | 外貌、背景、说话风格描述 |
| `behavior_lock` | `list[str]` | 性格锁定（绝对不会做的事） |

### 1.3 双层需求系统

**代码定义**：[core/types/narrative.py#L65](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L65)

```python
@dataclass
class CharacterNeed:
    external: str  # 外部目标："逆天改命，登顶巅峰"
    internal: str  # 内在渴望："证明自己不是废物"
```

### 1.4 角色定位分类

**代码定义**：[core/types/narrative.py#L32](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L32)

| 定位 | 枚举值 | 功能描述 |
|------|--------|----------|
| 主角 | `PROTAGONIST` | 故事核心，推动主线发展 |
| 反派 | `ANTAGONIST` | 主要冲突来源 |
| 守护者 | `GUARDIAN` | 导师/引导者 |
| 伙伴 | `SIDEKICK` | 忠诚支持者 |
| 恋人 | `LOVE_INTEREST` | 情感线索承载者 |
| 冲击者 | `IMPACT` | 改变主角认知的人 |
| 阻碍者 | `CONTAGONIST` | 表面帮助，实际拖延 |
| 怀疑者 | `SKEPTIC` | 质疑主角决策 |
| 理性者 | `REASON` | 提供理性分析 |
| 感性者 | `EMOTION` | 提供情感支持 |

### 1.5 核心功能

- **视角提供者**：作为章节POV角色
- **动机驱动**：通过 `need` 属性驱动情节发展
- **冲突引擎**：`obstacles` 定义角色面临的挑战
- **成长载体**：`arc` 定义角色的变化轨迹

---

## 2. 世界 (World)

### 2.1 系统定位

世界是故事发生的舞台，包含地点、势力、规则三个核心组件，为叙事提供空间框架和规则约束。

### 2.2 数据结构

#### 地点 (Location)

**代码定义**：[core/types/narrative.py#L246](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L246)

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 地点唯一标识 |
| `name` | `str` | 地点名称 |
| `description` | `str` | 地点描述 |
| `connections` | `list[str]` | 相邻地点ID列表 |
| `faction` | `str \| None` | 所属势力 |
| `dramatic_potential` | `str \| None` | 该地点的戏剧潜力 |

#### 势力 (Faction)

**代码定义**：[core/types/narrative.py#L256](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L256)

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 势力唯一标识 |
| `name` | `str` | 势力名称 |
| `description` | `str` | 势力描述 |
| `relations` | `dict[str, int]` | 与其他势力的关系值（-100~100） |
| `core_interest` | `str` | 核心利益诉求 |

#### 世界规则 (WorldRule)

**代码定义**：[core/types/narrative.py#L266](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L266)

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 规则名称 |
| `description` | `str` | 规则描述 |
| `consequence` | `str` | 违反规则的后果 |
| `is_hard` | `bool` | 是否为不可违反的硬规则 |

### 2.3 边界范围

- **地理边界**：通过 `Location.connections` 定义可达性
- **规则边界**：通过 `WorldRule.is_hard` 定义硬性约束
- **势力边界**：通过 `Faction.relations` 定义势力关系网络

### 2.4 关联关系

```
世界
├── 地点 (Location) → 角色活动场所、事件发生地
├── 势力 (Faction) → 角色所属组织、冲突来源
└── 规则 (WorldRule) → 约束角色行为、事件结果
```

---

## 3. 事件 (StoryEvent)

### 3.1 定义

事件是推动故事发展的基本单位，包含触发条件、执行效果和连锁反应。

### 3.2 数据格式

**代码定义**：[core/types/narrative.py#L276](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L276)

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 事件唯一标识 |
| `name` | `str` | 事件名称 |
| `description` | `str` | 事件描述 |
| `preconditions` | `list[str]` | 触发前提条件 |
| `effects` | `list[str]` | 事件执行效果 |
| `triggers` | `list[str]` | 触发的后续事件ID |
| `suggested_act` | `Act \| None` | 建议放置的幕次 |
| `suggested_function` | `DramaticFunction \| None` | 建议的戏剧功能 |

### 3.3 触发机制

```
┌─────────────────────────────────────────────────────────────┐
│                    事件触发流程                            │
├─────────────────────────────────────────────────────────────┤
│  1. 检查 preconditions（前提条件）                          │
│     └── 角色状态、世界状态是否满足                          │
│  2. 执行 effects（效果）                                    │
│     └── 改变角色关系、世界状态、触发因果链                    │
│  3. 触发 triggers（连锁事件）                                │
│     └── 激活关联的后续事件                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.4 传播路径

```
事件A → triggers → 事件B → triggers → 事件C
         ↓
    affects_characters → 角色状态变化
    affects_threads    → 跨线程影响
```

### 3.5 对系统状态的影响

- **角色关系**：修改角色关系值
- **世界状态**：改变地点属性、势力关系
- **因果链**：添加到 `CausalLink` 追踪因果关系
- **时间轴**：记录到 `TimelineEvent`

---

## 4. 线程 (NarrativeThread)

### 4.1 定义

叙事线程是多线叙事的基本单元，每条线程有独立的视角角色、目标弧线和进度追踪。

### 4.2 属性构成

**代码定义**：[core/types/narrative.py#L192](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L192)

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 线程唯一标识 |
| `name` | `str` | 线程名称 |
| `type` | `ThreadType` | 线程类型 |
| `pov_character_id` | `str` | 主视角角色ID |
| `character_ids` | `list[str]` | 相关角色ID列表 |
| `goal` | `str` | 线程终极目标 |
| `growth_arc` | `str` | 成长弧线描述 |
| `start_chapter` | `int` | 起始章节 |
| `last_active_chapter` | `int` | 最后活跃章节 |
| `weight` | `float` | 权重（影响字数分配） |
| `status` | `str` | 状态（active/inactive） |
| `merge_target_thread` | `str \| None` | 合并目标线程 |
| `hook_score` | `int` | 钩子评分 |
| `merge_chapter` | `int \| None` | 计划合并章节 |
| `end_hook` | `str` | 结尾钩子 |

### 4.3 线程类型

**代码定义**：[core/types/narrative.py#L184](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L184)

| 类型 | 枚举值 | 功能描述 |
|------|--------|----------|
| 主线 | `MAIN` | 核心叙事线，权重1.0 |
| 支线 | `SUBPLOT` | 辅助主线，权重0.7 |
| 并行线 | `PARALLEL` | 同时发生，最终汇合 |
| 闪回线 | `FLASHBACK` | 回忆叙事 |

### 4.4 生命周期管理

```
创建 → 活跃 → 暂停/休眠 → 合并/结束
  ↓       ↓          ↓           ↓
AI生成   写作中   超过5章未活跃   汇入主线
```

### 4.5 资源占用特性

- **字数分配**：`weight` 属性决定章节字数比例
- **活跃追踪**：`last_active_chapter` 用于掉线预警
- **时间轴资源**：每个线程维护独立的时间线事件

---

## 5. 角色定位详解

### 5.1 具体含义

角色定位定义了角色在叙事结构中的功能位置，而非简单的性格描述，基于 Dramatica 叙事理论。

### 5.2 确定依据

1. **叙事功能**：根据故事结构需要确定角色职能
2. **用户配置**：在世界观表单中手动选择
3. **AI 建议**：系统根据角色设定自动推荐

### 5.3 在系统中的作用

- **视角分配**：决定哪些角色可以成为章节POV
- **冲突构建**：主角 vs 反派的核心矛盾
- **主题表达**：导师传递主题，恋人提供情感线索

---

## 6. 元素生成机制

### 6.1 生成时机与触发条件

| 元素 | 生成时机 | 触发条件 |
|------|----------|----------|
| **角色** | Step 3 世界观配置 | 创建书籍后进入世界观配置 |
| **世界** | Step 3 世界观配置 | 角色配置完成后 |
| **事件** | Step 3 世界观配置 | 世界配置完成后 |
| **线程** | Step 4 大纲规划 | 章节大纲生成后 |

### 6.2 页面功能模块

| 元素 | 页面模块 | 用户操作路径 |
|------|----------|--------------|
| **角色** | 角色表单 | 世界观 → 角色 → 添加/编辑 |
| **世界** | 世界表单 | 世界观 → 世界 → 添加/编辑 |
| **事件** | 事件表单 | 世界观 → 事件 → 添加/编辑 |
| **线程** | 线程管理 | 世界观 → 线程 → 从章纲生成/添加 |

---

## 7. 核心方法调用链

### 7.1 角色生成

```python
# 表单模式保存
POST /api/books/{book_id}/setup/characters
→ setup_save() [core/server.py#L512]
→ _write_json("setup/characters.json")

# AI生成
POST /api/books/{book_id}/ai-generate-characters
→ ai_generate_characters()
→ CharacterGenerator.generate()
```

### 7.2 线程生成

```python
# 从章纲生成
POST /api/books/{book_id}/auto-generate-threads
→ auto_generate_threads() [core/server.py#L761]
→ sm.create_thread(new_thread) [core/state/__init__.py#L401]
→ write_world_state(state)
```

### 7.3 核心方法说明

**create_thread**：[core/state/__init__.py#L401](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/state/__init__.py#L401)

| 参数 | 类型 | 说明 |
|------|------|------|
| `thread` | `NarrativeThread` | 线程对象 |

**write_world_state**：[core/state/__init__.py#L281](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/state/__init__.py#L281)

| 参数 | 类型 | 说明 |
|------|------|------|
| `state` | `WorldState` | 世界状态对象 |

---

## 8. 功能场景应用

### 8.1 场景一：多线叙事写作

**需求**：在主线推进的同时，并行描写反派的阴谋线

**应用方式**：
1. 创建主线和反派支线两个线程
2. 在章节大纲中分配不同POV
3. 写作时传入当前线程上下文
4. 审计时检查跨线程一致性

### 8.2 场景二：事件驱动叙事

**需求**：确保故事事件有明确的因果关系

**应用方式**：
1. 在事件配置中定义 `preconditions` 和 `triggers`
2. 写作时自动检查前置条件是否满足
3. 审计时验证因果链完整性

### 8.3 场景三：世界观约束写作

**需求**：确保写作符合设定的世界规则

**应用方式**：
1. 配置世界规则（硬规则/软规则）
2. 写作时传入世界规则上下文
3. 审计时检查是否违反规则

### 8.4 业务价值体现

| 元素 | 业务价值 |
|------|----------|
| **角色** | 提供有深度的人物塑造，驱动情节发展 |
| **世界** | 构建沉浸式故事环境，提供叙事舞台 |
| **事件** | 确保情节逻辑性，构建因果链条 |
| **线程** | 支持多线叙事，提升故事复杂度和层次感 |

---

## 9. 数据存储结构

### 9.1 文件存储路径

```
dramatica-flow/
  books/
    {book_id}/
      setup/
        characters.json    ← 角色数据
        world.json         ← 世界数据（地点、势力、规则）
        events.json        ← 事件数据
      state/
        world_state.json   ← 运行时状态（线程、时间轴、因果链）
```

### 9.2 world_state.json 结构

```json
{
  "book_id": "book_001",
  "current_chapter": 5,
  "character_positions": { "char_001": "loc_001" },
  "relationships": [...],
  "threads": [
    {
      "id": "thread_main",
      "name": "主角线",
      "type": "main",
      "pov_character_id": "char_001",
      "start_chapter": 1,
      "last_active_chapter": 5,
      "weight": 1.0,
      "status": "active"
    }
  ],
  "timeline": [...],
  "causal_chain": [...]
}
```

---

## 附录：元素相互关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                        世界观系统                              │
├─────────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐      属于       ┌──────────┐                    │
│  │  角色    │──────────────→│  线程    │                    │
│  └────┬─────┘                └────┬─────┘                    │
│       │ 发生于                    │ 包含                      │
│       ↓                          ↓                            │
│  ┌──────────┐           ┌──────────────┐                     │
│  │  事件    │←────触发──│  世界规则   │                     │
│  └────┬─────┘           └──────────────┘                     │
│       │ 发生在                                                │
│       ↓                                                       │
│  ┌──────────┐      归属       ┌──────────┐                    │
│  │  地点    │←──────────────│  势力    │                    │
│  └──────────┘                └──────────┘                    │
│                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

**文档版本**：v1.0  
**创建日期**：2026-06-05  
**适用范围**：Dramatica Flow 世界观系统