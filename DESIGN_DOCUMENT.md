# Dramatica-Flow 优化设计文档

> **设计原则：先设计，后实现**
>
> *本文档详细说明基于Dramatica叙事理论的功能增强方案*

---

## 1. 项目概述

### 1.1 背景
Dramatica-Flow是一个AI辅助的长篇小说创作工具，目前已具备：
- 世界观系统（角色、地点、势力、规则）
- 多线叙事支持（主线、支线、并行线、闪回线）
- 钩子系统（伏笔管理）
- AI写作流水线

### 1.2 优化目标
基于Dramatica叙事理论，增强以下功能：
1. **线程系统** - 支持Dramatica四条故事线分类
2. **钩子系统** - 大幅增强钩子管理和审计功能
3. **主题系统** - 添加明确的主题和核心矛盾设定
4. **API扩展** - 支持新功能的后端接口

---

## 2. Dramatica理论映射

### 2.1 四条故事线（Four Throughlines）

| Dramatica概念 | 说明 | 现有功能 | 拟增强 |
|---|---|---|---|
| **OS (Objective Story)** | 客观主线 - 外部大世界危机 | 主线(ThreadType.MAIN) | ✅ 添加story_line_type字段 |
| **MC (Main Character)** | 主角线 - 内在执念与成长 | 主角角色配置 | ✅ 关联story_line_type |
| **IC (Influence Character)** | 影响者线 - 对立价值观 | 导师/反派角色 | ✅ 关联story_line_type |
| **RS (Relationship Story)** | 关系线 - 双人羁绊与成长 | 配角、情侣线 | ✅ 关联story_line_type |

### 2.2 八类功能角色

| 功能角色 | 戏剧作用 | 现有实现 |
|---|---|---|
| 主角 | 核心视角、经历变化 | CharacterRole.PROTAGONIST |
| 影响者 | 对立价值观、挑战主角 | CharacterRole.GUARDIAN/ANTAGONIST |
| 助手 | 忠诚支持、辅助主角 | CharacterRole.SIDEKICK |
| 对手 | 直接阻碍、制造冲突 | CharacterRole.ANTAGONIST |
| 信使 | 传递信息、推动剧情 | ⚠️ 待评估 |
| 门卫 | 考验主角、筛选准入 | ⚠️ 待评估 |
| 小丑 | 提供喜剧、缓解紧张 | ⚠️ 待评估 |
| 反派 | 终极威胁、具象矛盾 | CharacterRole.ANTAGONIST |

**决策：** 暂不添加新角色类型，保持现有8种角色定位。

---

## 3. 详细设计

### 3.1 线程系统增强

#### 3.1.1 新增 StoryLineType 枚举
**文件：** `core/types/narrative.py`

```python
class StoryLineType(str, Enum):
    """Dramatica四条故事线类型"""
    OS = "os"               # 客观主线（外部大世界危机）
    MC = "mc"               # 主角线（内在执念与成长）
    IC = "ic"               # 影响者线（对立价值观）
    RS = "rs"               # 关系线（双人羁绊）
```

#### 3.1.2 更新 NarrativeThread 类
**文件：** `core/types/narrative.py`

```python
@dataclass
class NarrativeThread:
    id: str
    name: str
    type: ThreadType = ThreadType.MAIN

    # 【新增】Dramatica故事线类型
    story_line_type: StoryLineType = StoryLineType.OS

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

#### 3.1.3 更新 StateManager
**文件：** `core/state/__init__.py`

在 `read_world_state()` 中添加对 `story_line_type` 的解析：

```python
# 在重建线程时
thread = NarrativeThread(
    ...
    story_line_type=StoryLineType(t.get("story_line_type", "os")),
    ...
)
```

在 `create_thread()` 中更新：
```python
if existing:
    existing.story_line_type = thread.story_line_type  # 新增
    ...
```

新增故事线管理方法：
```python
def get_thread_by_storyline(self, story_line_type: str) -> list[NarrativeThread]:
    """获取特定故事线类型的所有线程"""
    state = self.read_world_state()
    return [t for t in state.threads if t.story_line_type.value == story_line_type]

