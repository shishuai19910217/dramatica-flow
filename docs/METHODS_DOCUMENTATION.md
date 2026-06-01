
# Dramatica-Flow 小说创作方法论

**版本**: v0.1.0  
**日期**: 2026-06-01  
**作者**: Dramatica-Flow 开发团队  
**状态**: 正式版

---

## 目录

1. [引言](#1-引言)
2. [核心叙事理论](#2-核心叙事理论)
3. [结构方法论](#3-结构方法论)
4. [故事技巧](#4-故事技巧)
5. [多线叙事架构](#5-多线叙事架构)
6. [质量保证体系](#6-质量保证体系)
7. [方法论整合](#7-方法论整合)
8. [附录](#8-附录)

---

## 1. 引言

### 1.1 项目概述

**Dramatica-Flow** 是一款基于成熟叙事理论构建的 AI 长篇小说创作系统，其核心价值在于将小说创作抽象为可量化、可追踪、可审计的工程流程。与普通 AI 写作工具不同，本系统不依赖临时生成，而是通过系统化的方法论确保长篇作品的叙事一致性和内在逻辑性。

### 1.2 方法论设计原则

| 原则 | 说明 |
|------|------|
| **理论驱动** | 以成熟叙事理论为基础，而非随意创作 |
| **可追踪性** | 所有创作决策可追溯、可解释 |
| **因果优先** | 强制建立事件间的因果关系 |
| **状态一致性** | 世界状态在章节间正确累积 |
| **可审计性** | 三层审计确保叙事质量 |

---

## 2. 核心叙事理论

### 2.1 Dramatica 叙事理论

#### 2.1.1 理论定义

**Dramatica** 是一套全面的叙事理论，由 Chris Huntley 和 Melanie Anne Phillips 开发，核心思想是：
- 每个故事都有内在逻辑结构
- 角色并非随机行动，而是基于内在需求和外部压力做出选择
- 故事围绕核心冲突展开，最终解决某种不平衡

#### 2.1.2 在项目中的应用

在 Dramatica-Flow 中，Dramatica 理论主要体现在：

| 应用维度 | 实现方式 |
|----------|----------|
| **双层需求模型** | 每个角色具有外部目标（可见的）和内在渴望（真实的） |
| **角色职能体系** | 主角、反派、冲击者、守护者等具有明确职能 |
| **信息边界原则** | 角色只能知道亲眼所见的信息 |

#### 2.1.3 角色双层需求模型

**数据结构**（[core/types/narrative.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L64)）：
```python
@dataclass
class CharacterNeed:
    external: str  # 外部可见的目标
    internal: str  # 角色不自知的真实需求
```

**实践示例**：
| 角色 | 外部目标 | 内在渴望 |
|------|----------|----------|
| 玄幻主角 | 逆天改命，获得最高地位 | 证明自己不是废物，获得认可 |
| 现代职场 | 拿下关键项目，升职加薪 | 找到工作的意义，与自我和解 |

#### 2.1.4 角色职能体系

| 角色职能 | 叙事作用 |
|----------|----------|
| **主角 (Protagonist)** | 推动故事前进的核心力量 |
| **反派 (Antagonist)** | 与主角目标对立的对抗者 |
| **冲击者 (Impact Character)** | 改变主角认知的关键人物 |
| **守护者 (Guardian)** | 导师/引导者角色 |
| **阻碍者 (Contagonist)** | 表面帮助，实际拖延的角色 |
| **伙伴 (Sidekick)** | 忠诚的支持者 |
| **怀疑者 (Skeptic)** | 质疑与反面声音 |

**相关代码**：[core/types/narrative.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L32)

---

### 2.2 信息边界原则

#### 2.2.1 概念定义

**信息边界** 是 Dramatica-Flow 中的核心原则：角色只能知道他们亲眼所见、亲耳所闻、亲身推理或明确被告知的信息，不能拥有上帝视角。

#### 2.2.2 在项目中的应用

**数据结构**（[core/types/state.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/state.py#L77)）：
```python
@dataclass
class KnownInfoRecord:
    character_id: str
    info_key: str
    content: str
    learned_in_chapter: int
    source: Literal["witnessed", "hearsay", "deduced", "document"]
```

**信息来源**：
| 来源类型 | 说明 |
|----------|------|
| `witnessed` | 角色亲眼所见 |
| `hearsay` | 从他人处听闻 |
| `deduced` | 角色自己推理得出 |
| `document` | 通过文字材料获知 |

#### 2.2.3 实践示例

**正确做法**：
> 角色 A 在第 3 章偷听到反派密谋，但角色 B 在第 5 章才能从角色 A 处得知此事。

**错误做法**：
> 角色 B 在第 4 章就知道反派的阴谋，而没有任何合理的信息来源。

---

## 3. 结构方法论

### 3.1 三幕式结构 (Three-Act Structure)

#### 3.1.1 理论定义

**三幕式结构** 是经典的叙事框架，将故事分为：
- **第一幕**（Setup）：建立世界、角色、冲突，发生激励事件
- **第二幕**（Confrontation）：持续升级对抗，中点转折，灵魂黑夜
- **第三幕**（Resolution）：高潮对决，解决冲突，完成角色弧线

#### 3.1.2 在项目中的应用

**章节分配**：
| 幕数 | 占比 | 功能 |
|------|------|------|
| **第一幕** | 25% | 建立世界、角色、激励事件 |
| **第二幕** | 50% | 持续升级对抗、中点转折、危机最低点 |
| **第三幕** | 25% | 高潮对决、解决冲突、完成角色弧线 |

**四大关键锚点**（[core/narrative/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/narrative/__init__.py#L125)）：
```python
class KeyAnchorsSchema(BaseModel):
    opening_hook: str    # 开篇强钩子（第 1 章）
    midpoint_twist: str  # 中点反转（约 50% 处）
    soul_night: str      # 灵魂黑夜（约 75% 处）
    final_climax: str    # 终局高潮（结尾）
```

#### 3.1.3 实践示例

以 90 章小说为例：
| 锚点 | 章节 | 作用 |
|------|------|------|
| 开篇钩子 | 第 1-3 章 | 退婚/背叛/危机，抓住读者 |
| 中点转折 | 第 45 章 | 获得重要线索/盟友背叛 |
| 灵魂黑夜 | 第 68 章 | 失去一切，看似无解 |
| 终局高潮 | 第 85-90 章 | 最终对决，解决一切 |

---

### 3.2 Dan Harmon 8 步故事圈

#### 3.2.1 理论定义

**Dan Harmon 8 步故事圈** 是由《废柴联盟》编剧 Dan Harmon 开发的叙事框架，包含：
1. 身处安逸 (You)
2. 渴望某物 (Need)
3. 进入未知 (Go)
4. 适应过程 (Search)
5. 获得宝物 (Find)
6. 付出代价 (Pay)
7. 返回考验 (Return)
8. 蜕变新生 (Change)

#### 3.2.2 在项目中的应用

项目实现了根据序列长度自动分配故事圈节奏的功能（[core/narrative/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/narrative/__init__.py#L23)）：

**分配逻辑**：
| 序列长度 | 故事圈节奏分配 |
|----------|----------------|
| ≥ 8 章 | 完整 8 步，每步对应章节 |
| 4-7 章 | 合并某些步骤，保持整体节奏 |
| ≤ 3 章 | 简化为核心 4 步 |

#### 3.2.3 实践示例

以 8 章序列为例：
| 步骤 | 章节 | 功能 |
|------|------|------|
| 1. 身处安逸 | 第 1 章 | 介绍日常状态 |
| 2. 渴望某物 | 第 2 章 | 引入冲突或目标 |
| 3. 进入未知 | 第 3 章 | 冒险开始 |
| 4. 适应过程 | 第 4-5 章 | 探索与适应 |
| 5. 获得宝物 | 第 6 章 | 达成关键目标 |
| 6. 付出代价 | 第 7 章 | 遭遇挫折或损失 |
| 7. 返回考验 | 第 7-8 章 | 回归并面对考验 |
| 8. 蜕变新生 | 第 8 章 | 角色成长与变化 |

---

## 4. 故事技巧

### 4.1 因果链驱动叙事 (Causal Chain)

#### 4.1.1 概念定义

**因果链** 是 Dramatica-Flow 的核心创新：强制每个事件回答三个问题：
1. **Cause**（因为什么）：事件的触发原因
2. **Event**（发生了什么）：事件本身
3. **Consequence**（导致了什么）：事件的直接后果

#### 4.1.2 在项目中的应用

**数据结构**（[core/types/state.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/state.py#L109)）：
```python
@dataclass
class CausalLink:
    id: str
    chapter: int
    cause: str                              # 触发原因
    event: str                              # 发生了什么
    consequence: str                        # 直接后果
    affected_decisions: list[AffectedDecision]  # 角色决策变化
    triggered_events: list[str]             # 下游事件
    thread_id: str = "thread_main"          # 所属线程
    source_thread_id: str = ""              # 跨线程因果来源
```

**提取流程**（[core/narrative/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/narrative/__init__.py#L480)）：
1. 截取章节内容（前 4000 字 + 后 2000 字）
2. 调用 LLM 分析提取 2-5 条关键因果链
3. Pydantic 验证格式
4. 存储到 world_state 和 causal_chain.md

#### 4.1.3 实践示例

**因果链示例**：
| 章节 | 原因 | 事件 | 后果 |
|------|------|------|------|
| 第 1 章 | 宗门大比失败 | 主角被退婚 | 主角决心修炼复仇 |
| 第 5 章 | 主角救了长老 | 长老赠予功法 | 主角获得快速成长机会 |
| 第 10 章 | 主角实力大增 | 反派上门挑衅 | 引发冲突，伏笔后续对决 |

---

### 4.2 伏笔管理系统 (Hook System)

#### 4.2.1 概念定义

**伏笔** 是在叙事中提前埋设、后来回收的线索，用于构建悬念和前后呼应。Dramatica-Flow 支持 6 种伏笔类型，并实现了完整的生命周期管理。

#### 4.2.2 伏笔类型

| 伏笔类型 | 说明 | 示例 |
|----------|------|------|
| `FORESHADOW` | 暗线铺垫 | 第 3 章提及的神秘玉佩 |
| `PROMISE` | 叙事承诺 | "三年之约"必须兑现 |
| `MYSTERY` | 未解之谜 | 密室中消失的灵力 |
| `CONFLICT` | 未解决矛盾 | 两大势力的暗战 |
| `TWIST` | 反转伏笔 | 某人的真实身份 |
| `CHARACTER_SECRET` | 角色秘密 | 隐藏的过去 |

#### 4.2.3 在项目中的应用

**数据结构**：
```python
@dataclass
class Hook:
    id: str
    type: HookType
    content: str
    planted_in_chapter: int
    expected_resolve_chapter: int
    status: Literal["planted", "advanced", "resolved", "overdue", "abandoned"] = "planted"
    thread_id: str = "thread_main"
```

**生命周期**：
```
埋设(planted) → 推进(advanced) → 回收(resolved)
                  ↓
               逾期(overdue) → 放弃(abandoned)
```

**预警机制**：超过预期回收章节的伏笔会被标记为 `overdue`，提醒作者处理。

#### 4.2.4 实践示例

**伏笔埋设与回收**：
| 章节 | 类型 | 内容 | 状态 |
|------|------|------|------|
| 第 3 章 | MYSTERY | "这个玉佩上的符文似乎很古老" | planted |
| 第 5 章 | FORESHADOW | 玉佩在月光下微闪 | advanced |
| 第 20 章 | RESOLVED | 玉佩开启了秘境大门 | resolved |

---

### 4.3 情感弧线追踪 (Emotional Arcs)

#### 4.3.1 概念定义

**情感弧线** 是角色在故事中的情感变化轨迹，结合 Dramatica 的双层需求模型，追踪角色外部目标和内在渴望的演变。

#### 4.3.2 在项目中的应用

项目通过写后结算表实现情感状态更新：
```python
@dataclass
class WriterSettlement:
    emotional_changes: list[EmotionalChange]  # 情感变化列表
    # ... 其他状态变化
```

#### 4.3.3 实践示例

**主角情感弧线**：
| 章节 | 情感状态 | 触发事件 |
|------|----------|----------|
| 第 1 章 | 屈辱、愤怒 | 退婚事件 |
| 第 10 章 | 期待、紧张 | 首次获得重要功法 |
| 第 30 章 | 怀疑、迷茫 | 发现信任的人背叛 |
| 第 60 章 | 坚定、无畏 | 找到自己要守护的事物 |
| 第 90 章 | 平静、成长 | 完成旅程，获得真正的认可 |

---

### 4.4 关系网络 (Relationship Network)

#### 4.4.1 概念定义

**关系网络** 追踪角色间关系强度的变化，从 -100（死敌）到 +100（生死同盟）连续变化。

#### 4.4.2 在项目中的应用

**数据结构**（[core/types/state.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/state.py#L58)）：
```python
@dataclass
class RelationshipRecord:
    character_a: str
    character_b: str
    type: RelationshipType  # ALLY/ENEMY/NEUTRAL/FAMILY/MENTOR/RIVAL/ROMANTIC
    strength: int           # -100 到 +100
    history: list[RelationshipDelta]  # 变化历史
```

---

## 5. 多线叙事架构

### 5.1 线程类型体系

| 线程类型 | 权重 | 说明 |
|----------|------|------|
| `MAIN` | 1.0 | 主线，核心故事线 |
| `SUBPLOT` | 0.7 | 支线，次要故事线 |
| `PARALLEL` | 0.8 | 并行线，同时发生，最终汇合 |
| `FLASHBACK` | 0.5 | 闪回线，回忆内容 |

**数据结构**（[core/types/narrative.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L191)）：
```python
@dataclass
class NarrativeThread:
    id: str
    name: str
    type: ThreadType
    pov_character_id: str = ""
    character_ids: list[str] = field(default_factory=list)
    goal: str = ""
    start_chapter: int = 1
    last_active_chapter: int = 0
    weight: float = 1.0
    status: Literal["active", "dormant", "resolved", "merged"] = "active"
    hook_score: int = 80
```

---

### 5.2 跨线程感知机制

在 [core/pipeline.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/pipeline.py#L359) 中实现的跨线程感知机制：

```python
def _build_thread_context(self, ws, current_thread_id: str, chapter: int) -> str:
    """构建跨线程感知上下文"""
    lines = []
    for t in ws.get_active_threads():
        if t.id == current_thread_id:
            continue
        lines.append(
            f"- {t.name}（{t.id}）：上次活跃 Ch.{t.last_active_chapter}，"
            f"期待感 {t.hook_score}/100"
        )
        if t.end_hook:
            lines.append(f"  当前悬念：{t.end_hook}")
    return "\n".join(lines)
```

**应用效果**：
- 建筑师 Agent 了解其他线程的状态
- 写手 Agent 考虑多线的相互影响
- 审计 Agent 检查线程间的逻辑一致性

---

### 5.3 全局时间轴 (Global Timeline)

#### 5.3.1 概念定义

**时间轴** 以泳道图形式呈现，将不同线程的事件按时间顺序排列，确保多线叙事的时间一致性。

#### 5.3.2 时间轴事件数据结构

```python
@dataclass
class TimelineEvent:
    id: str
    chapter: int
    physical_time: str        # "第一天清晨"
    character_id: str
    location_id: str
    action: str
    thread_id: str
    affected_threads: list[str]  # 跨线程影响
```

---

## 6. 质量保证体系

### 6.1 三层审计框架

在 [core/agents/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/agents/__init__.py#L448) 中实现的三层审计：

| 审计层次 | 检查内容 |
|----------|----------|
| **大纲对齐审计** | 剧情是否跑偏、mandatory_tasks 是否完成、因果一致性 |
| **人设逻辑审计** | OOC、信息边界、连续性、情感弧线 |
| **节奏合规审计** | 结尾钩子、冲突质量、AI 标记词密度、三幕式节奏 |

**审计报告结构**：
```python
@dataclass
class AuditReport:
    passed: bool
    issues: list[AuditIssue]
    overall_score: int  # 0-100

@dataclass
class AuditIssue:
    severity: Literal["critical", "warning", "info"]
    category: Literal["outline", "character", "pacing", "other"]
    description: str
    suggestion: str
```

---

### 6.2 写后验证（零 LLM）

在 [core/validators/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/validators/__init__.py) 中实现的硬规则验证：

| 验证项目 | 说明 |
|----------|------|
| 字数验证 | 检查是否达到目标字数的 80% |
| 禁止词检查 | 用户自定义禁止词列表 |
| 格式验证 | 章节标题格式、段落结构 |
| AI 标记词检查 | "综上所述"、"总而言之"等标记词密度 |

---

### 6.3 修订闭环

当审计发现问题时，系统自动触发修订流程：
1. 识别 critical 和 warning 级别问题
2. 调用 Reviser Agent 进行自动修订
3. 重新审计修订后的内容
4. 最多执行 2 轮修订

---

## 7. 方法论整合

### 7.1 单章创作流程

完整的单章创作工作流（[core/pipeline.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/pipeline.py#L53)）：

```
1. 快照备份 → 2. 读取上下文（真相文件）→ 3. 建筑师规划蓝图
    ↓
4. 写手生成正文+写后结算表 → 5. 写后验证（零 LLM）
    ↓
6. 三层审计 → 7. 修订闭环（如需要）
    ↓
8. 因果链提取 → 9. 摘要生成 → 10. 状态结算
    ↓
11. 时间轴记录 + 线程状态更新
```

---

### 7.2 真相文件系统

项目通过 8 种真相文件维护世界状态（[core/state/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/state/__init__.py)）：

| 真相文件 | 内容 | 更新频率 |
|----------|------|----------|
| `current_state.md` | 当前世界状态摘要 | 每章结束 |
| `story_bible.md` | 世界观圣经 | 人工更新 |
| `chapter_summaries.md` | 章节摘要 | 每章结束 |
| `pending_hooks.md` | 未闭合伏笔 | 每章结束 |
| `emotional_arcs.md` | 情感弧线 | 每章结束 |
| `character_matrix.md` | 角色交互矩阵 | 每章结束 |
| `causal_chain.md` | 因果链日志 | 每章结束 |
| `thread_status.md` | 线程状态 | 每章结束 |

---

### 7.3 快照回滚机制

**快照存储格式**：`snapshots/ch_0001.json`

**回滚功能**：
- 将世界状态恢复到指定章节
- 删除后续所有章节内容
- 重置真相文件到当时状态

---

## 8. 附录

### 8.1 四大硬性故事线

系统强制要求小说必须包含四条核心故事线（[core/narrative/__init__.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/narrative/__init__.py#L118)）：
```python
class CoreStorylinesSchema(BaseModel):
    protagonist_growth: str   # 主角内心成长线
    antagonist_conflict: str  # 反派/影响角色博弈线
    relationship_dynamics: str # 核心人物关系拉扯线
    external_events: str      # 外部客观事件线（复仇/逆袭/权谋）
```

---

### 8.2 戏剧功能节拍 (DramaticFunction)

| 功能 | 说明 |
|------|------|
| `setup` | 建立角色/世界/规则 |
| `inciting` | 激励事件，打破平衡 |
| `turning` | 转折点，方向改变 |
| `midpoint` | 中点，承诺升级或假胜利 |
| `crisis` | 危机，最低点（灵魂黑夜） |
| `climax` | 高潮，终极对决 |
| `reveal` | 信息揭示，改变认知 |
| `decision` | 角色做出关键选择 |
| `consequence` | 行动的后果落地 |
| `transition` | 过渡，节奏调节 |

---

### 8.3 方法论与普通 AI 写作对比

| 维度 | 普通 AI 写作工具 | Dramatica-Flow |
|------|------------------|----------------|
| 叙事逻辑 | 逐段生成，缺乏全局因果 | **强制建模因果链** |
| 角色一致性 | 容易 OOC（性格崩塌） | **信息边界系统** |
| 长篇连贯性 | 前后矛盾频发 | **世界状态快照 + 真相文件** |
| 伏笔管理 | 无 | **伏笔生命周期管理** |
| 多线叙事 | 无 | **全局时间轴 + 线程调度** |

---

**文档结束**
