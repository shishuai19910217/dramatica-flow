# 小说创作质量保障体系改进设计文档

## 1. 需求分析

### 1.1 业务背景
基于对小说评价标准的深入讨论，结合现有系统架构，需要建立一套科学有效的小说质量保障体系，涵盖内容评估、流程规范和质量监控三大维度。

### 1.2 核心需求（基于5W2H分析）

| 维度 | 分析内容 |
|------|----------|
| **What-What** | 建立四维度质量评估体系（故事、人物、语言、阅读体验），实现AI+人工结合的质量监控机制 |
| **Why-Why** | 确保小说创作质量，提升读者体验，降低创作门槛，提高创作效率 |
| **When** | 在创作流程的关键节点进行质量检查（大纲阶段、章纲阶段、初稿阶段、修订阶段、终稿阶段） |
| **Where** | 集成到现有写作系统中，作为独立的质量保障模块 |
| **Who** | 作者（自查）、AI系统（自动检查）、编辑（人工审核） |
| **How** | 通过规则引擎+LLM审计实现自动化检查，辅以人工审核 |
| **How much** | 目标：AI自动检测率≥80%，人工审核效率提升50%，问题修复率≥95% |

### 1.3 功能需求清单

| 优先级 | 需求编号 | 需求描述 | 来源 |
|--------|----------|----------|------|
| P0 | REQ-001 | 实现故事层面质量检查（因果链、结构、设定、伏笔） | 讨论结论 |
| P0 | REQ-002 | 实现人物层面质量检查（动机、弧光、行为一致性、情感真实性） | 讨论结论 |
| P0 | REQ-003 | 实现语言层面质量检查（文笔、节奏、视角、对话、AI痕迹） | 讨论结论 |
| P0 | REQ-004 | 实现阅读体验层面质量评估（沉浸感、情感共鸣、追读欲望） | 讨论结论 |
| P1 | REQ-005 | 建立创作流程质量把控（章纲审核、跨章节一致性检查） | 讨论结论 |
| P1 | REQ-006 | 实现AI+人工结合的质量监控机制 | 讨论结论 |
| P1 | REQ-007 | 优化AI调用效率，减少不必要的调用 | 讨论结论 |
| P1 | REQ-008 | 优化审计与修订闭环流程，提高修复效率 | 讨论结论 |
| P2 | REQ-009 | 建立质量评估报告体系 | 讨论结论 |
| P2 | REQ-010 | 实现质量数据可视化展示 | 讨论结论 |

---

## 2. 架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        质量保障体系架构                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   输入层     │    │   处理层     │    │   输出层     │              │
│  │ 章纲/正文    │───▶│ 四维度审核   │───▶│ 质量报告     │              │
│  └──────────────┘    │              │    │ 修订建议     │              │
│                      │  ┌────────┐  │    │ 优化建议     │              │
│                      │  │故事审核│  │    └──────────────┘              │
│                      │  ├────────┤  │                                  │
│                      │  │人物审核│  │                                  │
│                      │  ├────────┤  │                                  │
│                      │  │语言审核│  │                                  │
│                      │  ├────────┤  │                                  │
│                      │  │体验评估│  │                                  │
│                      │  └────────┘  │                                  │
│                      └──────────────┘                                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    质量监控闭环                               │        │
│  │  [检测] ──▶ [报告] ──▶ [修订] ──▶ [复核] ──▶ [通过/回退]    │        │
│  └─────────────────────────────────────────────────────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分与职责

| 模块 | 职责 | 状态 |
|------|------|------|
| **QualityChecker** | 四维度质量检查主入口 | 新增 |
| **StoryAuditor** | 故事层面审核（因果链、结构、设定、伏笔） | 增强现有AuditorAgent |
| **CharacterAuditor** | 人物层面审核（动机、弧光、行为一致性） | 增强现有AuditorAgent |
| **LanguageAuditor** | 语言层面审核（文笔、节奏、视角、AI痕迹） | 增强现有PostWriteValidator |
| **ExperienceEvaluator** | 阅读体验评估（沉浸感、情感共鸣） | 新增 |
| **RevisionEngine** | 修订建议生成与执行 | 增强现有ReviserAgent |
| **QualityReport** | 质量报告生成与展示 | 新增 |

### 2.3 技术栈选型

| 层次 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 语言 | Python | 3.11+ | 成熟稳定，AI生态完善 |
| 框架 | FastAPI | 0.100+ | 高性能API框架，支持异步 |
| LLM集成 | LangChain | 0.1+ | 提供统一的LLM接口抽象 |
| 数据库 | SQLite | 3.40+ | 轻量级，适合单机部署 |
| 缓存 | Redis | 7.0+ | 提高响应速度，减少重复计算 |

---

## 3. 核心模块设计

### 3.1 质量检查模块（QualityChecker）

#### 3.1.1 类设计

```python
class QualityChecker:
    """质量检查器，协调四个维度的审核"""
    
    def __init__(self, llm_provider):
        self.story_auditor = StoryAuditor(llm_provider)
        self.character_auditor = CharacterAuditor(llm_provider)
        self.language_auditor = LanguageAuditor()
        self.experience_evaluator = ExperienceEvaluator(llm_provider)
    
    def check_chapter(
        self,
        chapter_content: str,
        chapter_outline: ChapterOutlineSchema,
        world_context: dict
    ) -> QualityReport:
        """检查单章节质量"""
        # 并行执行四个维度的检查
        story_issues = self.story_auditor.audit(chapter_content, chapter_outline)
        character_issues = self.character_auditor.audit(chapter_content, world_context)
        language_issues = self.language_auditor.validate(chapter_content)
        experience_score = self.experience_evaluator.evaluate(chapter_content)
        
        return QualityReport(
            story_issues=story_issues,
            character_issues=character_issues,
            language_issues=language_issues,
            experience_score=experience_score,
            overall_score=self._calculate_overall_score(...)
        )
```

### 3.2 故事审核器（StoryAuditor）

#### 3.2.1 检查项设计

| 检查项 | 检查逻辑 | 严重级别 |
|--------|----------|----------|
| **因果链检查** | 验证事件之间是否有明确的因果关系 | critical |
| **结构完整性** | 检查起承转合是否完整 | warning |
| **设定一致性** | 检测设定冲突（如能力使用前后矛盾） | critical |
| **伏笔回收** | 追踪伏笔状态，提醒未回收的伏笔 | warning |
| **冲突密度** | 评估章节冲突强度是否达标 | info |