def get_storyline_summary(self) -> dict:
    """获取四条故事线的汇总信息"""
    state = self.read_world_state()
    from ..types.narrative import StoryLineType

    summary = {}
    for sl_type in StoryLineType:
        threads = self.get_thread_by_storyline(sl_type.value)
        hooks = self.get_hooks_by_storyline(sl_type.value)
        active_count = len([t for t in threads if t.status == "active"])
        resolved_count = len([t for t in threads if t.status == "resolved"])
        open_hooks = [h for h in hooks if h.status == HookStatus.OPEN]
        resolved_hooks = [h for h in hooks if h.status == HookStatus.RESOLVED]

        summary[sl_type.value] = {
            "name": {
                "os": "客观主线（外部危机）",
                "mc": "主角线（内在执念）",
                "ic": "影响者线（对立价值观）",
                "rs": "关系线（双人羁绊）",
            }[sl_type.value],
            "thread_count": len(threads),
            "active_threads": active_count,
            "resolved_threads": resolved_count,
            "open_hooks": len(open_hooks),
            "resolved_hooks": len(resolved_hooks),
            "threads": [...]
        }
    return summary
```

---

### 3.2 钩子系统增强

#### 3.2.1 增强 Hook 类
**文件：** `core/types/narrative.py`

```python
@dataclass
class Hook:
    id: str
    type: HookType
    description: str
    planted_in_chapter: int
    expected_resolution_range: tuple[int, int]
    status: HookStatus = HookStatus.OPEN
    resolved_in_chapter: int | None = None
    tension_level: int = 50
    storylines: list[str] = field(default_factory=list)
    reminder: str = ""

    # 【新增字段】
    associated_events: list[str] = field(default_factory=list)      # 关联的事件ID
    associated_characters: list[str] = field(default_factory=list)  # 关联的角色
    priority_level: int = 3                                         # 优先级 1-5
    dependent_hooks: list[str] = field(default_factory=list)         # 依赖的钩子
    prerequisite_hooks: list[str] = field(default_factory=list)     # 前置钩子
    tags: list[str] = field(default_factory=list)                   # 自定义标签
    reminder_threshold: int = 3                                     # 提前多少章提醒
    resolved_description: str = ""                                  # 回收描述
    satisfaction_score: int | None = None                           # 回收满意度 0-100
    notes: str = ""                                                 # 管理员备注
```

#### 3.2.2 新增 StateManager 钩子管理方法
**文件：** `core/state/__init__.py`

```python
def get_hook_reminders(self, current_chapter: int) -> list[Hook]:
    """
    获取当前章节需要提醒的钩子列表
    包含：即将到期、已逾期、高优先级
    """
    state = self.read_world_state()
    reminders = []
    for hook in state.pending_hooks:
        if hook.status != HookStatus.OPEN:
            continue
        reminder_ch = hook.expected_resolution_range[1] - hook.reminder_threshold
        if current_chapter >= reminder_ch or current_chapter > hook.expected_resolution_range[1] or hook.priority_level >= 4:
            reminders.append(hook)
    return reminders

def get_overdue_hooks(self) -> list[Hook]:
    """获取所有逾期未回收的钩子"""
    state = self.read_world_state()
    current_ch = state.current_chapter
    return [h for h in state.pending_hooks
            if h.status == HookStatus.OPEN and current_ch > h.expected_resolution_range[1]]

def get_hooks_by_storyline(self, story_line_type: str) -> list[Hook]:
    """获取特定故事线的所有钩子"""
    state = self.read_world_state()
    return [h for h in state.pending_hooks if story_line_type in h.storylines]

def get_hooks_by_priority(self, min_priority: int = 3) -> list[Hook]:
    """获取高于指定优先级的开放钩子"""
    state = self.read_world_state()
    return [h for h in state.pending_hooks
            if h.status == HookStatus.OPEN and h.priority_level >= min_priority]

def update_hook(self, hook_id: str, status: HookStatus | None = None,
                tension_level: int | None = None, priority_level: int | None = None,
                resolved_description: str | None = None,
                satisfaction_score: int | None = None, notes: str | None = None):
    """更新钩子属性"""
    state = self.read_world_state()
    for hook in state.pending_hooks:
        if hook.id == hook_id:
            if status: hook.status = status
            if tension_level is not None: hook.tension_level = tension_level
            if priority_level is not None: hook.priority_level = priority_level
            if resolved_description: hook.resolved_description = resolved_description
            if satisfaction_score is not None: hook.satisfaction_score = satisfaction_score
            if notes: hook.notes = notes
            break
    self.write_world_state(state)

def resolve_hook_with_feedback(self, hook_id: str, chapter: int,
                               resolved_description: str, satisfaction_score: int):
    """带反馈的钩子回收"""
    state = self.read_world_state()
    hook = next((h for h in state.pending_hooks if h.id == hook_id), None)
    if hook:
        hook.status = HookStatus.RESOLVED
        hook.resolved_in_chapter = chapter
        hook.resolved_description = resolved_description
        hook.satisfaction_score = satisfaction_score
        self.write_world_state(state)

