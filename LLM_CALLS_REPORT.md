
# 项目 LLM 调用全面排查报告

生成时间: 2026-06-07

---

## 一、总览

项目: 戏剧性叙事创作系统 (Dramatica-Flow)

| 统计 | 数量 |
|------|------|
| 总扫描文件数 | 19 个 Python 文件 |
| 涉及 LLM 调用核心模块数 | 4 个 |
| 总 LLM 调用总数 | 13+ 次 |

---

## 二、LLM 交互核心模块分布

### 1. `core/agents/__init__.py (7个调用)

#### 1.1 `ArchitectAgent.plan_chapter()` (第 172-198 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是故事建筑师，只输出合法 JSON，不输出任何说明文字。 |
| **User Prompt** | 你是精通戏剧结构的故事建筑师，为写手规划本章写作蓝图。<br><br>## 章纲<br>- 章节：第 {chapter_outline.chapter_number} 章《{chapter_outline.title}》<br>- 摘要：{chapter_outline.summary}<br>- 必完任务：{chapter_outline.mandatory_tasks}<br>- 情感弧：{chapter_outline.emotional_arc}<br>- 字数目标：{chapter_outline.target_words} 字<br>- 节拍序列：{chapter_outline.beats}<br>{pov_section}{thread_section}<br>## 当前世界状态<br>{world_context}<br><br>## 未闭合伏笔<br>{pending_hooks}<br><br>请输出完整 JSON，字段说明：... |
| **返回类型** | `ArchitectBlueprint` (Pydantic Schema) |
| **功能描述** | 规划单章写作蓝图，包括核心冲突、伏笔、情感旅程、节奏说明等 |

---

#### 1.2 `WriterAgent.write_chapter()` (第 386-412 行)

| 项目 | 内容 |
|------|------|
| **System Message** | WRITER_SYSTEM_PROMPT 变量内容：<br>你是一位优秀的中文小说写手，专注于{genre}题材。<br><br>## 创作铁律（不可违反）<br>1. 只写动作、感知、对话——不替读者下结论，不做心理分析式独白<br>2. 冲突必须源于角色目标与障碍的碰撞，绝对不靠巧合推进<br>3. 每个场景必须推进叙事 OR 揭示角色，二者至少占其一<br>4. 场景结尾状态必须比开始更极端（更好/更坏/意外转折）<br>5. 对话要有潜台词，人物说的话和真正想说的话之间要有张力<br><br>## 语言规范<br>- AI 标记词（仿佛/忽然/竟然/不禁/宛如/猛地/顿时）：每 3000 字各最多 1 次<br>- 绝对禁止：元叙事（核心动机/叙事节奏/人物弧线）<br>- 绝对禁止：报告式语言（分析了形势/从…角度来看/综合考虑）<br>- 绝对禁止：作者说教（显然/不言而喻/毫无疑问）<br>- 绝对禁止：集体反应套话（全场震惊/众人哗然/所有人都）<br>- 破折号「——」：全书最多用 3 次，珍惜使用<br><br>## 写后必须输出结算表<br>正文写完后，用 ===SETTLEMENT=== 分隔，输出 JSON 结算表。 |
| **User Prompt** | 包含：前一章结尾衔接（prev_section）+ 节拍序列（beats_str）+ POV 角色信息 + 主角信息 + 核心冲突 + 结尾钩子 + 节奏建议 + 登场角色 + 当前世界状态 + 前情摘要 + 未闭合伏笔 + 因果链 + 情感弧 + 高风险连续性点 + 字数目标（硬性约束） |
| **返回类型** | `WriterOutput` (含 content + settlement) |
| **功能描述** | 生成单章小说内容，包含正文 + 结算表（世界状态变化记录） |

---

#### 1.3 `AuditorAgent.audit_chapter()` (第 610-639 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是严格的叙事审计员，专注叙事质量，对 critical 问题零容忍但不制造假阳性。只输出合法 JSON，不输出任何说明文字。 |
| **User Prompt** | 审计检查项：大纲偏离、因果一致性、伏笔管理、OOC、信息边界、连续性、情感弧线、节奏、结尾钩子、冲突质量、去AI味、跨线程一致性、事实准确性、表达准确性 |
| **返回类型** | `AuditReport` (审计报告) |
| **功能描述** | 审计章节质量，检测各种问题并给出评分和建议 |