#### 3.2.2 核心方法

```python
class StoryAuditor:
    def audit(self, content: str, outline: ChapterOutlineSchema) -> list[AuditIssue]:
        issues = []
        
        # 因果链检查
        causal_gaps = self._detect_causal_gaps(content)
        for gap in causal_gaps:
            issues.append(AuditIssue(
                dimension="故事层面",
                severity="critical",
                description=f"因果链断裂：{gap}",
                location=self._find_location(content, gap)
            ))
        
        # 设定一致性检查
        setting_conflicts = self._detect_setting_conflicts(content)
        for conflict in setting_conflicts:
            issues.append(AuditIssue(
                dimension="故事层面",
                severity="critical",
                description=f"设定冲突：{conflict}",
                location=self._find_location(content, conflict)
            ))
        
        return issues
```

### 3.3 人物审核器（CharacterAuditor）

#### 3.3.1 检查项设计

| 检查项 | 检查逻辑 | 严重级别 |
|--------|----------|----------|
| **主角动机检查** | 验证主角行为是否有明确动机 | critical |
| **人物弧光检查** | 评估主角成长轨迹是否合理 | warning |
| **行为一致性** | 检测OOC（Out of Character）行为 | critical |
| **反派合理性** | 评估反派动机是否可信 | warning |
| **情感真实性** | 检测情感反应是否符合情境 | warning |

### 3.4 语言审核器（LanguageAuditor）

#### 3.4.1 检查项设计

| 检查项 | 检查逻辑 | 严重级别 |
|--------|----------|----------|
| **AI痕迹检测** | 检测套路词、元叙事语言 | warning |
| **视角一致性** | 检测视角跳变 | critical |
| **对话真实性** | 评估对话是否符合人物身份 | warning |
| **字数偏差** | 检测章节字数是否达标 | warning |
| **章节钩子** | 评估结尾悬念质量 | info |

### 3.5 阅读体验评估器（ExperienceEvaluator）

#### 3.5.1 评估指标

| 指标 | 评估方法 | 权重 |
|------|----------|------|
| **沉浸感** | LLM评估文本代入感 | 30% |
| **情感共鸣** | LLM分析情感传递效果 | 30% |
| **追读欲望** | 评估章节结尾吸引力 | 25% |
| **信息密度** | 分析信息分布合理性 | 15% |

---

## 4. 数据库与数据结构设计

### 4.1 质量报告数据结构

```python
@dataclass
class QualityReport:
    chapter_number: int
    chapter_title: str
    story_issues: list[AuditIssue]
    character_issues: list[AuditIssue]
    language_issues: list[AuditIssue]
    experience_score: float
    overall_score: float
    generated_at: datetime
```

### 4.2 检查项数据结构

```python
@dataclass
class AuditIssue:
    dimension: str          # 故事/人物/语言/体验
    severity: str           # critical/warning/info
    description: str        # 问题描述
    location: str           # 原文位置引用
    suggestion: str         # 修复建议
    rule: str               # 规则名称
```

### 4.3 质量趋势数据结构

```python
@dataclass
class QualityTrend:
    book_id: str
    chapter_number: int
    story_score: float
    character_score: float
    language_score: float
    experience_score: float
    overall_score: float
```

---

## 5. API接口设计

### 5.1 质量检查接口

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 检查章节质量 | POST | `/api/quality/check` | 检查单章节质量 |
| 获取质量报告 | GET | `/api/quality/report/{book_id}/{chapter}` | 获取章节质量报告 |
| 获取质量趋势 | GET | `/api/quality/trend/{book_id}` | 获取书籍质量趋势 |
| 批量检查 | POST | `/api/quality/batch` | 批量检查多章节 |

#### 5.1.1 POST /api/quality/check

**请求体**：
```json
{
    "book_id": "book_001",
    "chapter_number": 3,
    "content": "第三章正文内容...",
    "outline": {...},
    "world_context": {...}
}
```

**响应体**：
```json
{
    "ok": true,
    "report": {
        "chapter_number": 3,
        "overall_score": 85.5,
        "issues": [
            {
                "dimension": "语言层面",
                "severity": "warning",
                "description": "AI痕迹：「仿佛」出现3次",
                "location": "第15段",
                "suggestion": "建议替换为更自然的表达"
            }
        ],
        "experience_score": 88.0
    }
}
```

---

## 6. 质量监控机制设计

### 6.1 检查触发时机

**当前实现状态**：采用手动触发方式，用户可在 Step 6（审计修订）页面主动发起检查。

| 触发方式 | 检查内容 | 检查方式 | 实现状态 |
|----------|----------|----------|----------|
| 手动点击「深度检查」按钮 | 五维度深度分析（情节逻辑、人物塑造、语言风格、主题契合、创意新颖） | LLM深度分析 | ✅ 已实现 |
| 手动点击「一键优化」按钮 | 全维度检查 + AI智能优化 | LLM分析 + 自动修订 | ✅ 已实现 |
| 章纲提交自动触发 | 结构完整性、目标合理性 | AI自动检查 | 🔄 待实现 |
| 初稿完成自动触发 | 全维度检查 | AI自动检查 | 🔄 待实现 |
| 修订完成自动触发 | 问题修复验证 | AI自动检查 | 🔄 待实现 |
| 终稿提交自动触发 | 全维度审核 | AI+人工结合 | 🔄 待实现 |

**手动触发入口**：在 Step 6（审计修订）页面中，每个章节卡片提供两个操作按钮：
- `🧠 深度检查`：调用 LLM 进行五维度质量分析，生成详细报告
- `✨ 一键优化`：先进行深度检查，再基于分析结果调用 LLM 进行智能优化

### 6.2 质量阈值设定

| 严重级别 | 阈值 | 处理方式 |
|----------|------|----------|
| critical | >0 | 阻塞发布，必须修复 |
| warning | >5 | 建议修订后发布 |
| info | 无限制 | 提供优化建议 |

### 6.3 AI+人工协作流程

```
[作者提交] ──▶ [AI自动检查] ──▶ [生成报告]
                                          │
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
            [critical>0]           [warning>5]            [通过]
                    │                      │                      │
                    ▼                      ▼                      ▼
            [强制修订]           [建议人工审核]           [正常发布]
                    │                      │
                    ▼                      ▼
            [重新检查]           [编辑审核]
                    │                      │
                    └──────────────────────┘
                              │
                              ▼
                       [通过/退回]
```

