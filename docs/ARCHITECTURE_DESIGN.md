
# Dramatica-Flow 架构设计文档

**版本**: v0.1.0  
**日期**: 2026-06-01  
**作者**: Dramatica-Flow 开发团队  
**状态**: 正式版

---

## 目录

1. [引言](#1-引言)
2. [系统整体架构](#2-系统整体架构)
3. [模块划分与职责](#3-模块划分与职责)
4. [技术栈选型说明](#4-技术栈选型说明)
5. [核心组件设计](#5-核心组件设计)
6. [接口定义](#6-接口定义)
7. [数据流程图](#7-数据流程图)
8. [部署架构](#8-部署架构)
9. [安全策略](#9-安全策略)
10. [扩展性设计](#10-扩展性设计)
11. [附录](#11-附录)

---

## 1. 引言

### 1.1 项目概述

Dramatica-Flow 是一款基于 **Dramatica 叙事理论**构建的 AI 长篇小说创作系统。与普通 AI 写作工具不同，它将小说创作抽象为可量化、可追踪、可审计的工程流程，通过因果链管理、情感弧线追踪、伏笔系统、关系网络等核心机制，确保 AI 生成的内容具有真正的叙事逻辑和内在一致性。

### 1.2 设计目标

| 目标 | 描述 |
|------|------|
| **叙事质量保障** | 通过三层审计机制确保输出内容符合叙事理论 |
| **状态一致性** | 世界状态在章节间正确累积，永不丢失 |
| **多线叙事支持** | 支持主线、支线、并行线、闪回线的复杂叙事结构 |
| **可扩展性** | 支持多种 LLM 后端，易于扩展新功能 |
| **易用性** | 提供 Web UI 和 CLI 两种交互方式 |

### 1.3 核心价值主张

| 维度 | 普通 AI 写作工具 | Dramatica-Flow |
|------|------------------|----------------|
| 叙事逻辑 | 逐段生成，缺乏全局因果 | **强制建模因果链** |
| 角色一致性 | 容易 OOC（性格崩塌） | **信息边界系统** |
| 长篇连贯性 | 前后矛盾频发 | **世界状态快照 + 真相文件** |
| 伏笔管理 | 无 | **伏笔生命周期管理** |
| 多线叙事 | 无 | **全局时间轴 + 线程调度** |

---

## 2. 系统整体架构

### 2.1 架构层次图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Web UI 层                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │
│  │ 总览面板        │  │ 故事配置        │  │ 大纲管理        │       │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤       │
│  │ 章节创作        │  │ 故事追踪        │  │ 时间线          │       │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘       │
│                              │                                       │
├───────────────────────────────┼───────────────────────────────────────┤
│                          REST API 层                                 │
│                    FastAPI · 50+ 端点 · Pydantic 校验                 │
│                              │                                       │
├───────────────────────────────┼───────────────────────────────────────┤
│                          Agent 管线层                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ 建筑师  │──▶│ 写手    │──▶│ 审计员  │──▶│ 修订者  │  │ 摘要生成│    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │
│                              │                                       │
├───────────────────────────────┼───────────────────────────────────────┤
│                          叙事引擎层                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│  │ 因果链引擎  │ │ 伏笔系统    │ │ 情感弧线    │ │ 关系网络    │     │
│  ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤     │
│  │ 多线叙事    │ │ 信息边界    │ │ 世界状态    │ │ 时间轴      │     │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │
│                              │                                       │
├───────────────────────────────┼───────────────────────────────────────┤
│                          LLM 抽象层                                  │
│                DeepSeek · Ollama · OpenAI 兼容协议                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 架构风格

- **分层架构**：清晰的五层架构，职责分离
- **管道过滤器模式**：写作管线采用流水线处理模式
- **状态机模式**：世界状态管理采用状态机模式
- **策略模式**：LLM Provider 支持多种后端切换

---

## 3. 模块划分与职责

### 3.1 模块清单

| 模块 | 路径 | 职责描述 |
|------|------|----------|
| **CLI** | `cli/main.py` | 命令行工具，提供 init/book/setup/write/audit 等命令 |
| **Agent 层** | `core/agents/` | 五大 Agent：建筑师、写手、审计员、修订者、摘要生成 |
| **叙事引擎** | `core/narrative/` | 大纲生成、章纲展开、因果链提取、故事圈管理 |
| **状态管理** | `core/state/` | 真相文件读写、世界状态管理、快照回滚 |
| **类型定义** | `core/types/` | 角色、事件、因果链、伏笔、线程等数据类型 |
| **LLM 抽象** | `core/llm/` | 多 Provider 支持、JSON 解析、重试机制 |
| **验证器** | `core/validators/` | 写后验证（字数、禁忌词、格式） |
| **配置加载** | `core/setup.py` | 从 JSON 文件加载角色、世界、事件配置 |
| **Web 服务** | `core/server.py` | FastAPI 后端，提供 50+ REST API 端点 |

### 3.2 核心模块职责详解

#### 3.2.1 Agent 层

| Agent | 职责 | 核心输出 |
|-------|------|----------|
| **ArchitectAgent** | 分析章纲和世界状态，生成写作蓝图 | `ArchitectBlueprint` |
| **WriterAgent** | 根据蓝图生成正文和写后结算表 | `WriterOutput` |
| **AuditorAgent** | 三层审计：大纲对齐、人设逻辑、节奏合规 | `AuditReport` |
| **ReviserAgent** | 根据审计结果修订正文 | `ReviseResult` |
| **SummaryAgent** | 生成章节摘要用于上下文传递 | 结构化摘要 |

#### 3.2.2 叙事引擎

| 组件 | 职责 |
|------|------|
| **故事大纲生成** | 基于三幕式结构生成完整故事大纲 |
| **章纲展开** | 将序列展开为具体章节大纲 |
| **因果链提取** | 从正文中提取因果关系 |
| **Dan Harmon 8步** | 章节节奏指导 |
| **四大故事线管理** | 主角成长、反派博弈、关系拉扯、外部事件 |

#### 3.2.3 状态管理

| 组件 | 职责 |
|------|------|
| **真相文件系统** | 8 种真相文件的读写管理 |
| **世界状态** | 角色位置、关系、情感、伏笔、因果链的内存状态 |
| **快照机制** | 章节快照创建与回滚 |
| **线程管理** | 多线叙事的线程创建、更新、删除 |

---

## 4. 技术栈选型说明

### 4.1 技术栈清单

| 层次 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 语言 | Python | 3.11+ | 成熟稳定，AI 生态丰富，异步支持良好 |
| Web 框架 | FastAPI | 0.110+ | 高性能，自动文档，Pydantic 集成 |
| 数据校验 | Pydantic | 2.0+ | 严格类型校验，LLM 输出校验 |
| CLI 框架 | Typer | 0.12+ | 现代化 CLI 开发，Rich 集成 |
| 终端美化 | Rich | 13.0+ | 美观的终端输出 |
| LLM SDK | OpenAI | 1.30+ | 兼容 DeepSeek、Ollama 等多后端 |
| 测试框架 | pytest | 8.0+ | 成熟的 Python 测试框架 |
| 异步测试 | pytest-asyncio | 0.23+ | 异步代码测试支持 |

### 4.2 LLM 后端支持

| Provider | 配置方式 | 适用场景 |
|----------|----------|----------|
| **DeepSeek** | API Key | 效果最佳，需付费 |
| **Ollama** | 本地部署 | 完全免费，隐私保护 |
| **OpenAI** | API Key | 标准接口，通用性强 |
| **其他兼容** | 自定义配置 | 支持任意 OpenAI 兼容接口 |

### 4.3 前端技术

- **框架**: 原生 HTML/CSS/JS（零构建依赖）
- **优势**: 无需 Node.js，开箱即用，部署简单

---

## 5. 核心组件设计

### 5.1 写作管线（核心流程）

#### 5.1.1 管线流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    单章写作管线流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  快照备份 ──▶ 读取上下文 ──▶ 建筑师规划 ──▶ 写手写章 ──▶ 写后验证   │
│                                                              │    │
│                                                              ▼    │
│  更新状态 ◀── 因果链提取 ◀── 摘要生成 ◀── 修订闭环 ◀── 审计员审计   │
│                                                              │    │
│                                                              ▼    │
│                                                   时间轴记录 + 线程更新  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 5.1.2 管线组件交互

```python
class WritingPipeline:
    MAX_REVISE_ROUNDS = 2  # 最多修订 2 轮
    
    def run(self, chapter_outline):
        # 1. 快照备份
        self.sm.create_snapshot(ch - 1)
        
        # 2. 读取上下文（世界状态、伏笔、因果链、情感弧线）
        world_context = self.sm.read_truth_bundle([CURRENT_STATE, CHARACTER_MATRIX])
        
        # 3. 建筑师规划蓝图
        blueprint = self.architect.plan_chapter(chapter_outline, world_context, ...)
        
        # 4. 写手写章
        writer_output = self.writer.write_chapter(blueprint, ...)
        
        # 5. 写后验证（零 LLM）
        val_result = self.validator.validate(writer_output.content)
        
        # 6. 审计 → 修订闭环
        audit_report = self.auditor.audit_chapter(...)
        while not audit_report.passed and revision_rounds < MAX_REVISE_ROUNDS:
            revise_result = self.reviser.revise(...)
            revision_rounds += 1
        
        # 7. 因果链提取
        causal_links = self.engine.extract_causal_links(...)
        
        # 8. 摘要生成
        summary = self.summary_agent.generate_summary(...)
        
        # 9. 状态更新
        self._apply_settlement(writer_output.settlement)
        
        # 10. 时间轴记录 + 线程状态更新
        self._record_timeline_events(...)
```
[代码位置](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/pipeline.py#L53)

### 5.2 因果链引擎

#### 5.2.1 数据结构

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
[代码位置](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/state.py#L109)

#### 5.2.2 因果链提取流程

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 截取章节内容 | 前 4000 字 + 后 2000 字 |
| 2 | 调用 LLM 分析 | 提取 2-5 条关键因果链 |
| 3 | 结构校验 | Pydantic 验证格式 |
| 4 | 存储 | 写入 world_state.json 和 causal_chain.md |

### 5.3 伏笔系统

#### 5.3.1 伏笔类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `FORESHADOW` | 暗线铺垫 | 神秘玉佩 |
| `PROMISE` | 叙事承诺 | 三年之约 |
| `MYSTERY` | 未解之谜 | 消失的灵力 |
| `CONFLICT` | 未解决矛盾 | 势力暗战 |
| `TWIST` | 反转伏笔 | 身份反转 |
| `CHARACTER_SECRET` | 角色秘密 | 隐藏身份 |

#### 5.3.2 伏笔生命周期

```
埋设(planted_in_chapter) ──▶ 推进(ADVANCED) ──▶ 回收(RESOLVED)
        │                           │
        └──────────▶ 逾期预警(overdue) ◀──────────┘
                        │
                        ▼
                   放弃(ABANDONED)
```

### 5.4 多线叙事系统

#### 5.4.1 线程类型

| 类型 | 权重 | 说明 |
|------|------|------|
| `MAIN` | 1.0 | 主线，核心故事线 |
| `SUBPLOT` | 0.7 | 支线，次要故事线 |
| `PARALLEL` | 0.8 | 并行线，同时发生 |
| `FLASHBACK` | 0.5 | 闪回线，回忆内容 |

#### 5.4.2 线程数据结构

```python
@dataclass
class NarrativeThread:
    id: str                              # 线程唯一标识
    name: str                            # 线程名称
    type: ThreadType                     # 线程类型
    pov_character_id: str = ""           # 视角角色
    character_ids: list[str] = field(default_factory=list)
    goal: str = ""                       # 线程目标
    start_chapter: int = 1               # 起始章节
    last_active_chapter: int = 0         # 上次活跃章节
    weight: float = 1.0                  # 篇幅权重
    status: Literal["active", "dormant", "resolved", "merged"] = "active"
    hook_score: int = 80                 # 期待感指数(0-100)
```
[代码位置](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/types/narrative.py#L191)

---

## 6. 接口定义

### 6.1 API 端点总览

#### 6.1.1 书籍管理

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/books` | 获取书籍列表 |
| POST | `/api/books` | 创建书籍 |
| GET | `/api/books/{id}` | 获取书籍详情 |
| DELETE | `/api/books/{id}` | 删除书籍 |

#### 6.1.2 故事配置

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/books/{id}/setup/status` | 获取配置状态 |
| POST | `/api/books/{id}/setup/init` | 初始化配置模板 |
| GET | `/api/books/{id}/setup/{type}` | 获取配置（角色/世界/事件） |
| PUT | `/api/books/{id}/setup/{type}` | 更新配置 |
| POST | `/api/books/{id}/setup/load` | 加载配置到世界状态 |

#### 6.1.3 AI 创作核心

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/books/{id}/ai-generate/outline` | AI 生成故事大纲 |
| POST | `/api/books/{id}/ai-continue/outline` | AI 续写故事大纲 |
| POST | `/api/books/{id}/ai-generate/chapter-outlines` | AI 生成章节大纲 |
| POST | `/api/books/{id}/continue-writing` | 续写章节大纲（联动故事大纲） |
| POST | `/api/books/{id}/ai-generate/chapter-content` | AI 生成章节内容 |
| POST | `/api/books/{id}/ai-rewrite-segment` | AI 重写指定段落 |

#### 6.1.4 故事追踪

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/books/{id}/causal-chain` | 获取因果链 |
| GET | `/api/books/{id}/emotional-arcs` | 获取情感弧线 |
| GET | `/api/books/{id}/hooks` | 获取伏笔列表 |
| GET | `/api/books/{id}/relationships` | 获取关系网络 |
| GET | `/api/books/{id}/threads` | 获取叙事线程 |
| GET | `/api/books/{id}/timeline` | 获取全局时间轴 |

### 6.2 请求/响应示例

#### 6.2.1 创建书籍

**请求**:
```http
POST /api/books
Content-Type: application/json

{
    "title": "我的玄幻小说",
    "genre": "玄幻",
    "chapters": 90,
    "words": 4000,
    "forbidden": "敏感词1,敏感词2",
    "style_guide": "古风仙侠风格"
}
```

**响应**:
```json
{
    "ok": true,
    "book_id": "我的玄幻小说",
    "title": "我的玄幻小说"
}
```

#### 6.2.2 AI 生成章节内容

**请求**:
```http
POST /api/books/{id}/ai-generate/chapter-content
Content-Type: application/json

{
    "chapter_number": 1,
    "outline": {...},
    "world_context": "..."
}
```

**响应**:
```json
{
    "ok": true,
    "chapter_number": 1,
    "content": "第一章 退婚...",
    "word_count": 4200,
    "audit_passed": true,
    "revision_rounds": 0,
    "causal_links": 3
}
```

### 6.3 CLI 命令接口

| 命令 | 说明 | 示例 |
|------|------|------|
| `df init <name>` | 初始化项目 | `df init my_project` |
| `df book` | 创建新书 | `df book --title "小说名" --genre "玄幻"` |
| `df setup init-templates` | 初始化配置模板 | `df setup init-templates my_book` |
| `df setup load` | 加载配置 | `df setup load my_book` |
| `df write` | 写下一章 | `df write my_book --count 5` |
| `df audit` | 审计章节 | `df audit my_book 5` |
| `df revise` | 修订章节 | `df revise my_book 5` |
| `df status` | 查看状态 | `df status my_book` |
| `df export` | 导出书籍 | `df export my_book` |
| `df threads` | 线程管理 | `df threads list my_book` |

---

## 7. 数据流程图

### 7.1 书籍创建流程

```
用户 ──▶ CLI/Web ──▶ server.py ──▶ StateManager.init()
                                           │
                                           ▼
                              ┌──────────────────────┐
                              │ 创建目录结构          │
                              │ books/{book_id}/     │
                              │   ├── state/        │
                              │   ├── snapshots/    │
                              │   └── chapters/     │
                              └──────────────────────┘
                                           │
                                           ▼
                              ┌──────────────────────┐
                              │ 初始化配置文件        │
                              │ - config.json        │
                              │ - world_state.json   │
                              │ - truth files        │
                              └──────────────────────┘
```

### 7.2 单章写作流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                      单章写作文档流                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  chapter_outlines.json ──▶ ArchitectAgent ──▶ blueprint (内存)     │
│         │                                    │                     │
│         │                                    ▼                     │
│         │                          WriterAgent                     │
│         │                                │                        │
│         │                                ▼                        │
│         │                     chapter_{n}_draft.md                 │
│         │                                │                        │
│         │                                ▼                        │
│         │                     AuditorAgent ──▶ audit_report       │
│         │                                │                        │
│         │                                ▼                        │
│         │                     ReviserAgent (如需要)                │
│         │                                │                        │
│         │                                ▼                        │
│         │                     chapter_{n}_final.md                 │
│         │                                │                        │
│         │          ┌─────────────────────┼─────────────────────┐    │
│         ▼          ▼                     ▼                     ▼    │
│  chapter_summaries.md   causal_chain.md   emotional_arcs.md   world_state.json
│                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.3 状态更新流程

```
写后结算表(WriterOutput.settlement)
            │
            ├─▶ character_position_changes ──▶ world_state.character_positions
            │
            ├─▶ emotional_changes ──▶ world_state.emotional_snapshots
            │                         └─▶ emotional_arcs.md
            │
            ├─▶ relationship_changes ──▶ world_state.relationships
            │
            ├─▶ new_hooks ──▶ world_state.pending_hooks
            │                 └─▶ pending_hooks.md
            │
            ├─▶ resolved_hooks ──▶ world_state.pending_hooks (更新状态)
            │
            └─▶ info_revealed ──▶ world_state.known_info
                                  └─▶ character_matrix.md
```

---

## 8. 部署架构

### 8.1 部署拓扑图

```
┌────────────────────────────────────────────────────────────────────┐
│                        开发/单机部署                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐                                             │
│  │    客户端浏览器   │                                             │
│  │  http://localhost:8766                                       │
│  └────────┬────────┘                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                             │
│  │    Uvicorn      │                                             │
│  │    (ASGI Server)│                                             │
│  │    :8766        │                                             │
│  └────────┬────────┘                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐    ┌─────────────────┐                      │
│  │   FastAPI       │    │    LLM 后端      │                      │
│  │   core/server.py│    │  DeepSeek/Ollama │                      │
│  └────────┬────────┘    └─────────────────┘                      │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐                 │
│  │              文件系统存储                    │                 │
│  │  books/                                    │                 │
│  │    ├── book1/                              │                 │
│  │    │   ├── state/                          │                 │
│  │    │   ├── snapshots/                      │                 │
│  │    │   └── chapters/                       │                 │
│  │    └── book2/                              │                 │
│  └─────────────────────────────────────────────┘                 │
│                                                                  │
└────────────────────────────────────────────────────────────────────┘
```

### 8.2 目录结构

```
dramatica-flow/
├── core/                           # 核心引擎
│   ├── agents/                     # AI Agent
│   ├── llm/                        # LLM 抽象层
│   ├── narrative/                  # 叙事引擎
│   ├── state/                      # 状态管理
│   ├── types/                      # 数据类型
│   ├── validators/                 # 验证器
│   ├── pipeline.py                 # 写作管线
│   └── server.py                   # FastAPI 服务
├── cli/                            # 命令行工具
│   └── main.py                     # CLI 入口
├── books/                          # 书籍数据（运行时生成）
│   └── {book_id}/
│       ├── state/
│       ├── snapshots/
│       └── chapters/
├── templates/                      # 配置模板
├── docs/                           # 文档
├── dramatica_flow_web_ui.html      # Web UI
├── dramatica_flow_timeline.html    # 时间线界面
├── .env                            # 环境变量
└── pyproject.toml                  # 项目配置
```

### 8.3 启动方式

#### 8.3.1 开发模式

```bash
# 启动开发服务器
python -m uvicorn core.server:app --reload --port 8766

# 访问 Web UI
# http://localhost:8766
```

#### 8.3.2 生产模式

```bash
# 使用 Gunicorn（推荐）
gunicorn -w 4 -k uvicorn.workers.UvicornWorker core.server:app --bind 0.0.0.0:8766

# 或使用 Uvicorn
uvicorn core.server:app --host 0.0.0.0 --port 8766
```

---

## 9. 安全策略

### 9.1 输入验证

| 验证类型 | 实现位置 | 说明 |
|----------|----------|------|
| **Pydantic 校验** | 所有 API 请求模型 | 严格的类型和格式校验 |
| **JSON 格式校验** | `core/setup.py` | 配置文件 JSON 解析校验 |
| **长度限制** | `core/server.py` | 防止超大请求 |
| **路径遍历防护** | `core/server.py` | 限制文件访问路径 |

### 9.2 敏感信息保护

| 措施 | 说明 |
|------|------|
| **API Key 环境变量** | 密钥存储在 `.env` 文件，不提交版本控制 |
| **日志脱敏** | 日志中不记录完整密钥 |
| **禁止词过滤** | 用户自定义禁止词列表，写作时自动过滤 |

### 9.3 资源访问控制

| 措施 | 说明 |
|------|------|
| **目录隔离** | 每个书籍独立目录，防止越权访问 |
| **模板白名单** | 仅允许访问指定模板文件 |
| **文件类型限制** | 仅允许 `.md`、`.json` 文件操作 |

### 9.4 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| **LLM 连接失败** | 重试机制（最多 3 次） |
| **JSON 解析失败** | 自动修复或优雅降级 |
| **文件不存在** | 友好的错误提示 |
| **参数错误** | 详细的错误信息和修复建议 |

---

## 10. 扩展性设计

### 10.1 LLM Provider 扩展

系统支持通过配置切换不同的 LLM 后端：

```python
def create_provider(config=None, provider_type=None):
    """
    从环境变量或显式配置创建 Provider。
    支持：deepseek、ollama、openai、自定义
    """
    if provider_type == "ollama":
        return OllamaProvider(config)
    # 默认使用 DeepSeek（OpenAI 兼容）
    return DeepSeekProvider(config)
```
[代码位置](file:///d:/owned/ai/xiaoshuo/dramatica-flow/core/llm/__init__.py#L445)

### 10.2 新增 Agent 扩展

系统采用插件式设计，新增 Agent 只需：
1. 实现 Agent 类
2. 在 `WritingPipeline` 中集成
3. 配置对应的 LLM 参数

### 10.3 数据类型扩展

新增数据类型只需：
1. 在 `core/types/` 中定义新的 dataclass
2. 在 `WorldState` 中添加对应字段
3. 更新 `StateManager` 的读写逻辑

### 10.4 API 扩展

新增 API 端点只需：
1. 在 `core/server.py` 中添加路由
2. 定义请求/响应模型
3. 实现业务逻辑

### 10.5 未来扩展方向

| 扩展方向 | 说明 |
|----------|------|
| **协作编辑** | 支持多人同时编辑同一书籍 |
| **版本控制** | Git 风格的版本管理 |
| **移动端适配** | 移动端 Web 界面优化 |
| **插件系统** | 支持第三方插件扩展 |
| **多语言支持** | 支持英文等其他语言 |

---

## 11. 附录

### 11.1 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.0 | 2026-06-01 | 初始版本 |

### 11.2 参考文档

- [Dramatica Theory](https://dramatica.com/)
- [Dan Harmon Story Circle](https://channel101.fandom.com/wiki/Story_Circle)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 11.3 术语表

| 术语 | 定义 |
|------|------|
| **因果链** | 事件之间的因果关系记录 |
| **伏笔** | 叙事中的线索，需在后续回收 |
| **信息边界** | 角色只能知道亲眼所见的信息 |
| **真相文件** | 存储世界状态的 Markdown 文件 |
| **写后结算表** | 章节对世界状态的所有改变 |
| **线程** | 多线叙事中的独立故事线 |

---

**文档结束**