def get_hook_audit_report(self) -> dict:
    """生成钩子系统审计报告"""
    state = self.read_world_state()
    current_ch = state.current_chapter
    open_hooks = [h for h in state.pending_hooks if h.status == HookStatus.OPEN]
    resolved_hooks = [h for h in state.pending_hooks if h.status == HookStatus.RESOLVED]
    overdue_hooks = [h for h in open_hooks if current_ch > h.expected_resolution_range[1]]
    satisfaction_scores = [h.satisfaction_score for h in resolved_hooks if h.satisfaction_score is not None]
    avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else 0

    return {
        "total_hooks": len(state.pending_hooks),
        "open_count": len(open_hooks),
        "resolved_count": len(resolved_hooks),
        "overdue_count": len(overdue_hooks),
        "avg_satisfaction": round(avg_satisfaction, 1),
        "high_priority_open": len([h for h in open_hooks if h.priority_level >= 4]),
        "overdue_hooks": [
            {"id": h.id, "description": h.description,
             "planted": h.planted_in_chapter,
             "expected": h.expected_resolution_range}
            for h in overdue_hooks
        ],
    }
```

---

### 3.3 主题系统新增

#### 3.3.1 新增 ThemeType 枚举
**文件：** `core/types/narrative.py`

```python
class ThemeType(str, Enum):
    """故事主题类型"""
    JUSTICE = "justice"
    TRUTH = "truth"
    LOVE = "love"
    POWER = "power"
    SELF_DISCOVERY = "self_discovery"
    SACRIFICE = "sacrifice"
    TRUST = "trust"
    SURVIVAL = "survival"
    REDEMPTION = "redemption"
    IDENTITY = "identity"
```

#### 3.3.2 新增 StoryTheme 类
**文件：** `core/types/narrative.py`

```python
@dataclass
class StoryTheme:
    """
    故事主题定义（Dramatica核心）

    Dramatica认为故事是一次价值观的探索：
    - 主题提出问题
    - 论点（主角立场）尝试回答
    - 反论点（反派立场）提出反驳
    - 综合（结局）给出最终答案或升华
    """
    id: str
    core_question: str                          # 核心问题
    argument: str                               # 论点（主角立场）
    counter_argument: str                       # 反论点（对立立场）
    synthesis: str                              # 综合答案（结局升华）
    theme_type: ThemeType                       # 主题类型
    description: str = ""                       # 主题描述
    related_characters: list[str] = field(default_factory=list)
    related_threads: list[str] = field(default_factory=list)
    manifestation_range: tuple[int, int] = (1, 100)  # 主题展现章节范围
    intensity_curve: dict[int, int] = field(default_factory=dict)  # 主题强度曲线
    is_fulfilled: bool = False
    satisfaction_score: int | None = None
```

#### 3.3.3 新增 CoreConflict 类
**文件：** `core/types/narrative.py`

```python
@dataclass
class CoreConflict:
    """核心矛盾定义"""
    id: str
    name: str
    protagonist_flaw: str                   # 主角的错误执念
    objective_solution: str                 # 客观最优解
    description: str                        # 矛盾描述
    conflict_type: Literal["internal", "external", "both"] = "both"
    involved_characters: list[str] = field(default_factory=list)
    start_chapter: int = 1
    expected_resolution_chapter: int = 100
    is_resolved: bool = False
    resolution: str = ""
```

---

### 3.4 API接口扩展

#### 3.4.1 新增API端点
**文件：** `core/server.py`

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/api/books/{book_id}/storylines/summary` | 获取四条故事线汇总 |
| `GET` | `/api/books/{book_id}/storylines/{type}/threads` | 获取特定故事线的线程 |
| `GET` | `/api/books/{book_id}/hooks/audit` | 获取钩子审计报告 |
| `GET` | `/api/books/{book_id}/hooks/reminders` | 获取钩子提醒 |
| `GET` | `/api/books/{book_id}/hooks/overdue` | 获取逾期钩子 |
| `GET` | `/api/books/{book_id}/hooks` | 获取钩子列表（支持过滤） |

**代码示例：**