---

## 7. 执行处理逻辑优化

### 7.1 AI调用效率优化

| 优化策略 | 实现方式 | 预期收益 |
|----------|----------|----------|
| **缓存机制** | 缓存重复检查结果 | 减少30%AI调用 |
| **增量检查** | 只检查修改部分 | 减少50%处理时间 |
| **优先级调度** | 先执行快速检查（规则引擎） | 快速反馈 |
| **批量处理** | 合并多个章节检查请求 | 提高吞吐量 |

### 7.2 审计与修订流程优化

```python
# 优化后的修订流程
def optimize_revision_flow(content, issues):
    # 1. 分类问题
    critical_issues = [i for i in issues if i.severity == "critical"]
    warning_issues = [i for i in issues if i.severity == "warning"]
    
    # 2. 并行处理同类问题
    if critical_issues:
        content = revise_critical(content, critical_issues)
    
    if warning_issues:
        content = revise_warning(content, warning_issues)
    
    # 3. 针对性处理特殊问题（如字数偏差）
    word_count_issue = find_word_count_issue(issues)
    if word_count_issue:
        content = adjust_word_count(content, word_count_issue)
    
    return content
```

### 7.3 缓存策略设计

| 缓存类型 | 缓存内容 | 过期时间 |
|----------|----------|----------|
| 设定缓存 | 世界观设定、人物设定 | 持久化 |
| 检查缓存 | 章节质量检查结果 | 24小时 |
| 修订缓存 | 修订建议 | 1小时 |
| 趋势缓存 | 质量趋势数据 | 6小时 |

---

## 8. 安全性与稳定性考虑

### 8.1 安全性

| 风险点 | 防护措施 |
|--------|----------|
| 输入注入 | 对用户输入进行严格校验和过滤 |
| 敏感信息泄露 | 日志脱敏处理，不记录完整正文内容 |
| LLM安全风险 | 使用prompt注入防护，限制输出格式 |
| 资源滥用 | 限制API调用频率，添加请求限流 |

### 8.2 稳定性

| 保障措施 | 实现方式 |
|----------|----------|
| 异常处理 | 完善的try-catch机制，优雅降级 |
| 重试机制 | 对LLM调用添加重试策略 |
| 超时控制 | 设置合理的超时时间，防止阻塞 |
| 监控告警 | 添加关键指标监控和异常告警 |

---

## 9. 部署与集成方案

### 9.1 模块集成

```python
# 在现有WritingPipeline中集成质量检查
class WritingPipeline:
    def __init__(self, ...):
        self.quality_checker = QualityChecker(llm_provider)  # 新增
    
    def run(self, chapter_outline):
        # ... 现有逻辑 ...
        
        # 写后质量检查（新增）
        quality_report = self.quality_checker.check_chapter(
            content=writer_output.content,
            chapter_outline=chapter_outline,
            world_context=world_context
        )
        
        # 根据质量报告决定是否需要修订
        if not quality_report.passed:
            revise_result = self.reviser.revise(
                content=writer_output.content,
                issues=quality_report.all_issues
            )
            content = revise_result.content
        
        # ... 后续逻辑 ...
```

### 9.2 配置管理

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `quality.enabled` | 是否启用质量检查 | true |
| `quality.strict_mode` | 是否启用严格模式 | false |
| `quality.critical_threshold` | critical问题阈值 | 0 |
| `quality.warning_threshold` | warning问题阈值 | 5 |
| `quality.cache_ttl` | 缓存过期时间（秒） | 86400 |

---

## 10. 测试与验证

### 10.1 测试用例设计

| 测试场景 | 测试用例 | 预期结果 |
|----------|----------|----------|
| 因果链断裂 | 事件A后直接发生事件C，缺少事件B | 检测到critical问题 |
| 设定冲突 | 角色第一章说不会武功，第三章使用武功 | 检测到critical问题 |
| AI痕迹过多 | 使用「仿佛」「忽然」等词超过阈值 | 检测到warning问题 |
| 字数偏差 | 目标5000字，实际4000字 | 检测到warning问题 |
| 视角跳变 | 突然从主角视角切换到配角视角 | 检测到critical问题 |

### 10.2 性能测试

| 指标 | 目标值 |
|------|--------|
| 单章节检查时间 | <10秒 |
| 批量检查10章 | <60秒 |
| API响应时间 | <2秒 |
| 错误率 | <1% |

---

## 11. 实施计划

### 11.1 阶段划分

| 阶段 | 时间 | 任务 | 交付物 |
|------|------|------|--------|
| **Phase 1** | 1-2周 | 需求分析与设计 | 设计文档 |
| **Phase 2** | 2-3周 | 核心模块开发 | StoryAuditor、CharacterAuditor |
| **Phase 3** | 2周 | 语言审核与体验评估 | LanguageAuditor、ExperienceEvaluator |
| **Phase 4** | 2周 | 集成与测试 | 完整质量检查流程 |
| **Phase 5** | 1周 | 部署与上线 | 生产环境部署 |

### 11.2 里程碑

| 里程碑 | 完成标准 |
|--------|----------|
| M1 | 故事层面检查功能上线 |
| M2 | 人物层面检查功能上线 |
| M3 | 语言层面检查功能上线 |
| M4 | 阅读体验评估功能上线 |
| M5 | 完整质量保障体系上线 |

---

## 11. 前端扩展设计（方案A：在现有审计控制页面扩展）

### 11.1 扩展后的页面结构

