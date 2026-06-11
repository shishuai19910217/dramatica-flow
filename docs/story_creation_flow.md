
# 小说创作流程完整指南

## 一、整体流程概览

```
创建书籍 → 世界观生成 → 故事大纲生成 → 章节大纲生成
```

---

## 二、各阶段详细说明

### 1. 创建书籍

**任务**：设置书籍基本信息

**输入参数**：
- 书名
- 题材（都市/玄幻/科幻/历史/悬疑/仙侠/言情/游戏/无限流等）
- 目标章数
- 写作风格

**生成数据**：
- 项目目录结构（如 `data/books/书名/`）

---

### 2. 世界观生成

**任务**：构建故事世界基础设定

**生成文件**：

| 文件 | 内容 | 数量要求 |
|------|------|---------|
| `setup/characters.json` | 角色列表（姓名、性格、背景等） | 3-6个 |
| `setup/world.json` | 地点、势力、世界规则 | 地点4-8个，势力2-4个，规则2-5个 |
| `setup/events.json` | 种子事件 | 5-10个，覆盖三幕结构 |

**种子事件结构**：
```json
{
  "id": "evt_001",
  "name": "事件名称",
  "description": "事件描述",
  "suggested_act": 1,
  "suggested_function": "inciting_incident",
  "characters_involved": ["char_001"],
  "dramatic_question": "这个事件引发的戏剧性疑问"
}
```

**戏剧功能类型**：
- `inciting_incident`：激励事件
- `turning_point`：转折点
- `climax`：高潮
- `resolution`： Resolution
- `setup`：铺垫
- `midpoint`：中点

---

### 3. 故事大纲生成

**任务**：规划故事整体结构和关键节点

**生成文件**：`outline.json`

**核心数据结构**：
```json
{
  "sequences": [
    {
      "estimated_scenes": 10,
      "key_events": ["事件1", "事件2", ...],
      "summary": "序列摘要",
      "narrative_goal": "叙事目标",
      "dramatic_function": "setup"
    }
  ]
}
```

**关键要求**：
- `key_events` 数量 **必须等于** `estimated_scenes`
- 如果AI生成不足，系统会自动补充

---

### 4. 章节大纲生成

**任务**：为每章生成具体内容框架

**生成文件**：`chapters/chapter_xxx.json`

**章节数据结构**：
```json
{
  "title": "第1章 觉醒危机",
  "summary": "章节摘要内容",
  "dramatic_function": "setup",
  "story_circle_step": 1
}
```

**事件获取策略（5层）**：

```
章节大纲生成
    ├──→ 1. 优先使用 key_events（质量最高）
    ├──→ 2. 补充预定义词汇库（按题材）
    ├──→ 3. AI增强生成（仅在必要时）
    ├──→ 4. 兜底策略（关键词+序号）
    └──→ 5. 循环偏移分配（确保每批不同）
```

---

## 三、事件类型演变路径

```
种子事件（5-10个，世界观阶段）
    ↓
key_events（每个序列 estimated_scenes 个，故事大纲阶段）
    ↓
derived_events（组合后约30+个，章节大纲阶段）
    ↓
每章事件种子（循环偏移分配，确保独特）
```

---

## 四、文件结构总览

```
data/books/书名/
├── setup/
│   ├── characters.json    # 角色数据
│   ├── world.json         # 世界设定（地点、势力、规则）
│   └── events.json        # 种子事件
├── outline.json           # 故事大纲
└── chapters/
    ├── chapter_001.json   # 章节1
    ├── chapter_002.json   # 章节2
    └── ...
```

---

## 五、关键设计原则

### 1. 质量优先原则
- 优先使用高质量的 `key_events`
- AI增强仅在必要时调用

### 2. 多样性保证
- 循环偏移分配确保每批事件不同
- 严格去重逻辑

### 3. 题材适配
- 按题材选择预定义词汇库
- 确保事件类型符合世界观

### 4. 稳定性保障
- 多层兜底策略
- AI失败时自动降级

---

## 六、常见问题

### Q1：为什么章节标题会重复？
**原因**：`key_events` 数量不足，导致事件种子重复使用  
**解决方案**：强制要求 `key_events` 数量 = `estimated_scenes`

### Q2：预定义词汇库何时使用？
**触发条件**：当 `key_events` 数量 < 章节数时自动补充

### Q3：AI增强生成何时调用？
**触发条件**：当 `key_events` 和预定义词汇库都不足时调用

---

## 七、技术要点

### 性能优化
- 预定义词汇库减少AI调用次数
- 按需AI增强，避免不必要的API调用

### 容错机制
- AI调用失败时静默跳过
- 使用兜底策略确保流程不中断

### 扩展性设计
- 题材分类词汇库可轻松扩展
- 支持配置化管理
