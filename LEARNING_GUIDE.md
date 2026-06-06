# Dramatica Flow 学习指南

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心概念入门](#2-核心概念入门)
3. [快速上手](#3-快速上手)
4. [世界观系统详解](#4-世界观系统详解)
5. [叙事引擎指南](#5-叙事引擎指南)
6. [API 接口说明](#6-api-接口说明)
7. [开发指南](#7-开发指南)
8. [最佳实践](#8-最佳实践)
9. [常见问题](#9-常见问题)

---

## 1. 项目概述

### 1.1 项目定位

Dramatica Flow 是一款基于 **Dramatica 叙事理论** 的 AI 小说创作辅助工具，旨在帮助作家和创作者构建有深度、有结构的故事。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| **智能大纲生成** | 基于 Dramatica 理论自动生成章节大纲 |
| **多线叙事管理** | 支持主线、支线、并行线等多种叙事线程 |
| **角色深度塑造** | 基于双重需求系统构建立体角色 |
| **AI 辅助写作** | 智能生成符合设定的章节内容 |
| **质量审计** | 检查叙事一致性和结构完整性 |

### 1.3 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Dramatica Flow                          │
├─────────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Web UI    │    │   API层     │    │   核心引擎  │    │
│  │ (HTML/JS)  │───▶│ (FastAPI)  │───▶│  (Python)  │    │
│  └─────────────┘    └─────────────┘    └──────┬──────┘    │
│                                                │          │
│                    ┌───────────────────────────┘          │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    数据层                          │   │
│  │  setup/    state/    chapters/    characters/     │   │
│  │  (JSON)    (JSON)    (Markdown)   (JSON)          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### 1.4 文件结构

```
dramatica-flow/
├── core/                    # 核心代码
│   ├── agents/             # AI 代理（Writer、Reviser、Auditor等）
│   ├── llm/                # LLM 接口抽象
│   ├── narrative/          # 叙事引擎
│   ├── pipeline.py         # 写作流水线
│   ├── server.py           # API 服务
│   ├── state/              # 状态管理
│   └── types/              # 数据类型定义
├── templates/              # JSON 模板
├── books/                  # 书籍数据目录
│   └── {book_id}/          # 具体书籍
│       ├── setup/          # 世界观配置
│       ├── state/          # 运行时状态
│       └── chapters/       # 章节内容
└── dramatica_flow_web_ui.html  # Web 界面
```

---

## 2. 核心概念入门

### 2.1 基本概念速览

| 概念 | 定义 | 重要性 |
|------|------|--------|
| **角色 (Character)** | 故事的核心载体，具备双重需求 | ⭐⭐⭐⭐⭐ |
| **世界 (World)** | 故事发生的舞台，包含地点、势力、规则 | ⭐⭐⭐⭐ |
| **事件 (StoryEvent)** | 推动故事发展的基本单位 | ⭐⭐⭐ |
| **线程 (NarrativeThread)** | 多线叙事的基本单元 | ⭐⭐⭐⭐ |
| **章纲 (ChapterOutline)** | 章节的详细大纲 | ⭐⭐⭐⭐ |

### 2.2 Dramatica 核心理论

#### 双重需求系统

每个角色都有**外部需求**和**内部需求**：

```python
# 示例：主角设定
Character(
    name="陆沉",
    need=CharacterNeed(
        external="逆天改命，登顶巅峰",  # 可见目标
        internal="证明自己不是废物"       # 内在渴望
    ),
    arc="positive"  # 正向成长弧线
)
```

#### 四元角色模型

| 角色职能 | 功能描述 |
|----------|----------|
| 主角 (Protagonist) | 推动故事发展，追求目标 |
| 反派 (Antagonist) | 制造障碍，代表对立力量 |
| 守护者 (Guardian) | 提供指导和帮助 |
| 阻碍者 (Contagonist) | 表面帮助，实际拖延 |

---

## 3. 快速上手

### 3.1 创建书籍

**步骤1**：调用创建书籍 API

```python
POST /api/books
{
    "title": "我的第一本小说",
    "genre": "玄幻",
    "words": 3000,           # 每章目标字数
    "chapters": 20,          # 目标章节数
    "forbidden": "",          # 禁用词
    "style_guide": "古风"     # 风格指南
}
```

**步骤2**：配置世界观（Step 3）

填写角色、世界、事件信息：
- **角色**：定义主角、反派、导师等
- **世界**：设定地点、势力、规则
- **事件**：规划关键剧情节点

**步骤3**：生成章节大纲（Step 4）

点击「生成大纲」按钮，AI 将基于世界观生成章节大纲。

**步骤4**：生成线程（可选）

在世界观页面点击「从章纲生成」自动创建叙事线程。

**步骤5**：开始写作（Step 5）

选择章节，点击「AI 续写」生成内容。

---

## 4. 世界观系统详解

### 4.1 角色管理

#### 角色属性

**代码定义**：[core/types/narrative.py#L163](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L163)

| 属性 | 说明 | 示例 |
|------|------|------|
| `id` | 唯一标识 | `char_001` |
| `name` | 角色名称 | `陆沉` |
| `need` | 双重需求 | `CharacterNeed` 对象 |
| `worldview` | 世界观倾向 | `CharacterWorldview` 对象 |
| `arc` | 成长弧线 | `positive/negative/flat/corrupt` |
| `behavior_lock` | 性格锁定 | `["背叛朋友"]` |

#### 角色定位选择

```python
class CharacterRole(str, Enum):
    PROTAGONIST   = "protagonist"    # 主角
    ANTAGONIST    = "antagonist"     # 反派
    GUARDIAN      = "guardian"       # 守护者
    SIDEKICK      = "sidekick"       # 伙伴
    LOVE_INTEREST = "love_interest"  # 恋人
    # ... 更多角色类型
```

### 4.2 世界构建

#### 地点 (Location)

```python
Location(
    id="loc_001",
    name="青锋山脉",
    description="险峻的山脉，蕴含丰富的灵脉",
    connections=["loc_002", "loc_003"],  # 相邻地点
    faction="faction_001",
    dramatic_potential="适合战斗场景"
)
```

#### 势力 (Faction)

```python
Faction(
    id="faction_001",
    name="青云宗",
    description="正道第一大宗",
    relations={"血魔谷": -80, "天音寺": 50},  # 势力关系
    core_interest="维护正道秩序"
)
```

#### 世界规则 (WorldRule)

```python
WorldRule(
    name="灵力守恒",
    description="灵力既不能凭空产生，也不能凭空消失",
    consequence="违反此规则将遭受天谴",
    is_hard=True  # 不可违反的硬规则
)
```

### 4.3 事件规划

```python
StoryEvent(
    id="evt_001",
    name="退婚之辱",
    description="主角被未婚妻当众退婚",
    preconditions=["主角修为低下"],
    effects=["主角决心变强", "与未婚妻结怨"],
    triggers=["evt_002"],  # 触发下一个事件
    suggested_act=1,
    suggested_function="inciting"  # 激励事件
)
```

---

## 5. 叙事引擎指南

### 5.1 章节大纲生成

#### 生成流程

```python
# 调用示例
POST /api/books/{book_id}/ai-generate-outline
{
    "prompt": "生成一个废土异能题材的章节大纲",
    "style": "硬核科幻"
}
```

#### 章纲结构

```python
ChapterOutlineSchema(
    chapter_number=1,
    title="第1章-废土求生",
    summary="主角在废土中艰难求生，发现自己的异能",
    beats=[
        BeatSchema(
            id="beat_1_1",
            description="遭遇变异兽",
            dramatic_function="setup",
            story_circle_step=1
        ),
        # ... 更多节拍
    ],
    target_words=3000,
    pov="陆沉",
    writing_notes="保持紧张感"
)
```

### 5.2 线程系统

#### 线程类型

```python
class ThreadType(str, Enum):
    MAIN = "main"           # 主线
    SUBPLOT = "subplot"     # 支线
    PARALLEL = "parallel"   # 并行线
    FLASHBACK = "flashback" # 闪回线
```

#### 线程权重

| 线程类型 | 权重 | 说明 |
|----------|------|------|
| MAIN | 1.0 | 核心叙事，字数最多 |
| SUBPLOT | 0.7 | 辅助主线 |
| PARALLEL | 0.8 | 同时发生 |
| FLASHBACK | 0.6 | 回忆叙事 |

#### 线程生命周期

```
创建 → 活跃 → 休眠 → 合并/结束
  ↓       ↓        ↓          ↓
AI生成  写作中   5章未活跃    汇入主线
```

### 5.3 写作流水线

**代码定义**：[core/pipeline.py](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/pipeline.py)

```python
class WritingPipeline:
    def write_chapter(self, chapter_number: int):
        # 1. 获取章纲
        outline = self._get_chapter_outline(chapter_number)
        
        # 2. 获取线程上下文
        thread_context = self._build_thread_context(chapter_number)
        
        # 3. 调用 WriterAgent 生成内容
        content = self.writer.write_chapter(
            outline=outline,
            thread_context=thread_context,
            max_tokens=self._calculate_max_tokens(outline.target_words)
        )
        
        # 4. 审计内容
        audit_report = self.auditor.audit_chapter(content)
        
        # 5. 质量保障
        quality_report = self.quality_agent.evaluate(content)
        
        # 6. 自动修订
        if audit_report.has_errors:
            content = self.reviser.revise(
                content,
                audit_report.issues,
                target_words=outline.target_words
            )
        
        return content
```

---

## 6. API 接口说明

### 6.1 书籍管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books` | POST | 创建书籍 |
| `/api/books` | GET | 获取书籍列表 |
| `/api/books/{book_id}` | GET | 获取书籍详情 |
| `/api/books/{book_id}` | PUT | 更新书籍信息 |
| `/api/books/{book_id}` | DELETE | 删除书籍 |

### 6.2 世界观管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books/{book_id}/setup/characters` | PUT | 保存角色 |
| `/api/books/{book_id}/setup/world` | PUT | 保存世界 |
| `/api/books/{book_id}/setup/events` | PUT | 保存事件 |
| `/api/books/{book_id}/setup/load` | POST | 加载配置 |

### 6.3 线程管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books/{book_id}/threads` | GET | 获取线程列表 |
| `/api/books/{book_id}/threads` | POST | 创建线程 |
| `/api/books/{book_id}/threads/{thread_id}` | PUT | 更新线程 |
| `/api/books/{book_id}/threads/{thread_id}` | DELETE | 删除线程 |
| `/api/books/{book_id}/auto-generate-threads` | POST | 从章纲生成线程 |

### 6.4 写作接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/books/{book_id}/ai-generate-outline` | POST | 生成章节大纲 |
| `/api/books/{book_id}/ai-write-chapter` | POST | AI 续写章节 |
| `/api/books/{book_id}/audit-chapter` | POST | 审计章节 |
| `/api/books/{book_id}/revise-chapter` | POST | 修订章节 |

---

## 7. 开发指南

### 7.1 环境搭建

```bash
# 克隆项目
git clone <repo_url>
cd dramatica-flow

# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
cp .env.example .env
# 编辑 .env，配置 LLM API 密钥

# 启动服务
python -m core.server
```

### 7.2 扩展 AI 代理

```python
# 示例：创建自定义 Agent
from core.agents.base import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
    
    def process(self, input_data):
        # 实现自定义逻辑
        prompt = self._build_prompt(input_data)
        response = self.llm.complete([LLMMessage("user", prompt)])
        return self._parse_response(response)
```

### 7.3 添加新的叙事类型

```python
# 示例：添加新的线程类型
from enum import Enum

class ThreadType(str, Enum):
    MAIN = "main"
    SUBPLOT = "subplot"
    PARALLEL = "parallel"
    FLASHBACK = "flashback"
    MY_NEW_TYPE = "my_new_type"  # 新增
```

---

## 8. 最佳实践

### 8.1 角色设计技巧

1. **明确双重需求**：每个主要角色都应有明确的外部目标和内在渴望
2. **性格锁定**：定义角色绝对不会做的事，增加可信度
3. **成长弧线**：规划角色从故事开始到结束的变化

### 8.2 世界构建原则

1. **规则一致性**：硬规则不可违反，软规则增加张力
2. **地点连接**：通过 `connections` 构建合理的地理网络
3. **势力关系**：使用 `-100~100` 的关系值定义势力间的态度

### 8.3 多线叙事策略

1. **主线优先**：确保主线有最高权重和最多篇幅
2. **交叉影响**：在关键节点让不同线程产生互动
3. **掉线预警**：定期检查长时间未活跃的线程

### 8.4 字数控制

1. **设置合理目标**：根据故事节奏设置每章字数
2. **使用线程权重**：支线可以比主线短
3. **API 层面控制**：通过 `max_tokens` 参数限制输出

---

## 9. 常见问题

### Q1：章节大纲生成后，线程不会自动生成？

**A**：是的，线程需要手动点击「从章纲生成」按钮。这样设计是为了让用户有机会在生成线程前检查和调整章纲。

### Q2：为什么设置了3000字，但生成的内容超过4000字？

**A**：可能有以下原因：
1. `ChapterOutlineSchema` 的 `target_words` 默认值是4000
2. 需要检查章节大纲是否正确使用了用户设置的字数
3. 可以在代码层面强制使用用户设置的字数

### Q3：线程保存后刷新页面显示"暂无线程"？

**A**：这是一个已知的序列化问题。修复方法：
1. 在 `write_world_state` 中正确处理枚举类型
2. 在 `read_world_state` 中正确转换 `ThreadType`

### Q4：如何自定义 AI 生成的风格？

**A**：可以通过以下方式：
1. 在创建书籍时设置 `style_guide` 参数
2. 在章纲的 `writing_notes` 中添加风格指导
3. 修改 `WriterAgent` 的提示词模板

---

## 附录：工具列表

| 工具 | 说明 | 位置 |
|------|------|------|
| **WriterAgent** | AI 写作代理 | `core/agents/__init__.py` |
| **ReviserAgent** | 内容修订代理 | `core/agents/__init__.py` |
| **AuditorAgent** | 内容审计代理 | `core/agents/__init__.py` |
| **QualityAgent** | 质量评估代理 | `core/agents/__init__.py` |
| **NarrativeEngine** | 叙事引擎 | `core/narrative/__init__.py` |
| **WritingPipeline** | 写作流水线 | `core/pipeline.py` |

---

**文档版本**：v1.0  
**创建日期**：2026-06-05  
**适用范围**：Dramatica Flow 学习与使用