```
【审计控制】页面扩展布局
┌─────────────────────────────────────────────────────────────────────┐
│  左侧控制面板                                    │  右侧展示区      │
│  ┌──────────────────────────┐                    │                  │
│  │ 审计章节选择             │                    │  ┌─────────────┐ │
│  │ 审计范围选择             │                    │  │ 质量评分卡片 │ │
│  │ [开始审计] [自动修订]    │                    │  │ 四维度评分  │ │
│  ├──────────────────────────┤                    │  └─────────────┘ │
│  │ 标签页切换               │                    │                  │
│  │ ┌────┬────┬────┬─────┐  │                    │  ┌─────────────┐ │
│  │ │审计│故事│正文│质量 │  │                    │  │ 审计结果    │ │
│  │ │结果│数据│编辑│监控 │  │                    │  │ 问题列表    │ │
│  │ └────┴────┴────┴─────┘  │                    │  └─────────────┘ │
│  │ 故事数据面板             │                    │                  │
│  │ (story-data-panel)       │                    │  ┌─────────────┐ │
│  │ 正文编辑面板             │                    │  │ 质量趋势图  │ │
│  │ (edit-panel)             │                    │  │ 章节对比    │ │
│  │ 质量监控面板             │                    │  └─────────────┘ │
│  │ (quality-panel) ←新增    │                    │                  │
│  └──────────────────────────┘                    └──────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 新增质量评分卡片组件

| 组件 | 描述 | 数据来源 |
|------|------|----------|
| **质量评分仪表盘** | 圆形进度条展示四维度评分 | `/api/quality/report/{book_id}/{chapter}` |
| **问题分布饼图** | 按维度/严重级别展示问题分布 | 审计结果数据 |
| **质量趋势折线图** | 展示各章节质量变化趋势 | `/api/quality/trend/{book_id}` |

### 11.3 新增API接口

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 获取质量报告 | GET | `/api/quality/report/{book_id}/{chapter}` | 获取单章节四维度质量报告 |
| 获取质量趋势 | GET | `/api/quality/trend/{book_id}` | 获取全书各章节质量趋势数据 |
| 批量质量检查 | POST | `/api/quality/batch` | 批量检查多章节质量 |

### 11.4 前端扩展实现

#### 11.4.1 新增标签页切换

```javascript
// 在现有标签页中增加"质量监控"标签
<div class="mode-tabs" style="margin-bottom:8px">
  <div class="mode-tab active" id="tab-audit" onclick="switchAuditTab('audit',this)">审计结果</div>
  <div class="mode-tab" id="tab-story" onclick="switchAuditTab('story',this)">故事数据</div>
  <div class="mode-tab" id="tab-edit" onclick="switchAuditTab('edit',this)">正文编辑</div>
  <div class="mode-tab" id="tab-quality" onclick="switchAuditTab('quality',this)">质量监控</div>
</div>
```

#### 11.4.2 新增质量评分卡片HTML结构

```html
<div class="quality-score-card">
  <div class="card-header">📊 质量评分</div>
  <div class="quality-scores">
    <div class="score-item">
      <div class="score-ring" style="--score: ${storyScore}">
        <span class="score-value">${storyScore}</span>
      </div>
      <span class="score-label">故事层面</span>
    </div>
    <div class="score-item">
      <div class="score-ring" style="--score: ${charScore}">
        <span class="score-value">${charScore}</span>
      </div>
      <span class="score-label">人物层面</span>
    </div>
    <div class="score-item">
      <div class="score-ring" style="--score: ${langScore}">
        <span class="score-value">${langScore}</span>
      </div>
      <span class="score-label">语言层面</span>
    </div>
    <div class="score-item">
      <div class="score-ring" style="--score: ${expScore}">
        <span class="score-value">${expScore}</span>
      </div>
      <span class="score-label">阅读体验</span>
    </div>
  </div>
  <div class="overall-score">
    <div class="overall-ring" style="--score: ${overallScore}">
      <span class="overall-value">${overallScore}</span>
    </div>
    <span class="overall-label">综合评分</span>
  </div>
</div>
```

#### 11.4.3 质量监控面板

```javascript
async function loadQualityPanel() {
  const panel = document.getElementById('quality-panel');
  if (!panel) return;
  
  const ch = parseInt(document.getElementById('audit-chapter')?.value);
  if (!ch) {
    panel.innerHTML = '<div class="empty">请先选择章节</div>';
    return;
  }
  
  panel.innerHTML = '<div class="loading">加载质量数据...</div>';
  
  try {
    // 获取当前章节质量报告
    const report = await api(`/books/${currentBook.id}/quality/report/${ch}`);
    // 获取全书质量趋势
    const trend = await api(`/books/${currentBook.id}/quality/trend`);
    
    panel.innerHTML = renderQualityPanel(report, trend);
  } catch (e) {
    panel.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
  }
}
```

### 11.5 样式设计

```css
/* 质量评分卡片样式 */
.quality-score-card {
  padding: 16px;
  background: var(--bg-dark);
  border-radius: var(--radius);
  margin-bottom: 12px;
}