```python
@app.get("/api/books/{book_id}/storylines/summary")
def get_storylines_summary(book_id: str):
    """获取Dramatica四条故事线的汇总信息"""
    sm = _sm(book_id)
    return sm.get_storyline_summary()

@app.get("/api/books/{book_id}/storylines/{storyline_type}/threads")
def get_threads_by_storyline(book_id: str, storyline_type: str):
    """获取特定故事线类型的所有线程"""
    sm = _sm(book_id)
    threads = sm.get_thread_by_storyline(storyline_type)
    return _dc_to_dict(threads)

@app.get("/api/books/{book_id}/hooks/audit")
def get_hooks_audit(book_id: str):
    """获取钩子系统审计报告"""
    sm = _sm(book_id)
    return sm.get_hook_audit_report()

@app.get("/api/books/{book_id}/hooks/reminders")
def get_hooks_reminders(book_id: str):
    """获取当前章节需要提醒的钩子列表"""
    sm = _sm(book_id)
    ws = sm.read_world_state()
    reminders = sm.get_hook_reminders(ws.current_chapter)
    return _dc_to_dict(reminders)

@app.get("/api/books/{book_id}/hooks/overdue")
def get_overdue_hooks(book_id: str):
    """获取所有逾期未回收的钩子"""
    sm = _sm(book_id)
    overdue = sm.get_overdue_hooks()
    return _dc_to_dict(overdue)

@app.get("/api/books/{book_id}/hooks")
def get_hooks(book_id: str, storyline: str | None = None, priority: int | None = None):
    """获取钩子列表（支持按故事线和优先级过滤）"""
    sm = _sm(book_id)
    if storyline:
        hooks = sm.get_hooks_by_storyline(storyline)
    elif priority:
        hooks = sm.get_hooks_by_priority(priority)
    else:
        ws = sm.read_world_state()
        hooks = ws.pending_hooks
    return _dc_to_dict(hooks)
```

#### 3.4.2 更新现有API
更新 `auto-generate-threads` 以支持设置 `story_line_type`：
```python
# 根据角色定位自动推断故事线类型
if char.role == CharacterRole.PROTAGONIST:
    story_line_type = StoryLineType.MC
elif char.role in [CharacterRole.ANTAGONIST, CharacterRole.GUARDIAN]:
    story_line_type = StoryLineType.IC
elif char.role == CharacterRole.LOVE_INTEREST:
    story_line_type = StoryLineType.RS
else:
    story_line_type = StoryLineType.OS
```

---

## 4. 实施计划

### 4.1 优先级划分

| 优先级 | 模块 | 预计工时 |
|---|---|---|
| **P0** | ThreadSystem：StoryLineType + 更新StateManager | 1h |
| **P0** | HookSystem：增强Hook类 + 钩子管理方法 | 2h |
| **P1** | API扩展：新增7个端点 + 更新auto-generate | 1.5h |
| **P1** | ThemeSystem：新增ThemeType/StoryTheme/CoreConflict | 1h |
| **P2** | 前端界面更新（线程/钩子视图） | 3h |

**总工时：** 约8.5小时

### 4.2 依赖关系

```
ThreadSystem
   ↓
HookSystem
   ↓
API扩展
   ↓
ThemeSystem (可选)
   ↓
前端更新 (可选)
```

---

## 5. 风险与注意事项

### 5.1 数据兼容性
- 现有`world_state.json`中的线程缺少`story_line_type`字段
- **解决方案：** 默认设为`StoryLineType.OS`，向后兼容

### 5.2 钩子现有数据
- 现有钩子缺少`priority_level`等字段
- **解决方案：** 设置合理默认值，无需迁移

### 5.3 性能影响
- 新增加的审计和查询方法影响可忽略
- **验证：** 建议添加性能测试（100+钩子时）

---

## 6. 验收标准

### 6.1 功能验收
- [ ] 线程可以标记为OS/MC/IC/RS类型
- [ ] 可以查询特定故事线的所有线程
- [ ] 钩子系统有完整的审计报告
- [ ] 钩子提醒功能正常工作
- [ ] API返回格式正确

### 6.2 质量验收
- [ ] 无类型错误（mypy）
- [ ] 无语法错误
- [ ] 代码注释完整
- [ ] 文档同步更新

---

## 7. 后续建议

### 7.1 短期（1-2周）
- 添加主题设定UI
- 钩子管理界面增强

### 7.2 中期（1月）
- 将Dramatica四条故事线融入AI写作提示
- 主题一致性审计功能

### 7.3 长期（3月+）
- 基于StoryTheme的自动章纲生成
- 完整的Dramatica结构分析报告

---

**文档版本：** v1.0
**编写日期：** 2026-06-06
**下一步：** 等待用户确认后开始实施