---

#### 1.4 `ReviserAgent.revise()` (第 788-811 行)

| 项目 | 内容 |
|------|------|
| **System Message** | （由 mode 决定：精准的小说修订者 + mode 说明 |
| **User Prompt** | 修订任务 + 问题列表 + 原文 + 字数调整要求 |
| **返回类型** | `ReviseResult` (修订后的内容 + changelog) |
| **功能描述** | 根据审计结果修订章节内容 |

---

#### 1.5 `SummaryAgent.generate_summary()` (第 875-882 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是叙事编辑，生成精准的章节摘要，只输出 JSON。 |
| **User Prompt** | 章节内容 + 结算表信息 |
| **返回类型** | `_SummarySchema` (结构化摘要) |
| **功能描述** | 生成章节摘要供后续章节使用 |

---

#### 1.6 `QualityAgent.evaluate_chapter()` (第 1083-1138 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是专业的小说质量评估师，输出严格符合 JSON 格式的评估报告，不输出任何说明文字。 |
| **User Prompt** | 六个核心维度 + 六大连贯性层次 + 类型特征矩阵 + 章节内容 + 相关上下文 |
| **返回类型** | `QualityReport` (质量评估报告) |
| **功能描述** | 全面评估章节质量，给出评分和建议 |

---

#### 1.7 `QualityAgent.revise()` (第 1210-1222 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 通过 `_get_revise_system_prompt(mode)` 生成 |
| **User Prompt** | 质量评估问题 + 原文 + 修订要求 |
| **返回类型** | `QualityReviseResult` |
| **功能描述** | 根据质量评估结果进行修订 |

---

### 2. `core/narrative/__init__.py` (3个调用)

#### 2.1 `generate_story_outline()` (第 265-273 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是精通戏剧理论的故事架构师，只输出合法 JSON。 |
| **返回类型** | `StoryOutlineSchema` |
| **功能描述** | 生成故事大纲（序列级） |

---

#### 2.2 `generate_chapter_outlines()` (第 471-478 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是精通节拍表的故事编辑，只输出合法 JSON 数组，章数必须精确。 |
| **返回类型** | `list[ChapterOutlineSchema]` |
| **功能描述** | 批量生成章节大纲，支持进度回调 |

---

#### 2.3 `analyze_causal_chain()` (还有一个调用)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是叙事分析师，分析因果结构，只输出合法 JSON 数组。 |
| **返回类型** | `list[CausalLinkSchema]` |
| **功能描述** | 分析因果关系链 |

---

### 3. `core/server.py` (5个+ 个调用)

#### 3.1 `generate_continue_outlines()` (第 1334 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是专业的小说编辑，只输出合法 JSON 数组。 |
| **User Prompt** | 续写章节大纲 |
| **返回类型** | JSON 数组 |
| **功能描述** | 续写章节大纲 |

---

#### 3.2 `generate_world_setting()` (第 1509 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是资深网文世界观设计师，只输出合法 JSON。 |
| **User Prompt** | 世界观设计 |
| **返回类型** | JSON |
| **功能描述** | 生成世界观设定 |

---

#### 3.3 `extract_from_novel()` (第 1619 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是资深的小说分析师，擅长从文本中提取角色和世界观设定。只输出合法 JSON。 |
| **功能描述** | 从现有小说文本中提取角色和世界设定 |

---

#### 3.4 `extract_from_novel()` (第 1728 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是小说分析专家，擅长从正文提取结构化状态数据。只输出合法 JSON。 |
| **功能描述** | 从小说正文提取状态信息 |

---

#### 3.5 `action_write_stream` (第 2075 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是小说分析专家，擅长从正文提取结构化状态数据。只输出合法 JSON。 |
| **User Prompt** | 提取状态数据 |
| **功能描述** | 状态数据提取 |

---