.quality-scores {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.score-item {
  text-align: center;
}

.score-ring {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: conic-gradient(
    var(--green) calc(var(--score) * 3.6deg),
    var(--border) calc(var(--score) * 3.6deg)
  );
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
  position: relative;
}

.score-ring::before {
  content: '';
  position: absolute;
  width: 48px;
  height: 48px;
  background: var(--bg-dark);
  border-radius: 50%;
}

.score-value {
  position: relative;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.score-label {
  font-size: 11px;
  color: var(--text3);
}

.overall-score {
  text-align: center;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.overall-ring {
  width: 80px;
  height: 80px;
  margin: 0 auto 8px;
  background: conic-gradient(
    var(--purple) calc(var(--score) * 3.6deg),
    var(--border) calc(var(--score) * 3.6deg)
  );
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.overall-ring::before {
  content: '';
  position: absolute;
  width: 64px;
  height: 64px;
  background: var(--bg-dark);
  border-radius: 50%;
}

.overall-value {
  position: relative;
  font-size: 20px;
  font-weight: 700;
  color: var(--purple);
}

.overall-label {
  font-size: 12px;
  color: var(--text2);
  font-weight: 600;
}

/* 质量趋势图表样式 */
.quality-trend-chart {
  padding: 16px;
  background: var(--bg-dark);
  border-radius: var(--radius);
}

.trend-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.trend-chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.trend-legend {
  display: flex;
  gap: 16px;
  font-size: 11px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-color {
  width: 12px;
  height: 2px;
  border-radius: 1px;
}

.trend-chart-body {
  height: 200px;
  position: relative;
}

.trend-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.trend-grid-line {
  height: 1px;
  background: var(--border);
}

.trend-lines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.trend-line {
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-point {
  r: 4;
  fill: var(--bg-dark);
  stroke-width: 2;
}
```

### 11.6 后端API实现（server.py）

```python
@app.get("/api/books/{book_id}/quality/report/{chapter}")
def get_quality_report(book_id: str, chapter: int):
    """获取章节质量报告"""
    sm = _sm(book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        raise HTTPException(404, "章节不存在")
    
    # 计算各维度评分（简化版，实际应调用QualityChecker）
    report = {
        "chapter_number": chapter,
        "story_score": calculate_story_score(content),
        "character_score": calculate_character_score(content),
        "language_score": calculate_language_score(content),
        "experience_score": calculate_experience_score(content),
        "overall_score": calculate_overall_score(...),
        "issues": get_issues_for_chapter(book_id, chapter),
    }
    return report

@app.get("/api/books/{book_id}/quality/trend")
def get_quality_trend(book_id: str):
    """获取全书质量趋势"""
    sm = _sm(book_id)
    chapters = sm.list_chapters()
    trend_data = []
    
    for ch in chapters:
        content = sm.read_final(ch.number) or sm.read_draft(ch.number)
        if content:
            trend_data.append({
                "chapter_number": ch.number,
                "story_score": calculate_story_score(content),
                "character_score": calculate_character_score(content),
                "language_score": calculate_language_score(content),
                "experience_score": calculate_experience_score(content),
                "overall_score": calculate_overall_score(...),
            })
    
    return {"chapters": trend_data}
```

---

## 12. 质量监控与审计修订联动机制

### 12.1 联动流程设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    质量监控与审计修订联动流程                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [章节完成] ──▶ [质量评分] ──▶ [阈值判断]                               │
│                                      │                                  │
│                    ┌─────────────────┼─────────────────┐                │
│                    ▼                 ▼                 ▼                │
│              [合格]             [警告]             [严重]              │
│                    │                 │                 │                │
│                    ▼                 ▼                 ▼                │
│              [正常发布]      [建议修订]         [强制修订]              │
│                                      │                 │                │
│                                      └────────┬────────┘                │
│                                               ▼                        │
│                                      [AI自动修订]                       │
│                                               │                        │
│                                               ▼                        │
│                                      [重新评分]                         │
│                                               │                        │
│                                   ┌────────────┴────────────┐           │
│                                   ▼                         ▼           │
│                              [达标]                   [未达标]         │
│                                   │                         │           │
│                                   ▼                         ▼           │
│                              [发布]                   [人工审核]       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 质量阈值配置

| 级别 | 综合评分范围 | 处理方式 | 颜色标识 |
|------|-------------|----------|----------|
| **严重不合格** | < 40 | 强制修订，阻止发布 | 🔴 红色 |
| **警告** | 40 - 60 | 建议修订，可选择跳过 | 🟡 黄色 |
| **合格** | 60 - 80 | 正常发布，建议优化 | 🟢 绿色 |
| **优秀** | >= 80 | 正常发布 | ✨ 紫色 |

### 12.3 联动机制实现

#### 12.3.1 新增API接口

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 质量检查并修订 | POST | `/api/books/{book_id}/quality/check-and-revise/{chapter}` | 检查质量并自动修订不合格内容 |
| 获取优化建议 | GET | `/api/books/{book_id}/quality/suggestions/{chapter}` | 获取针对性优化建议 |
| 设置质量阈值 | PUT | `/api/books/{book_id}/quality/threshold` | 自定义质量阈值配置 |

#### 12.3.2 质量检查并修订流程

```python
@app.post("/api/books/{book_id}/quality/check-and-revise/{chapter}")
def check_and_revise(book_id: str, chapter: int):
    """检查质量并自动修订"""
    sm = _sm(book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    
    # 1. 计算质量评分
    report = calculate_quality_report(content)
    
    # 2. 判断是否需要修订
    if report["overall_score"] < QUALITY_THRESHOLD["critical"]:
        # 3. 执行自动修订
        revised_content = auto_revise(content, report)
        sm.save_draft(chapter, revised_content)
        
        # 4. 重新计算评分
        new_report = calculate_quality_report(revised_content)
        
        return {
            "status": "revised",
            "original_score": report["overall_score"],
            "new_score": new_report["overall_score"],
            "revised": True
        }
    
    return {
        "status": "passed",
        "score": report["overall_score"],
        "revised": False
    }
```

#### 12.3.3 优化建议生成

```python
def generate_suggestions(report, content):
    """根据质量报告生成针对性优化建议"""
    suggestions = []
    
    # 故事层面建议
    if report["story_score"] < 60:
        suggestions.append({
            "dimension": "故事层面",
            "score": report["story_score"],
            "suggestion": "建议增加更多情节转折和冲突，使用'但是'、'然而'等词制造悬念",
            "action": "add_plot_twists"
        })
    
    # 人物层面建议
    if report["character_score"] < 60:
        suggestions.append({
            "dimension": "人物层面",
            "score": report["character_score"],
            "suggestion": "建议增加人物心理描写和对话，使角色更立体",
            "action": "add_character_depth"
        })
    
    # 语言层面建议
    if report["language_score"] < 60:
        suggestions.append({
            "dimension": "语言层面",
            "score": report["language_score"],
            "suggestion": "建议减少AI痕迹词（如'仿佛'、'似乎'），增加语言多样性",
            "action": "improve_language"
        })
    
    # 阅读体验建议
    if report["experience_score"] < 60:
        suggestions.append({
            "dimension": "阅读体验",
            "score": report["experience_score"],
            "suggestion": "建议优化章节结尾，增加悬念钩子吸引读者继续阅读",
            "action": "improve_cliffhanger"
        })
    
    return suggestions
```

### 12.4 前端联动实现

#### 12.4.1 质量监控面板增强

```html
<div class="quality-panel">
  <!-- 评分卡片 -->
  <div class="quality-score-card" style="border-left: 4px solid ${getScoreColor(overall_score)}">
    <div class="card-header">📊 质量评分</div>
    <div class="overall-score">
      <div class="overall-ring" style="--score: ${overall_score}">
        <span class="overall-value">${overall_score}</span>
      </div>
      <span class="overall-label">${getScoreLevel(overall_score)}</span>
    </div>
    <!-- 行动按钮 -->
    <div style="display:flex;gap:8px;margin-top:12px">
      <button class="btn btn-primary btn-sm" onclick="runQualityRevise()">
        ✨ 一键优化
      </button>
      <button class="btn btn-sm" onclick="showSuggestions()">
        💡 查看建议
      </button>
    </div>
  </div>
  
  <!-- 优化建议面板 -->
  <div id="suggestions-panel" style="display:none;margin-top:12px">
    <div class="card-header">💡 优化建议</div>
    <div id="suggestions-content"></div>
  </div>
</div>
```

#### 12.4.2 联动逻辑

```javascript
async function runQualityRevise() {
  const ch = parseInt(document.getElementById('audit-chapter')?.value);
  if (!ch) return toast('请先选择章节', false);
  
  toast('正在进行质量优化...', 'loading');
  
  try {
    const res = await api(`/books/${currentBook.id}/quality/check-and-revise/${ch}`, {
      method: 'POST'
    });
    
    if (res.revised) {
      toast(`优化完成！评分从 ${res.original_score} 提升至 ${res.new_score}`, true);
      await loadQualityPanel(); // 刷新质量面板
      await loadAuditChapterText(); // 刷新正文
    } else {
      toast(`质量达标（${res.score}分），无需优化`, true);
    }
  } catch (e) {
    toast('优化失败: ' + e.message, false);
  }
}

function getScoreColor(score) {
  if (score < 40) return 'var(--red)';
  if (score < 60) return 'var(--yellow)';
  if (score < 80) return 'var(--green)';
  return 'var(--purple)';
}

function getScoreLevel(score) {
  if (score < 40) return '严重不合格';
  if (score < 60) return '需要优化';
  if (score < 80) return '合格';
  return '优秀';
}
```

### 12.5 质量预警机制

#### 12.5.1 趋势异常检测

```python
def detect_trend_anomaly(trend_data):
    """检测质量趋势异常"""
    anomalies = []
    
    if len(trend_data) < 3:
        return anomalies
    
    # 计算最近3章的平均评分
    recent_scores = [ch["overall_score"] for ch in trend_data[-3:]]
    avg_recent = sum(recent_scores) / len(recent_scores)
    
    # 计算之前章节的平均评分
    prev_scores = [ch["overall_score"] for ch in trend_data[:-3]]
    if prev_scores:
        avg_prev = sum(prev_scores) / len(prev_scores)
        
        # 如果最近评分下降超过15分，发出预警
        if avg_prev - avg_recent > 15:
            anomalies.append({
                "type": "trend_drop",
                "message": f"质量评分明显下降（{avg_prev:.1f} → {avg_recent:.1f}）",
                "severity": "warning"
            })
    
    return anomalies
```

#### 12.5.2 预警展示

```html
<!-- 趋势预警提示 -->
<div id="trend-warning" style="display:none;padding:12px;background:var(--yellow-bg);border-radius:var(--radius);margin-bottom:12px">
  <div style="display:flex;align-items:center;gap:8px">
    <span>⚠️</span>
    <span style="font-size:12px;color:var(--yellow)">质量趋势预警：最近章节评分明显下降，建议关注</span>
    <button onclick="document.getElementById('trend-warning').style.display='none'" style="margin-left:auto">✕</button>
  </div>
</div>
```

---

## 13. 全书质量概览功能

### 13.1 功能概述

为整本书提供全面的质量监控视图，包含：
- 全书质量总分统计
- 各维度质量分布
- 章节质量排行
- 常见问题汇总
- 改进建议总览

### 13.2 全书质量报告API

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 获取全书质量报告 | GET | `/api/books/{book_id}/quality/overview` | 获取整本书的综合质量报告 |
| 批量质量检查 | POST | `/api/books/{book_id}/quality/batch-check` | 批量检查所有章节质量 |
| 获取全书问题汇总 | GET | `/api/books/{book_id}/quality/issues-summary` | 获取全书常见问题汇总 |

### 13.3 全书质量报告结构

```python
@app.get("/api/books/{book_id}/quality/overview")
def get_book_quality_overview(book_id: str):
    """获取全书质量概览"""
    sm = _sm(book_id)
    
    # 获取所有章节质量数据
    chapters = get_all_chapters(sm)
    quality_data = []
    
    for ch in chapters:
        content = sm.read_final(ch.number) or sm.read_draft(ch.number)
        if content:
            quality_data.append({
                "chapter_number": ch.number,
                "title": ch.title,
                "story_score": calculate_story_score(content),
                "character_score": calculate_character_score(content),
                "language_score": calculate_language_score(content),
                "experience_score": calculate_experience_score(content),
                "overall_score": calculate_overall_score(content),
            })
    
    # 计算全书统计
    avg_story = sum(d["story_score"] for d in quality_data) / len(quality_data) if quality_data else 0
    avg_char = sum(d["character_score"] for d in quality_data) / len(quality_data) if quality_data else 0
    avg_lang = sum(d["language_score"] for d in quality_data) / len(quality_data) if quality_data else 0
    avg_exp = sum(d["experience_score"] for d in quality_data) / len(quality_data) if quality_data else 0
    
    # 找出问题章节
    problem_chapters = [d for d in quality_data if d["overall_score"] < QUALITY_THRESHOLD["warning"]]
    top_chapters = sorted(quality_data, key=lambda x: x["overall_score"], reverse=True)[:3]
    
    return {
        "book_id": book_id,
        "total_chapters": len(quality_data),
        "avg_story_score": round(avg_story, 1),
        "avg_character_score": round(avg_char, 1),
        "avg_language_score": round(avg_lang, 1),
        "avg_experience_score": round(avg_exp, 1),
        "book_overall_score": round((avg_story + avg_char + avg_lang + avg_exp) / 4, 1),
        "problem_chapters": len(problem_chapters),
        "top_chapters": top_chapters,
        "problematic_chapters": problem_chapters,
        "all_chapters": quality_data,
    }
```

### 13.4 全书质量概览前端设计

```html
<div class="book-quality-overview">
  <div class="card-header">📚 全书质量概览</div>
  
  <!-- 全书总分 -->
  <div class="book-overall-score">
    <div class="overall-ring-large" style="--score: ${book_overall}">
      <span class="overall-value-large">${book_overall}</span>
    </div>
    <span class="overall-label-large">全书综合评分</span>
    <span class="quality-level" style="color:${getScoreColor(book_overall)}">${getScoreLevel(book_overall)}</span>
  </div>
  
  <!-- 各维度平均分 -->
  <div class="dimension-avg">
    <div class="dim-item">
      <div class="dim-bar-container">
        <div class="dim-bar" style="width:${avg_story}%;background:var(--green)"></div>
      </div>
      <span class="dim-label">故事层面</span>
      <span class="dim-score">${avg_story}</span>
    </div>
    <!-- ... 其他维度 -->
  </div>
  
  <!-- 章节排行 -->
  <div class="chapter-ranking">
    <div class="rank-header">
      <span>🏆 质量最佳章节</span>
      <span style="font-size:11px;color:var(--text3)">点击查看详情</span>
    </div>
    ${top_chapters.map((ch, idx) => `
      <div class="rank-item" onclick="navigateToChapter(${ch.chapter_number})">
        <span class="rank-num">${idx+1}</span>
        <span class="rank-title">第${ch.chapter_number}章 ${ch.title}</span>
        <span class="rank-score" style="color:${getScoreColor(ch.overall_score)}">${ch.overall_score}</span>
      </div>
    `).join('')}
  </div>
  
  <!-- 需要改进的章节 -->
  <div class="problem-chapters">
    <div class="rank-header">
      <span>⚠️ 需要改进</span>
      <span style="font-size:11px;color:var(--text3)">${problem_count} 章</span>
    </div>
    ${problem_chapters.map(ch => `
      <div class="problem-item" onclick="navigateToChapter(${ch.chapter_number})">
        <span class="problem-title">第${ch.chapter_number}章</span>
        <span class="problem-score" style="color:var(--red)">${ch.overall_score}</span>
      </div>
    `).join('')}
  </div>
</div>
```

### 13.5 全书问题汇总

```python
@app.get("/api/books/{book_id}/quality/issues-summary")
def get_quality_issues_summary(book_id: str):
    """获取全书问题汇总"""
    sm = _sm(book_id)
    
    issues_summary = {
        "total_issues": 0,
        "critical_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "by_dimension": {
            "故事层面": [],
            "人物层面": [],
            "语言层面": [],
            "阅读体验": []
        },
        "common_problems": [],
        "suggestions": []
    }
    
    # 收集所有章节的问题
    chapters = get_all_chapters(sm)
    all_issues = []
    
    for ch in chapters:
        content = sm.read_final(ch.number) or sm.read_draft(ch.number)
        if content:
            issues = analyze_chapter_issues(content)
            all_issues.extend(issues)
    
    # 统计问题
    issues_summary["total_issues"] = len(all_issues)
    issues_summary["critical_count"] = sum(1 for i in all_issues if i["severity"] == "critical")
    issues_summary["warning_count"] = sum(1 for i in all_issues if i["severity"] == "warning")
    issues_summary["info_count"] = sum(1 for i in all_issues if i["severity"] == "info")
    
    # 按维度分类
    for issue in all_issues:
        issues_summary["by_dimension"][issue["dimension"]].append(issue)
    
    # 识别常见问题
    issue_counts = {}
    for issue in all_issues:
        key = issue["description"]
        issue_counts[key] = (issue_counts.get(key) or 0) + 1
    
    issues_summary["common_problems"] = sorted(
        issue_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]
    
    return issues_summary
```

---

## 14. LLM增强深度质量检查

### 14.1 功能概述

在规则引擎快速检查的基础上，增加LLM增强的深度质量检查，提供更全面、更准确的分析结果。

### 14.2 深度检查维度

| 维度 | 检查内容 | 调用方式 | 耗时估计 |
|------|----------|----------|----------|
| **情节逻辑分析** | 分析因果链完整性、情节合理性、伏笔设置 | LLM调用 | 5-10秒 |
| **人物一致性检查** | 判断人物行为是否符合设定、情感变化是否合理 | LLM调用 | 5-10秒 |
| **语言风格评估** | 评估文笔质量、语言流畅度、风格一致性 | LLM调用 | 3-5秒 |
| **主题契合度分析** | 评估内容是否符合题材、主题表达是否清晰 | LLM调用 | 3-5秒 |
| **创意新颖度评估** | 评估情节创意、设定创新程度 | LLM调用 | 5-10秒 |

### 14.3 深度检查API

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 深度检查单章节 | POST | `/api/books/{book_id}/quality/deep-check/{chapter}` | 使用LLM深度检查单章节 |
| 深度检查全书 | POST | `/api/books/{book_id}/quality/deep-check-all` | 使用LLM深度检查所有章节 |

### 14.4 深度检查结果结构

```python
@app.post("/api/books/{book_id}/quality/deep-check/{chapter}")
def deep_check_chapter(book_id: str, chapter: int):
    """使用LLM进行深度质量检查"""
    sm = _sm(book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        raise HTTPException(404, "章节不存在")
    
    # 获取书籍信息
    book = get_book(book_id)
    genre = book.get('genre', '')
    
    # 构建检查提示词
    prompt = f"""请深度分析以下小说章节，从多个维度进行评估：
    
【小说题材】{genre}

【章节内容】
{content[:2000]}

请按以下格式输出分析结果：
1. 情节逻辑：评估因果链是否完整、情节是否合理、是否有逻辑漏洞
2. 人物塑造：评估人物行为是否符合设定、情感变化是否合理
3. 语言风格：评估文笔质量、语言流畅度、风格一致性
4. 主题契合：评估内容是否符合题材、主题表达是否清晰
5. 创意新颖：评估情节创意、设定创新程度
6. 综合评分：给出0-100分的综合评分
7. 改进建议：提供具体的改进建议

每个维度请给出具体的分析和评分（0-100分）。
"""
    
    # 调用LLM
    result = llm.chat(prompt)
    
    # 解析结果
    deep_result = parse_deep_check_result(result)
    
    return {
        "chapter_number": chapter,
        "deep_check": deep_result,
        "timestamp": datetime.now().isoformat()
    }
```

### 14.5 前端交互设计

```html
<!-- 深度检查按钮 -->
<button class="btn btn-warning" onclick="runDeepCheck()" id="deep-check-btn">
  🧠 深度检查 (LLM)
</button>

<script>
async function runDeepCheck() {
  const btn = document.getElementById('deep-check-btn');
  btn.disabled = true;
  btn.textContent = '检查中...';
  
  try {
    const result = await api(`/books/${currentBook.id}/quality/deep-check/${currentChapter}`, {
      method: 'POST'
    });
    
    // 显示深度检查结果
    showDeepCheckResult(result);
  } catch (e) {
    toast('深度检查失败: ' + e.message, false);
  } finally {
    btn.disabled = false;
    btn.textContent = '🧠 深度检查 (LLM)';
  }
}
</script>
```

---

## 15. 附录

- [小说评价.md](file:///d:/owned/ai/xiaoshuo/dramatica-flow/小说评价.md) - 小说评价标准讨论
- [ARCHITECTURE_DESIGN.md](file:///d:/owned/ai/xiaoshuo/dramatica-flow/docs/ARCHITECTURE_DESIGN.md) - 系统架构设计文档

### 15.1 术语表

| 术语 | 定义 |
|------|------|
| OOC | Out of Character，人物行为不符合设定 |
| AI痕迹 | AI写作特有的套路词和表达方式 |
| 伏笔回收 | 前文埋设的伏笔在后续情节中得到呼应 |
| 因果链 | 事件之间的逻辑因果关系 |
| 人物弧光 | 角色从故事开始到结束的成长变化轨迹 |

---

## 16. 一键优化增强（深度分析+优化）

### 16.1 功能概述

一键优化功能现在结合了深度分析和智能优化，能够：
- 先调用LLM进行深度质量分析
- 基于分析结果生成针对性的优化
- 提供详细的质量改进报告

### 16.2 优化流程

```
用户点击"一键优化"
    ↓
检查是否已选择书籍
    ↓
计算基础质量评分（规则引擎）
    ↓
调用LLM进行深度分析（五个维度）
    ↓
提取优化问题列表（转换为 AuditIssue 对象）
    ↓
生成自定义优化提示词
    ↓
调用ReviserAgent执行优化（使用 custom_prompt 参数）
    ↓
保存优化结果到草稿
    ↓
重新计算质量评分
    ↓
展示优化对比和深度分析
```

### 16.3 深度分析维度

- **故事逻辑（plot_logic）**：因果链完整性、情节合理性、逻辑漏洞
- **人物塑造（character_consistency）**：人物行为一致性、情感变化合理性
- **语言风格（language_style）**：文笔质量、流畅度、风格一致性
- **主题契合（theme_fit）**：内容与题材匹配度、主题表达清晰度
- **创意新颖（creativity）**：情节创意、设定创新度

### 16.4 ReviserAgent增强

新增 `custom_prompt` 参数，支持自定义提示词进行优化：

```python
def revise(
    self,
    original_content: str,
    issues: list[AuditIssue],
    mode: ReviseMode = "spot-fix",
    custom_prompt: str | None = None,  # 新增参数
) -> ReviseResult:
```

**关键实现逻辑**：
- 如果提供了 `custom_prompt`，直接使用自定义提示词
- 自定义模式下的响应处理：直接返回 LLM 输出的完整内容
- 默认模式下的响应处理：解析 CHANGELOG_SEPARATOR 分隔的内容

### 16.5 API端点

**端点**：`POST /api/books/{book_id}/quality/check-and-revise/{chapter}`

**核心参数**：
- `book_id`：书籍ID（必填）
- `chapter`：章节号（必填）

**响应结构**：

```json
{
  "status": "revised",
  "original_score": 65.5,
  "new_score": 82.0,
  "revised": true,
  "changes": ["基于深度分析的质量优化"],
  "deep_check": {
    "plot_logic": {
      "score": 70,
      "comment": "...",
      "suggestions": ["建议1", "建议2"]
    },
    "character_consistency": {
      "score": 65,
      "comment": "...",
      "suggestions": ["建议1", "建议2"]
    },
    "language_style": {
      "score": 72,
      "comment": "...",
      "suggestions": ["建议1", "建议2"]
    },
    "theme_fit": {
      "score": 68,
      "comment": "...",
      "suggestions": ["建议1", "建议2"]
    },
    "creativity": {
      "score": 60,
      "comment": "...",
      "suggestions": ["建议1", "建议2"]
    },
    "overall_score": 67,
    "priority_suggestions": ["建议1", "建议2", "建议3"]
  },
  "original_dimensions": {
    "story_score": 60,
    "character_score": 65,
    "language_score": 70,
    "experience_score": 67
  },
  "new_dimensions": {
    "story_score": 80,
    "character_score": 82,
    "language_score": 85,
    "experience_score": 81
  }
}
```

### 16.6 前端交互

**API配置**：`http://localhost:8000/api`

**核心函数**：
1. `runQualityRevise(chapter)`：执行一键优化
   - 检查 currentBook 是否存在
   - 显示加载提示
   - 调用后端 API
   - 显示优化结果

2. `showDeepCheckResult(result)`：显示深度检查结果
   - 支持传入完整响应或直接传入 deep_check 对象
   - 展示五个维度的评分和分析

**错误处理**：
- 未选择书籍时提示用户
- 捕获并显示详细的错误信息

### 16.7 实现注意事项

1. **AuditIssue对象**：issues 参数必须转换为 `AuditIssue` 对象，而非字典
2. **环境变量加载**：函数开头必须调用 `_load_env()` 加载 .env 配置
3. **LLM调用**：使用 `asyncio.to_thread()` 避免阻塞主线程
4. **JSON解析容错**：深度检查结果解析失败时使用原始响应

### 16.8 与深度检查API的联动

一键优化 API 与深度检查 API (`/api/books/{book_id}/quality/deep-check/{chapter}`) 共享相同的深度分析逻辑：

```python
# 共享的深度检查提示词结构
deep_check_prompt = f"""请深度分析以下小说章节，从多个维度进行评估并提供具体的优化建议：

【小说题材】{genre}

【章节内容】
{content[:3000]}

请按以下JSON格式输出分析结果：
{{
  "plot_logic": {{...}},
  "character_consistency": {{...}},
  "language_style": {{...}},
  "theme_fit": {{...}},
  "creativity": {{...}},
  "overall_score": 0-100,
  "priority_suggestions": [...]
}}
"""
```

---

## 17. 实施建议与后续优化方向

### 17.1 当前实现状态

✅ 已完成功能：
- 四维度质量评分（故事、人物、语言、阅读体验）
- LLM深度质量分析（五个维度）
- 一键优化功能（深度分析 + 智能优化）
- 前端质量监控面板
- 全书质量趋势图

🔄 待优化项：
- 批量深度检查功能
- 质量数据持久化
- 质量预警机制
- 人工审核工作流

### 17.2 后续优化方向

1. **性能优化**
   - 添加批量检查的进度显示
   - 实现检查结果缓存
   - 添加断点续传功能

2. **功能增强**
   - 添加质量目标设定
   - 实现质量达标自动提醒
   - 添加质量报告导出功能

3. **用户体验优化**
   - 添加操作历史记录
   - 实现优化前后的内容对比
   - 添加批量优化功能