#### 3.6 `action_write` (第 2381 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是故事架构师，只输出合法 JSON。 |
| **功能描述** | 故事架构相关处理 |

---

#### 3.7 `refine_idea` (第 2467 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是故事架构师，只输出合法 JSON 数组。 |
| **功能描述** | 改进创作理念 |

---

#### 3.8 `rewrite_text` (第 3198-3200 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是一位经验丰富的小说编辑。只输出重写后的段落文本，不要任何说明。 |
| **功能描述** | 重写文本段落 |

---

#### 3.9 `refine_outline` (第 3574-3576 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是精通小说结构的故事编辑，只输出合法 JSON。 |
| **功能描述** | 改进大纲 |

---

#### 3.10 `action_write` (第 3766-3767 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是一位经验丰富的网络小说作家，擅长{genre}题材，文笔流畅，善用描写和对话推进情节。直接输出小说正文。{style_section} |
| **功能描述** | 写作章节正文 |

---

#### 3.11 `summary` (第 3796-3797 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你是小说编辑助手，生成简洁客观的章节摘要并分析伏笔回收情况。 |
| **功能描述** | 章节摘要生成 |

---

#### 3.12 `causal chain` (第 3855-3856 行)

| 项目 | 内容 |
|------|------|
| **System Message** | 你从小说正文中提取因果关系，每条一行。 |
| **功能描述** | 因果关系提取 |

---

### 4. `cli/main.py` (1个调用)

#### 4.1 `doctor` 命令 (第 754-755 行)

| 项目 | 内容 |
|------|------|
| **System Message** | (无) |
| **User Prompt** | 只回复数字 42。 |
| **功能描述** | API 连通性测试 |

---

## 三、核心 LLM 架构 (core/llm/__init__.py)

### Provider 类定义

```
LLMProvider (抽象基类)
  ├─ DeepSeekProvider (OpenAI 兼容接口)
  └─ OllamaProvider (本地模型接口)
```

### 数据结构

| 类名 | 描述 |
|------|------|
| `LLMMessage` | {role: "system"/"user"/"assistant", content: str} |
| `LLMResponse` | {content: str, input_tokens: int, output_tokens: int} |
| `LLMConfig` | API key、base_url、model、temperature、max_tokens |

### 工具函数

| 函数名 | 功能 |
|------|------|
| `parse_llm_json()` | 安全解析 LLM 输出的 JSON (支持截断修复) |
| `parse_llm_json_list()` | 解析 JSON 数组 |
| `with_retry()` | 重试装饰器 (LLMParseError 会触发重试) |

---

## 四、调用方式总结

### 按功能分类：

| 功能类型 | 调用次数 | 说明 |
|---------|---------|------|
| 大纲生成类 | 4+ | 故事/章节大纲生成 |
| 写作类 | 2 | 章节写作 |
| 审计类 | 1 | 质量审计 |
| 摘要提取类 | 4+ | 摘要/状态/因果提取 |
| 修订类 | 2 | 内容修订 |
| 分析类 | 3+ | 质量评估、因果分析 |

### 按输出格式分类：

| 输出格式 | 调用次数 |
|---------|---------|
| JSON (Pydantic | 大多数 |
| 文本 + JSON (结算表 | 1 (Writer) |

---

## 五、提示词特点

### 通用元素：

1. **身份锚定：都有明确的 "你是..." 职业定位
2. **输出约束：都要求 "只输出 JSON" 或类似限定词
3. **结构化要求：使用 Pydantic 校验
4. **重试机制：都有 `with_retry` 装饰器
5. **解析容错：都有 JSON 解析容错逻辑

---

## 六、依赖关系图

```
core/llm/__init__.py (LLM 层)
   ↑
core/agents/__init__.py (Agent 层)
core/narrative/__init__.py (叙事生成)
core/server.py (API 层)
   ↑
cli/main.py (CLI 层)
   ↑
用户界面
```

---

## 七、优化建议

### 7.1 当前架构良好，可考虑：

1. **提示词中心化管理（避免重复定义
2. **统一的 LLM 调用参数配置中心
3. **提示词版本管理
4. **调用日志记录与 Token 消耗监控

