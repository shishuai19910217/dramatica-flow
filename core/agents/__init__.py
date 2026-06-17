"""
核心 Agent 模块：建筑师、写手、审计员、修订者、摘要生成器、质量评估器
修复：
- ArchitectAgent 用 pydantic 校验，不再裸 json.loads
- AuditorAgent blueprint 序列化改用 dataclasses.asdict
- AuditIssue 增加 excerpt 字段（pipeline 需要）
- WriterAgent 增加前情摘要注入参数
- QualityAgent 新增：质量评估+修订一体化 Agent
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Dict

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema
from ..types.quality import (
    QualityIssue, DimensionScore, QualityReport, 
    QualityReviseResult, GenreCriteria, GENRE_MATRIX,
    QUALITY_DIMENSIONS, CONSISTENCY_LEVELS
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. 建筑师 Agent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreWriteChecklist:
    active_characters: list[str]
    required_locations: list[str]
    resources_in_play: list[str]
    hooks_status: list[str]
    risk_scan: str


@dataclass
class ArchitectBlueprint:
    core_conflict: str
    hooks_to_advance: list[str]
    hooks_to_plant: list[str]
    emotional_journey: dict[str, str]
    chapter_end_hook: str
    pace_notes: str
    pre_write_checklist: PreWriteChecklist
    # ── 多线叙事扩展 ──
    pov_character_id: str = ""             # 本章视角角色
    thread_id: str = ""                     # 本章所属线程
    thread_context: str = ""               # 其他线程的当前状态摘要（跨线程感知）


# ── pydantic schema 用于 LLM 输出校验 ────────────────────────────────────────

class _ChecklistSchema(BaseModel):
    active_characters: list[str] = Field(default_factory=list)
    required_locations: list[str] = Field(default_factory=list)
    resources_in_play: list[str] = Field(default_factory=list)
    hooks_status: list[str] = Field(default_factory=list)
    risk_scan: str = ""

    @field_validator("active_characters", "required_locations", "resources_in_play", "hooks_status", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        if isinstance(v, dict):
            return [f"{k}: {val}" if val else k for k, val in v.items()]
        return v


class _BlueprintSchema(BaseModel):
    core_conflict: str
    hooks_to_advance: list[str] = Field(default_factory=list)
    hooks_to_plant: list[str] = Field(default_factory=list)
    emotional_journey: dict[str, str] = Field(default_factory=dict)
    chapter_end_hook: str = ""
    pace_notes: str = ""
    pre_write_checklist: _ChecklistSchema = Field(default_factory=_ChecklistSchema)
    # 多线叙事扩展
    pov_character_id: str = ""
    thread_id: str = ""
    thread_context: str = ""

    @field_validator("hooks_to_advance", "hooks_to_plant", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        return v


class ArchitectAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def plan_chapter(
        self,
        chapter_outline: ChapterOutlineSchema,
        world_context: str,
        pending_hooks: str,
        prior_chapter_summary: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
        rewrite_reason: str = "",  # 新增：重写原因
    ) -> ArchitectBlueprint:

        prior_ctx = f"\n## 上章摘要\n{prior_chapter_summary}" if prior_chapter_summary else ""

        # ── POV 视角角色（多线叙事） ──
        pov_section = ""
        resolved_pov_id = ""
        if pov_character:
            resolved_pov_id = pov_character.id
            pov_section = f"""
## 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 蓝图设计应围绕 {pov_character.name} 的视角，情感旅程以该角色为准。
"""

        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        resolved_thread_id = getattr(chapter_outline, "thread_id", "thread_main") or "thread_main"
        if thread_context.strip():
            thread_section = f"""
## 其他线程状态（跨线程感知）
{thread_context}
> 注意：确保本章事件与其他线程的时间线不冲突。
"""

        # ── 重写指导（如果提供了重写原因） ──
        rewrite_section = ""
        if rewrite_reason.strip():
            rewrite_section = f"""
## 重写指导（重要）
本章需要重写，原因：{rewrite_reason}
请根据此原因调整本章的：
- 核心冲突设计：确保冲突更加合理、有张力
- 情节走向：修正原有问题，保持逻辑连贯
- 角色行为：确保角色动机和行为一致
> 重写后的内容必须解决原有问题，同时保持与前后章节的连贯性。
"""

        prompt = f"""\
你是精通戏剧结构的故事建筑师，为写手规划本章写作蓝图。

## 章纲
- 章节：第 {chapter_outline.chapter_number} 章《{chapter_outline.title}》
- 摘要：{chapter_outline.summary}
- 必完任务：{'；'.join(chapter_outline.mandatory_tasks)}
- 情感弧：{chapter_outline.emotional_arc.get('start', '')} → {chapter_outline.emotional_arc.get('end', '')}
- 字数目标：{chapter_outline.target_words} 字
- 节拍序列：{' → '.join(b.description for b in chapter_outline.beats)}
{prior_ctx}
{pov_section}{thread_section}{rewrite_section}
## 当前世界状态
{world_context}

## 未闭合伏笔
{pending_hooks if pending_hooks.strip() else "（暂无）"}

请输出完整 JSON，字段说明：
- core_conflict：本章核心冲突（一句话，必须源于角色目标与障碍的碰撞）
- hooks_to_advance：需要在本章推进的伏笔 ID 列表
- hooks_to_plant：本章可以埋下的新伏笔描述列表（每条一句话）
- emotional_journey：{{"start": "章节开始时主角的情绪状态", "end": "章节结束时的情绪状态"}}
- chapter_end_hook：本章最后一个场景/句子的悬念钩子，驱动读者读下一章
- pace_notes：节奏建议（快/慢场景的分配，张弛安排）
- pre_write_checklist：
  - active_characters：本章登场的所有角色名列表
  - required_locations：本章涉及的地点列表
  - resources_in_play：本章涉及的道具/资源/物品列表
  - hooks_status：每条相关伏笔的当前推进状态（一句话）
  - risk_scan：最可能引发连续性错误的高风险点（具体说明）

只输出 JSON，不要任何前言、说明或 Markdown。"""

        def _call() -> ArchitectBlueprint:
            resp = self.llm.complete([
                LLMMessage("system", "你是故事建筑师，只输出合法 JSON，不输出任何说明文字。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _BlueprintSchema, "plan_chapter")
            cl_data = parsed.pre_write_checklist
            checklist = PreWriteChecklist(
                active_characters=cl_data.active_characters,
                required_locations=cl_data.required_locations,
                resources_in_play=cl_data.resources_in_play,
                hooks_status=cl_data.hooks_status,
                risk_scan=cl_data.risk_scan,
            )
            return ArchitectBlueprint(
                core_conflict=parsed.core_conflict,
                hooks_to_advance=parsed.hooks_to_advance,
                hooks_to_plant=parsed.hooks_to_plant,
                emotional_journey=parsed.emotional_journey,
                chapter_end_hook=parsed.chapter_end_hook,
                pace_notes=parsed.pace_notes,
                pre_write_checklist=checklist,
                pov_character_id=resolved_pov_id,
                thread_id=resolved_thread_id,
                thread_context=thread_context,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 写手 Agent
# ─────────────────────────────────────────────────────────────────────────────

SETTLEMENT_SEPARATOR = "===SETTLEMENT==="


@dataclass
class PostWriteSettlement:
    """写后结算表：本章对世界状态的改变"""
    resource_changes: list[str] = field(default_factory=list)
    new_hooks: list[str] = field(default_factory=list)
    resolved_hooks: list[str] = field(default_factory=list)
    relationship_changes: list[str] = field(default_factory=list)
    info_revealed: list[dict[str, str]] = field(default_factory=list)
    character_position_changes: list[dict[str, str]] = field(default_factory=list)
    emotional_changes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class WriterOutput:
    content: str
    settlement: PostWriteSettlement


WRITER_SYSTEM_PROMPT = """\
你是一位经验丰富的番茄小说签约作家，专注于{genre}题材，深谙番茄平台爆款逻辑。

## 平台核心铁律（不可违反）
1. **节奏为王**：每500字一个小起伏（小打脸、金手指生效、危机闪现、线索更新），三章一小爆、十章一大爆
2. **钩子致命**：每章结尾必须设置不可逆新危机、颠覆性新线索、宿命感新羁绊三者其一，做到非看不可
3. **情绪密集**：每3章落地1次强情绪爆点（愤怒/委屈/狂喜/揪心），情绪点绑定人性/认知碰撞
4. **人物立住**：主角必须有显性标签+隐藏反差+固化性格短板，配角功能差异化、每人有独立弧光
5. **冲突落地**：冲突必须源于角色目标与障碍的碰撞，绝对不靠巧合推进

## 语言规范（番茄调性）
- **口语化表达**：使用短句、口语化词汇，避免书面化生硬表达，符合移动端阅读习惯
- **具象化描写**：用动作+感官+细节替代抽象情绪描写（例：不说"害怕"，写"后背冷汗浸透衣衫，牙关死死绷紧"）
- **AI味清零**：彻底杜绝AI套路词（仿佛/忽然/竟然/不禁/宛如/猛地/顿时/瞬间/刹那/骤然），每3000字各最多1次
- **冗余删除**：删除多余"的、地、得"，用精准动词替代冗余修饰词
- **排版适配**：单段文字≤3行，对话单独成行，关键动作/情绪/反转单独成段

## 绝对禁止
- 元叙事（核心动机/叙事节奏/人物弧线）
- 报告式语言（分析了形势/从…角度来看/综合考虑）
- 作者说教（显然/不言而喻/毫无疑问）
- 集体反应套话（全场震惊/众人哗然/所有人都）
- 破折号「——」：全书最多用3次，珍惜使用

## 写后必须输出结算表
正文写完后，用 ===SETTLEMENT=== 分隔，输出 JSON 结算表。"""


class WriterAgent:
    def __init__(self, llm: LLMProvider, style_guide: str = "", genre: str = "玄幻"):
        self.llm = llm
        self.style_guide = style_guide
        self.genre = genre

    def write_chapter(
        self,
        scene_summaries: str,
        blueprint: ArchitectBlueprint,
        protagonist: Character,
        world_context: str,
        chapter_number: int,
        target_words: int,
        prior_summaries: str = "",
        prev_chapter_tail: str = "",
        chapter_title: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
        pending_hooks: str = "",
        causal_chain: str = "",
        emotional_arcs: str = "",
        writing_notes: str = "",
        pov_instruction: str = "",
    ) -> WriterOutput:
        system = WRITER_SYSTEM_PROMPT.format(genre=self.genre)
        if self.style_guide:
            system += f"\n\n## 文风要求\n{self.style_guide}"

        prior_ctx = ""
        if prior_summaries.strip():
            # 只取最近 3 章摘要，避免 context 过长
            lines = prior_summaries.strip().split("\n## ")
            recent = lines[-3:] if len(lines) > 3 else lines
            prior_ctx = f"\n### 前情回顾（最近章节）\n## {'## '.join(recent)}"

        # 前一章结尾衔接
        prev_section = ""
        if prev_chapter_tail.strip():
            prev_section = f"""
### 前一章结尾（衔接用）
{prev_chapter_tail}
> 以上是上一章最后 800 字，本章开头必须自然衔接，保持场景、情绪、动作的连续性。
"""

        # scene_summaries 已经是格式化好的节拍序列
        beats_str = scene_summaries

        # ── POV 视角角色（多线叙事） ──
        effective_pov = pov_character or protagonist
        pov_section = ""
        if pov_character and pov_character.id != protagonist.id:
            pov_section = f"""
### 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 重要：本章以 {pov_character.name} 的视角叙事，描写风格、感知范围、
> 情感反应均应以该角色为准。该角色不知道的信息不可描写。
"""
        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        if thread_context.strip():
            thread_section = f"""
### 其他线程状态（不可在本章直接展现，但可间接暗示）
{thread_context}
> 以上信息仅供写手把握全局节奏，不可直接告诉视角角色。
"""

        settlement_schema = """{
  "resource_changes": ["道具/资源变化，如「林尘的玉佩碎裂」"],
  "new_hooks": ["新埋下的伏笔，一句话描述"],
  "resolved_hooks": ["已回收的伏笔 ID 列表"],
  "relationship_changes": ["关系变化，如「林尘-慕雪：从-80变为-60，原因：慕雪第一次动摇」"],
  "info_revealed": [{"character_id": "角色ID", "info_key": "信息标识", "content": "角色得知了什么"}],
  "character_position_changes": [{"character_id": "角色ID", "location_id": "地点ID"}],
  "emotional_changes": [{"character_id": "角色ID", "emotion": "情绪", "intensity": 7, "trigger": "触发原因"}]
}"""

        prompt = f"""\
## 写作任务：第 {chapter_number} 章{f'《{chapter_title}》' if chapter_title else ''}

{prev_section}### 节拍序列（按顺序写完所有节拍）
{scene_summaries}
{pov_section}{thread_section}{f'''### 视角要求
{pov_instruction.strip()}
''' if pov_instruction and pov_instruction.strip() else ''}
{f'''### 写作基调（本章重要指导）
{writing_notes.strip()}
''' if writing_notes and writing_notes.strip() else ''}
### 主角
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
本章情感旅程：{blueprint.emotional_journey.get('start', '??')} → {blueprint.emotional_journey.get('end', '??')}
性格锁定（绝对不做）：{'、'.join(protagonist.behavior_lock)}

### 核心冲突（必须贯穿全章）
{blueprint.core_conflict}

### 本章结尾钩子（最后必须实现）
{blueprint.chapter_end_hook}

### 节奏建议
{blueprint.pace_notes}

### 本章登场角色
{', '.join(blueprint.pre_write_checklist.active_characters)}

### 当前世界状态
{world_context}
{prior_ctx}
{f'''### 未闭合伏笔（需要在正文中自然推进或埋设）
{pending_hooks.strip()}
''' if pending_hooks and pending_hooks.strip() else ''}
{f'''### 近期因果链（确保本章事件与已有因果关系一致）
{causal_chain[-1200:].strip()}
''' if causal_chain and causal_chain.strip() else ''}
{f'''### 情感弧线（角色情感走向，请保持延续性）
{emotional_arcs[-600:].strip()}
''' if emotional_arcs and emotional_arcs.strip() else ''}

### 高风险连续性点（写时注意）
{blueprint.pre_write_checklist.risk_scan}

### 字数要求（硬性约束，必须遵守）
- 目标字数：{target_words} 字
- 允许范围：{int(target_words*0.9)}–{int(target_words*1.1)} 字（±10%）
- 硬性上限：绝对不能超过 {int(target_words*1.2)} 字
- 硬性下限：绝对不能少于 {int(target_words*0.8)} 字
- 警告：超过上限将直接被拒绝，少于下限将被要求重写
- 策略：先规划好场景长度，避免写太多后被迫大幅删减。如果感觉内容过多，请提前精简描写。

### 节奏与钩子要求（番茄平台硬性标准）
- **节奏密度**：每500字一个小起伏（小打脸、金手指生效、危机闪现、线索更新），杜绝平淡水文
- **结尾钩子**：本章结尾必须设置以下三者其一：
  1. 不可逆新危机（主角陷入绝境、关键人物死亡、核心目标受阻）
  2. 颠覆性新线索（身世秘密曝光、反转真相揭示、隐藏反派现身）
  3. 宿命感新羁绊（命运对决开启、情感关系剧变、生死契约缔结）
- **情绪爆点**：本章至少设置1次强情绪爆点（愤怒/委屈/狂喜/揪心），并绑定人性/认知层面的碰撞
- **排版适配**：单段文字≤3行，对话单独成行，关键动作/情绪/反转单独成段

### 语言风格要求（番茄调性）
- 使用短句口语化表达，避免书面化生硬语言
- 用动作+感官+细节替代抽象情绪描写
- 彻底杜绝AI套路词（仿佛/忽然/竟然/不禁/宛如/猛地/顿时/瞬间/刹那/骤然）
- 删除多余"的、地、得"，用精准动词替代冗余修饰词
- **绝对禁止使用特殊符号**：禁止使用 ◆ ● ■ ★ ☆ ♥ ◆ ○ ● ◇ ◆ 等任何装饰性符号，禁止使用emoji表情，禁止使用Unicode装饰字符

---
请直接开始写正文，写完后输出：
{SETTLEMENT_SEPARATOR}
{settlement_schema}"""

        def _call() -> WriterOutput:
            resp = self.llm.complete([
                LLMMessage("system", system),
                LLMMessage("user", prompt),
            ])
            parts = resp.content.split(SETTLEMENT_SEPARATOR, 1)
            content = parts[0].strip()

            # ── 字数自动处理（硬性约束闭环） ──
            content_length = len(content)
            max_length = int(target_words * 1.2)  # 硬性上限
            min_length = int(target_words * 0.8)  # 硬性下限
            ideal_length = int(target_words * 1.1)  # 理想上限
            
            if content_length > max_length:
                # 超过硬性上限，触发压缩重写机制
                over_ratio = content_length / target_words
                if over_ratio > 1.5:
                    # 严重超字数（超过50%），触发AI压缩重写
                    content = self._compress_chapter(content, target_words)
                else:
                    # 轻微超字数，智能截断
                    content = self._smart_truncate(content, ideal_length)
            
            elif content_length < min_length:
                # 少于下限，触发补写机制
                content = self._expand_chapter(content, target_words)

            settlement = PostWriteSettlement()
            if len(parts) > 1:
                try:
                    raw = json.loads(parts[1].strip())
                    settlement = PostWriteSettlement(
                        resource_changes=raw.get("resource_changes", []),
                        new_hooks=raw.get("new_hooks", []),
                        resolved_hooks=raw.get("resolved_hooks", []),
                        relationship_changes=raw.get("relationship_changes", []),
                        info_revealed=raw.get("info_revealed", []),
                        character_position_changes=raw.get("character_position_changes", []),
                        emotional_changes=raw.get("emotional_changes", []),
                    )
                except Exception:
                    pass  # 结算表解析失败不崩溃，用默认空值

            return WriterOutput(content=content, settlement=settlement)

        return with_retry(_call)

    def _smart_truncate(self, content: str, target_length: int) -> str:
        """智能截断：在句子结尾或段落结尾截断，保持内容完整性"""
        if len(content) <= target_length:
            return content
        
        # 尝试在句子结尾截断
        for i in range(target_length, min(len(content), target_length + 100)):
            if content[i] in ('。', '！', '？', '；', '\n', ' '):
                return content[:i+1].strip()
        
        # 如果没找到合适位置，在段落边界截断
        for i in range(target_length, min(len(content), target_length + 50)):
            if content[i] == '\n':
                return content[:i].strip()
        
        # 兜底：直接截断并添加省略号
        return content[:target_length].strip() + "..."
    
    def _compress_chapter(self, content: str, target_words: int) -> str:
        """压缩重写：让AI将内容压缩到目标字数"""
        compress_prompt = f"""请将以下章节内容压缩精简到约{target_words}字，保持故事完整性和连贯性：

【原文】
{content}

【要求】
1. 删除冗余描写和重复内容
2. 合并相似场景
3. 精简对话，但保留关键信息
4. 保持情节连贯和结尾钩子
5. 不要改变故事主线和人物关系

请直接输出压缩后的正文："""
        
        resp = self.llm.complete([
            LLMMessage("system", "你是专业的小说编辑，擅长精简压缩小说内容，保持故事核心不变。"),
            LLMMessage("user", compress_prompt),
        ])
        
        compressed = resp.content.strip()
        # 再次检查，如果仍超字数，进行智能截断
        if len(compressed) > int(target_words * 1.2):
            compressed = self._smart_truncate(compressed, int(target_words * 1.1))
        
        return compressed
    
    def _expand_chapter(self, content: str, target_words: int) -> str:
        """补写扩展：让AI将内容补充到目标字数"""
        expand_prompt = f"""请将以下章节内容扩展到约{target_words}字，保持故事连贯性：

【现有内容】
{content}

【要求】
1. 增加细节描写（环境、动作、心理）
2. 丰富对话内容
3. 添加过渡场景
4. 保持情节连贯
5. 不要改变故事主线

请直接输出扩展后的正文："""
        
        resp = self.llm.complete([
            LLMMessage("system", "你是专业的小说作家，擅长丰富扩展小说内容，保持故事流畅。"),
            LLMMessage("user", expand_prompt),
        ])
        
        expanded = resp.content.strip()
        # 检查是否超过上限
        if len(expanded) > int(target_words * 1.2):
            expanded = self._smart_truncate(expanded, int(target_words * 1.1))
        
        return expanded


# ─────────────────────────────────────────────────────────────────────────────
# 3. 审计员 Agent
# ─────────────────────────────────────────────────────────────────────────────

AuditSeverity = Literal["critical", "warning", "info"]


@dataclass
class AuditIssue:
    dimension: str
    severity: AuditSeverity
    description: str
    location: str | None = None   # 问题在原文的关键句引用
    suggestion: str | None = None
    excerpt: str | None = None    # 触发规则的文本片段（验证器用）


@dataclass
class AuditReport:
    chapter_number: int
    passed: bool
    issues: list[AuditIssue]
    overall_note: str

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class _AuditIssueSchema(BaseModel):
    dimension: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    location: str | None = None
    suggestion: str | None = None


class _AuditReportSchema(BaseModel):
    chapter_number: int
    passed: bool
    issues: list[_AuditIssueSchema] = Field(default_factory=list)
    overall_note: str = ""


# ── 番茄五大维度量化审计框架（对标平台审核标准） ──────────────────────────────
# 维度1：钩子与章节留存（20分）
# 维度2：剧情节奏与紧凑度（20分）
# 维度3：语言风格与移动端阅读性（20分）
# 维度4：逻辑、人设与世界观自洽（20分）
# 维度5：内容吸引力与核心看点（20分）

# AI套路词列表（用于检测AI味）
AI_WORDS = ["仿佛", "忽然", "竟然", "不禁", "宛如", "猛地", "顿时", "瞬间", "刹那", "骤然"]

# AI味替换映射
AI_WORD_REPLACEMENTS = {
    "仿佛": "好像",
    "忽然": "突然",
    "竟然": "居然",
    "不禁": "忍不住",
    "宛如": "好像",
    "猛地": "突然",
    "顿时": "立刻",
    "瞬间": "转眼",
    "刹那": "转眼",
    "骤然": "突然",
}

# 抽象情绪到具象动作的映射
EMOTION_TO_ACTION = {
    "害怕": ["后背冷汗浸透衣衫", "牙关死死绷紧", "指尖微微颤抖", "心脏狂跳不止"],
    "愤怒": ["拳头攥得咯咯响", "太阳穴突突直跳", "眼神骤然变冷", "咬牙切齿"],
    "悲伤": ["眼眶瞬间泛红", "喉咙像是被堵住", "肩膀微微颤抖", "泪水无声滑落"],
    "喜悦": ["嘴角不自觉上扬", "眼睛瞬间亮了", "脚步都轻快起来", "心里像喝了蜜"],
    "震惊": ["瞳孔骤然收缩", "猛地站起身来", "呼吸都停滞了", "大脑一片空白"],
}

# 报告式语言替换
REPORT_LANGUAGE_REPLACEMENTS = {
    "分析了形势": "想了想当前情况",
    "从…角度来看": "换个角度想",
    "综合考虑": "权衡之后",
    "显然": "",
    "不言而喻": "",
    "毫无疑问": "",
}

# 集体反应套话替换
COLLECTIVE_PHRASES = [
    "全场震惊", "众人哗然", "所有人都", "全场瞩目", "众人皆知",
    "大家都", "所有人", "全场鸦雀无声", "一片哗然",
]


def detect_ai_flavor(text: str) -> list[tuple[str, int, str]]:
    """检测文本中的AI味"""
    issues = []
    
    # 检测AI套路词
    for word in AI_WORDS:
        count = text.count(word)
        if count > 0:
            issues.append((word, count, f"AI套路词'{word}'出现{count}次"))
    
    # 检测报告式语言
    for phrase, replacement in REPORT_LANGUAGE_REPLACEMENTS.items():
        if phrase in text:
            count = text.count(phrase)
            issues.append((phrase, count, f"报告式语言'{phrase}'出现{count}次"))
    
    # 检测集体反应套话
    for phrase in COLLECTIVE_PHRASES:
        if phrase in text:
            count = text.count(phrase)
            issues.append((phrase, count, f"集体反应套话'{phrase}'出现{count}次"))
    
    return issues


def reduce_ai_flavor(text: str) -> str:
    """降低文本中的AI味"""
    # 替换AI套路词
    for word, replacement in AI_WORD_REPLACEMENTS.items():
        text = text.replace(word, replacement)
    
    # 替换报告式语言
    for phrase, replacement in REPORT_LANGUAGE_REPLACEMENTS.items():
        text = text.replace(phrase, replacement)
    
    # 删除集体反应套话
    for phrase in COLLECTIVE_PHRASES:
        text = text.replace(phrase, "")
    
    return text


def convert_to_conversational(text: str) -> str:
    """将书面化语言转换为口语化"""
    # 替换抽象情绪为具象动作
    for emotion, actions in EMOTION_TO_ACTION.items():
        if emotion in text:
            # 随机选择一个具象动作替换
            import random
            action = random.choice(actions)
            text = text.replace(f"心里{emotion}", action)
            text = text.replace(f"感到{emotion}", action)
            text = text.replace(f"十分{emotion}", action)
            text = text.replace(f"非常{emotion}", action)
            text = text.replace(f"心里十分{emotion}", action)
            text = text.replace(f"心里非常{emotion}", action)
    
    # 删除冗余的"的、地、得"
    text = text.replace("非常的", "非常")
    text = text.replace("十分的", "十分")
    text = text.replace("特别的", "特别")
    
    # 简化复杂句式
    text = text.replace("进行了", "做了")
    text = text.replace("进行", "做")
    text = text.replace("使得", "让")
    text = text.replace("因此", "所以")
    text = text.replace("然而", "但")
    text = text.replace("与此同时", "这时")
    
    return text


def optimize_paragraphs(text: str, max_lines: int = 3) -> str:
    """优化段落排版，确保单段≤max_lines行"""
    paragraphs = text.split("\n\n")
    optimized = []
    
    for para in paragraphs:
        lines = para.split("\n")
        # 如果段落行数超过限制，进行拆分
        if len(lines) > max_lines:
            # 在合适的位置拆分（逗号、句号、分号后）
            current_chunk = []
            for line in lines:
                current_chunk.append(line)
                if len(current_chunk) >= max_lines and (line.endswith("。") or line.endswith("！") or line.endswith("？") or line.endswith("；")):
                    optimized.append("\n".join(current_chunk))
                    current_chunk = []
            if current_chunk:
                optimized.append("\n".join(current_chunk))
        else:
            optimized.append(para)
    
    return "\n\n".join(optimized)

# 评分梯度标准
SCORE_GRADIENTS = {
    "excellent": (18, 20),
    "good": (12, 17),
    "fair": (6, 11),
    "poor": (0, 5),
}

def calculate_dimension_score(issue_count: int, severity_counts: dict) -> int:
    """计算单维度评分（0-20分）"""
    if issue_count == 0:
        return 20
    score = 20
    # critical 问题：每个扣5分
    score -= severity_counts.get("critical", 0) * 5
    # warning 问题：每个扣2分
    score -= severity_counts.get("warning", 0) * 2
    # info 问题：每个扣0.5分
    score -= severity_counts.get("info", 0) * 0.5
    return max(0, min(20, round(score)))

def get_risk_level(score: int) -> str:
    """根据分数获取风险等级"""
    if score >= 18:
        return "正常"
    elif score >= 12:
        return "轻微风险"
    elif score >= 6:
        return "中度风险"
    else:
        return "高危风险"

AUDIT_DIMENSIONS = [
    # ── 维度1：钩子与章节留存 ──
    "结尾钩子（必须落地新危机/新悬念/新反转/新伏笔/新冲突其一，禁止平淡收尾）",
    "钩子有效性（钩子是否具备不可逆性、颠覆性、宿命感）",
    # ── 维度2：剧情节奏与紧凑度 ──
    "节奏密度（每500字应有小起伏，避免平淡水文）",
    "冲突质量（每个场景的冲突是否源于角色目标与障碍的碰撞）",
    "无效注水（纯环境堆砌、无意义心理空想、重复赘述、空泛铺垫占比≤20%）",
    # ── 维度3：语言风格与移动端阅读性 ──
    "口语化表达（避免书面化生硬语言，符合番茄调性）",
    "AI味检测（AI套路词密度、套话、元叙事、报告式语言）",
    "排版适配（单段≤3行，对话单独成行，关键内容突出）",
    "语句流畅度（无病句错字、行文自然）",
    # ── 维度4：逻辑、人设与世界观自洽 ──
    "人设一致性（角色行为是否符合性格锁定，无OOC）",
    "信息边界（角色是否知道不应知道的信息）",
    "连续性（角色位置/道具/时间线/称谓/数值前后一致）",
    "世界观自洽（符合设定规则，无逻辑矛盾）",
    "伏笔管理（新开伏笔有铺垫，已声明回收的伏笔在正文中落地）",
    "因果一致性（每个事件的发生有前因，不靠巧合推进）",
    # ── 维度5：内容吸引力与核心看点 ──
    "爽点密度（每3章至少1次强情绪爆点：愤怒/委屈/狂喜/揪心）",
    "情绪起伏（情绪变化自然，有张力）",
    "配角塑造（配角有独立存在感，无工具人问题）",
    "剧情看点（冲突持续，无流水账）",
]


class AuditorAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm  # 应传入 temperature=0 的实例

    def audit_chapter(
        self,
        chapter_content: str,
        chapter_number: int,
        blueprint: ArchitectBlueprint,
        truth_context: str,
        settlement: PostWriteSettlement,
        cross_thread_context: str = "",
    ) -> AuditReport:

        # 安全序列化 blueprint（dataclass → dict，避免 json.dumps 崩溃）
        blueprint_dict = dataclasses.asdict(blueprint)
        blueprint_summary = f"""\
- 核心冲突：{blueprint.core_conflict}
- 情感旅程：{blueprint.emotional_journey.get('start','')} → {blueprint.emotional_journey.get('end','')}
- 必须推进伏笔：{blueprint.hooks_to_advance}
- 计划埋下伏笔：{blueprint.hooks_to_plant}
- 结尾钩子：{blueprint.chapter_end_hook}
- 风险点：{blueprint.pre_write_checklist.risk_scan}
- 登场角色：{blueprint.pre_write_checklist.active_characters}"""

        settlement_summary = f"""\
- 资源变化：{settlement.resource_changes}
- 新开伏笔：{settlement.new_hooks}
- 回收伏笔：{settlement.resolved_hooks}
- 关系变化：{settlement.relationship_changes}
- 信息揭示：{settlement.info_revealed}
- 位置变化：{settlement.character_position_changes}
- 情感变化：{settlement.emotional_changes}"""

        dimensions_str = "\n".join(f"{i+1}. {d}" for i, d in enumerate(AUDIT_DIMENSIONS))

        # 正文截断（避免超 token）
        content_for_audit = chapter_content
        if len(chapter_content) > 6000:
            content_for_audit = chapter_content[:3000] + "\n\n...[中间省略]...\n\n" + chapter_content[-2000:]

        # ── 跨线程上下文注入（多线叙事） ──
        cross_thread_section = ""
        if cross_thread_context.strip():
            cross_thread_section = f"""
### 跨线程一致性参照
以下是其他线程最近的时间轴和因果链，用于检测跨线程冲突：
{cross_thread_context[:2000]}

> 请特别检查：
> - 同一角色是否同时出现在不同地点
> - 不同线程中的时间线是否矛盾
> - 一个线程的事件是否与另一个线程的已确立事实冲突
"""

        prompt = f"""\
## 叙事审计：第 {chapter_number} 章

### 四大审计维度框架（逐一检查，不可遗漏）

#### 第一维度：大纲对齐审计
- 对比：最终正文 VS 章节细纲
- 检测：剧情是否跑偏、是否漏关键情节、是否加无关注水内容、mandatory_tasks 是否完成

#### 第二维度：人设逻辑审计
- 对比：正文 VS Dramatica 人物设定 & 四大故事线
- 检测：人设崩塌、性格前后不一、主线丢失、逻辑BUG、信息越界

#### 第三维度：节奏合规审计
- 检测：是否丢失钩子、是否太平淡、是否违背三幕式节奏、章末悬念是否有效

#### 第四维度：逻辑性审计
- 检测：描述是否符合常识和设定、语义是否精准、避免歧义或模糊表述、修饰词是否使用恰当
- 示例：「死在人手里」应明确是「死在自己人手里」或「死在敌人手里」

### 具体审计检查项
{dimensions_str}

### 章节正文
{content_for_audit}

### 写前蓝图（参照标准）
{blueprint_summary}
{cross_thread_section}
### 写后结算表（需与正文交叉验证）
{settlement_summary}

### 真相文件（连续性参照）
{truth_context[:3000] if len(truth_context) > 3000 else truth_context}

## 评判标准
- critical：叙事逻辑断裂、明显 OOC、重大连续性错误、mandatory_task 完全未完成、跨线程时间线矛盾、人设崩塌
- warning：轻微节奏问题、AI 痕迹、伏笔处理不当、情感弧线偏差、轻微偏离大纲
- info：可选优化建议

## 审计动作参考（用于建议修复方式）
- 轻微偏离：自动改写修正正文，贴合大纲
- 中度偏离：局部重写段落
- 严重偏离：拒绝输出、回滚上一级 Agent 重绘大纲

## 输出格式（严格 JSON）
{{
  "chapter_number": {chapter_number},
  "passed": true,
  "issues": [
    {{
      "dimension": "维度名称",
      "severity": "critical",
      "description": "具体问题描述，指出原文哪里出了问题",
      "location": "原文关键句引用（30字以内）",
      "suggestion": "具体修复建议"
    }}
  ],
  "overall_note": "整体评价（1-2句话）"
}}

只输出 JSON，不要任何说明。"""

        def _call() -> AuditReport:
            resp = self.llm.complete([
                LLMMessage(
                    "system",
                    "你是严格的叙事审计员，专注叙事质量，"
                    "对 critical 问题零容忍但不制造假阳性。"
                    "只输出合法 JSON，不输出任何说明文字。",
                ),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _AuditReportSchema, "audit_chapter")
            issues = [
                AuditIssue(
                    dimension=i.dimension,
                    severity=i.severity,  # type: ignore
                    description=i.description,
                    location=i.location,
                    suggestion=i.suggestion,
                )
                for i in parsed.issues
            ]
            passed = not any(i.severity == "critical" for i in issues)
            return AuditReport(
                chapter_number=parsed.chapter_number,
                passed=passed,
                issues=issues,
                overall_note=parsed.overall_note,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 4. 修订者 Agent
# ─────────────────────────────────────────────────────────────────────────────

ReviseMode = Literal["spot-fix", "rewrite-section", "polish"]

CHANGELOG_SEPARATOR = "===CHANGELOG==="

_MODE_INSTRUCTIONS: dict[str, str] = {
    "spot-fix":
        "只修改有问题的句子/段落，其余正文一字不动。"
        "保持原段落结构，只替换问题文本。",
    "rewrite-section":
        "重写包含问题的段落（前后各保留一段作为锚点），"
        "保持整体情节不变。",
    "polish":
        "在不改变情节的前提下提升文笔流畅度，"
        "禁止增删段落、修改角色名、加入新情节。",
}


@dataclass
class ReviseResult:
    content: str
    change_log: list[str]


class ReviserAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def revise(
        self,
        original_content: str,
        issues: list[AuditIssue],
        mode: ReviseMode = "spot-fix",
        custom_prompt: str | None = None,
        target_words: Optional[int] = None,  # 新增：目标字数参数
    ) -> ReviseResult:
        critical = [i for i in issues if i.severity == "critical"]
        warnings  = [i for i in issues if i.severity == "warning"]

        if not critical and not warnings and not target_words:
            return ReviseResult(
                content=original_content,
                change_log=["无需要修复的问题"],
            )

        # 专门处理字数偏差问题
        word_count_issue = None
        detected_target_words = None
        
        # 检测并提取字数偏差信息 - 需要同时检查 dimension 和 description
        import re
        for i in critical + warnings:
            if ("WORD_COUNT_DEVIATION" in i.dimension or 
                "WORD_COUNT_DEVIATION" in i.description or 
                "字数偏差" in i.dimension or 
                "字数偏差" in i.description):
                word_count_issue = i
                # 从描述中提取目标字数
                match = re.search(r"目标\s*(\d+)\s*字", i.description)
                if match:
                    detected_target_words = int(match.group(1))
                break
        
        # 优先使用传入的 target_words 参数，其次使用从问题中检测到的目标字数
        effective_target_words = target_words if target_words is not None else detected_target_words

        # 构建问题列表
        issue_lines = []
        for i in (critical + warnings):
            if i == word_count_issue:
                continue  # 字数偏差问题单独处理
            line = f"- [{i.severity.upper()}] {i.dimension}：{i.description}"
            if i.location:
                line += f"\n  原文位置：「{i.location}」"
            if i.suggestion:
                line += f"\n  修复建议：{i.suggestion}"
            issue_lines.append(line)

        # 如果有目标字数，添加字数约束提示（始终传递，而不仅限于检测到字数偏差时）
        word_count_instruction = ""
        if effective_target_words:
            current_words = len(original_content)
            deviation = abs(current_words - effective_target_words) / effective_target_words
            is_too_long = current_words > effective_target_words * 1.2
            is_too_short = current_words < effective_target_words * 0.8
            
            # 如果已有字数偏差问题，按照原有逻辑处理；否则仅作为参考约束
            if word_count_issue:
                if is_too_long:
                    operation_text = "适当精简压缩内容，删除冗余描写，保持核心情节"
                    action_text = "精简"
                else:
                    operation_text = "扩充内容，增加细节描写，丰富情节"
                    action_text = "扩充"
                
                word_count_instruction = f"""
## 特别注意：字数调整要求
- 当前字数：{current_words} 字
- 目标字数：{effective_target_words} 字
- 操作：{operation_text}
- 要求：请直接对全文进行{action_text}，字数接近目标字数，保持剧情走向和核心内容完全不变。
"""
            else:
                # 没有检测到字数偏差问题，但有目标字数作为参考
                word_count_instruction = f"""
## 字数参考约束
- 当前字数：{current_words} 字
- 目标字数：{effective_target_words} 字
- 要求：修订时请尽量保持字数在目标字数的 ±20% 范围内（{int(effective_target_words*0.8)} - {int(effective_target_words*1.2)} 字），避免大幅增减字数。
"""

        # 如果有自定义提示词，直接使用
        if custom_prompt:
            prompt = custom_prompt
        else:
            # 使用默认提示词
            prompt = f"""\
## 修订任务
模式：{mode}
规则：{_MODE_INSTRUCTIONS[mode]}
硬约束：不得引入新情节，不得修改角色名，不得改变情节走向。

{word_count_instruction}

## 需修订的问题
{chr(10).join(issue_lines) if issue_lines else "（无其他问题，只需调整字数）"}

## 原文
{original_content}

---
直接输出修订后的完整正文（不要任何前言），然后输出：
{CHANGELOG_SEPARATOR}
["改动说明1", "改动说明2", ...]"""

        def _call() -> ReviseResult:
            # 构建系统消息
            system_content = "你是专业的小说编辑和修订者。"
            if custom_prompt:
                system_content = "你是专业的小说编辑和修订者，请根据用户提供的分析和要求进行优化。"
            else:
                system_content = f"你是精准的小说修订者，模式：{mode}。{_MODE_INSTRUCTIONS[mode]}直接输出修订后正文，不要任何前言。"
            
            resp = self.llm.complete([
                LLMMessage("system", system_content),
                LLMMessage("user", prompt),
            ])
            
            # 处理响应
            if custom_prompt:
                # 自定义提示词模式：直接返回内容
                content = resp.content.strip()
                change_log = ["基于深度分析的质量优化"]
            else:
                # 默认模式：解析变更日志
                parts = resp.content.split(CHANGELOG_SEPARATOR, 1)
                content = parts[0].strip()
                change_log: list[str] = []
                if len(parts) > 1:
                    try:
                        change_log = json.loads(parts[1].strip())
                    except Exception:
                        change_log = [parts[1].strip()[:200]]
            
            return ReviseResult(content=content, change_log=change_log)

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 5. 摘要 Agent（新增）
# 写完章节后自动生成章节摘要，注入 chapter_summaries.md
# ─────────────────────────────────────────────────────────────────────────────

class _SummarySchema(BaseModel):
    chapter_number: int
    title: str
    summary: str               # 200字以内的情节摘要
    key_events: list[str]      # 关键事件列表
    characters_appeared: list[str]
    state_changes: list[str]   # 世界状态变化（位置/关系/信息）
    hook_updates: list[str]    # 伏笔动态（新开/推进/回收）
    emotional_note: str        # 主角本章情感变化一句话


class SummaryAgent:
    """章节摘要生成器，写完章节后调用，产出注入 chapter_summaries.md 的内容"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def generate_summary(
        self,
        chapter_content: str,
        chapter_number: int,
        chapter_title: str,
        settlement: PostWriteSettlement,
    ) -> _SummarySchema:

        content_excerpt = chapter_content[:4000]
        if len(chapter_content) > 4000:
            content_excerpt += "\n...(截断)"

        # JSON模板需要单独定义，避免与f-string冲突
        json_template = '''
{{
  "chapter_number": __CHAPTER_NUMBER__,
  "title": "__CHAPTER_TITLE__",
  "summary": "200字以内的情节摘要，说清楚发生了什么、谁做了什么决定",
  "key_events": ["关键事件1", "关键事件2"],
  "characters_appeared": ["出场角色名"],
  "state_changes": ["世界状态变化，如「林尘到达青峰山」「林尘得知灵根封印」"],
  "hook_updates": ["伏笔动态，如「新开：玉佩发热之谜」「推进：退婚之仇」"],
  "emotional_note": "主角本章情感轨迹一句话，如「从屈辱到坚定」"
}}
'''.replace('__CHAPTER_NUMBER__', str(chapter_number)).replace('__CHAPTER_TITLE__', chapter_title)

        prompt = f"""\
请为以下章节生成结构化摘要，供后续章节写作时作上下文参考。

## 章节正文（第 {chapter_number} 章《{chapter_title}》）
{content_excerpt}

## 写后结算表（已知的状态变化）
资源变化：{settlement.resource_changes}
新开伏笔：{settlement.new_hooks}
回收伏笔：{settlement.resolved_hooks}
关系变化：{settlement.relationship_changes}
信息揭示：{settlement.info_revealed}

## 输出要求（JSON）
{json_template.strip()}

只输出 JSON。"""

        def _call() -> _SummarySchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是叙事编辑，生成精准的章节摘要，只输出 JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _SummarySchema, "generate_summary")

        return with_retry(_call)

    def format_for_truth_file(self, summary: _SummarySchema) -> str:
        """格式化为写入 chapter_summaries.md 的 Markdown"""
        lines = [
            f"\n## 第 {summary.chapter_number} 章《{summary.title}》\n",
            f"{summary.summary}\n\n",
            f"**出场角色**：{', '.join(summary.characters_appeared)}\n\n",
            "**关键事件**：\n" + "\n".join(f"- {e}" for e in summary.key_events) + "\n\n",
            "**状态变化**：\n" + "\n".join(f"- {c}" for c in summary.state_changes) + "\n\n",
            "**伏笔动态**：\n" + "\n".join(f"- {h}" for h in summary.hook_updates) + "\n\n",
            f"**情感**：{summary.emotional_note}\n",
            "---\n",
        ]
        return "".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 6. 质量评估 Agent（新增）
# 职责：对章节进行全面质量评估（六个核心维度 + 六大连贯性层次）+ 自动修订
# ─────────────────────────────────────────────────────────────────────────────

class _DimensionScoreSchema(BaseModel):
    dimension: str
    score: int
    max_score: int = 100
    issues: List[dict] = Field(default_factory=list)
    weight: float = 1.0


class _QualityReportSchema(BaseModel):
    chapter_number: int
    overall_score: int
    dimension_scores: List[_DimensionScoreSchema] = Field(default_factory=list)
    consistency_scores: List[_DimensionScoreSchema] = Field(default_factory=list)
    genre: str
    genre_fit_score: int
    improvement_suggestions: List[str] = Field(default_factory=list)


class QualityAgent:
    """
    质量评估 Agent（内置修订功能）
    
    职责：
        1. 对章节进行全面的质量评估（六个核心维度 + 六大连贯性层次）
        2. 根据评估结果自动修订内容（参考 ReviserAgent）
    
    与其他 Agent 的协作关系：
        - AuditorAgent：专注叙事质量审计（深度分析，输出问题列表）
        - QualityAgent：专注综合质量评估 + 修订（输出质量分数 + 修订后内容）
        - SummaryAgent：基于修订后的最终内容生成摘要（最后一个处理环节）
    
    架构一致性：遵循现有 Agent 模式（ArchitectAgent/WriterAgent/AuditorAgent）
    """
    
    ReviseMode = Literal["spot-fix", "rewrite-section", "polish"]
    
    DIMENSIONS = ["情节", "人物", "设定", "语言", "阅读体验", "类型适配"]
    
    CONSISTENCY_LEVELS = ["时间", "空间", "逻辑", "情绪", "信息", "风格"]
    
    MAX_REVISE_ROUNDS = 2
    
    def __init__(self, llm: LLMProvider):
        """
        初始化质量评估 Agent
        
        Args:
            llm: LLM 提供者（建议传入 temperature=0 的实例确保评分客观）
        """
        self.llm = llm
    
    def evaluate_chapter(
        self,
        chapter_content: str,
        chapter_number: int,
        genre: str,
        blueprint: ArchitectBlueprint,
        truth_context: str,
        settlement: PostWriteSettlement,
        prev_chapter_content: str = "",
        cross_thread_context: str = "",
        audit_report: Optional[AuditReport] = None,
        auto_revise: bool = True,
        target_words: Optional[int] = None,  # 新增：目标字数参数
    ) -> tuple[str, QualityReport]:
        """
        执行章节质量评估（借鉴 AuditorAgent.audit_chapter() 参数设计）
        
        Args:
            chapter_content: 章节正文
            chapter_number: 章节编号
            genre: 小说类型（悬疑/言情/科幻/恐怖/网文）
            blueprint: 建筑师蓝图（评估参照标准）
            truth_context: 真相文件上下文（设定/人物一致性）
            settlement: 写后结算表（状态变化合理性检查）
            prev_chapter_content: 上一章内容（连贯性检查）
            cross_thread_context: 跨线程上下文（多线叙事一致性）
            audit_report: 审计报告（可复用结果，避免重复分析）
            auto_revise: 是否自动根据评估结果进行修订
            target_words: 目标字数（可选），用于字数约束检查
        
        Returns:
            Tuple[str, QualityReport]: (修订后的正文, 质量评估报告)
        """
        content_for_eval = chapter_content
        if len(chapter_content) > 6000:
            content_for_eval = chapter_content[:3000] + "\n\n...[中间省略]...\n\n" + chapter_content[-2000:]
        
        blueprint_summary = f"""\
- 核心冲突：{blueprint.core_conflict}
- 情感旅程：{blueprint.emotional_journey.get('start','')} → {blueprint.emotional_journey.get('end','')}
- 必须推进伏笔：{blueprint.hooks_to_advance}
- 计划埋下伏笔：{blueprint.hooks_to_plant}
- 结尾钩子：{blueprint.chapter_end_hook}
- 风险点：{blueprint.pre_write_checklist.risk_scan}
- 登场角色：{blueprint.pre_write_checklist.active_characters}"""
        
        settlement_summary = f"""\
- 资源变化：{settlement.resource_changes}
- 新开伏笔：{settlement.new_hooks}
- 回收伏笔：{settlement.resolved_hooks}
- 关系变化：{settlement.relationship_changes}
- 信息揭示：{settlement.info_revealed}
- 位置变化：{settlement.character_position_changes}
- 情感变化：{settlement.emotional_changes}"""
        
        audit_summary = ""
        if audit_report:
            audit_summary = f"""
### 审计报告（参考）
- 审计是否通过：{'通过' if audit_report.passed else '未通过'}
- Critical 问题数：{audit_report.critical_count}
- Warning 问题数：{audit_report.warning_count}
"""
        
        genre_criteria = self._get_genre_criteria(genre)
        
        prompt = f"""\
## 质量评估任务：第 {chapter_number} 章

### 六个核心评判维度
1. **情节维度**：开篇冲突建立情况、因果链条完整性、节奏张弛、结局呼应
2. **人物维度**：主角欲望与缺陷、配角独立性（独立名字+动机+行动）、反派逻辑、人物弧光
3. **设定维度**：设定新意（与常见设定对比）、逻辑自洽（规则一致性）、规则与代价、服务故事
4. **语言维度**：视觉描写丰富度、感官细节密度、比喻新颖度、句式变化
5. **阅读体验维度**：结尾钩子强度、信息密度、悬念设置、情感共鸣
6. **类型适配维度**：{', '.join(genre_criteria.criteria)}

### 六大连贯性层次
1. **时间连贯性**：时间线清晰、倒叙/插叙标记、时间跳跃说明
2. **空间连贯性**：移动交代、场景切换过渡、空间关系合理
3. **逻辑连贯性**：因果完整性、动机合理性、规则一致性、能力成长过程
4. **情绪连贯性**：情绪反应匹配、情绪转变过渡、性格一致性
5. **信息连贯性**：能力获得过程、信息来源交代、物品连续性
6. **风格连贯性**：语言风格统一、叙事视角统一、命名规则统一

### 类型特征矩阵（{genre}）
{chr(10).join(f"- {k}: {v*100:.0f}%" for k, v in genre_criteria.weights.items())}

### 章节正文
{content_for_eval}

### 写前蓝图
{blueprint_summary}

{audit_summary}
### 写后结算表
{settlement_summary}

### 真相文件（上下文参考）
{truth_context[:2000]}

### 上一章内容（连贯性参考）
{prev_chapter_content[:1000] if prev_chapter_content else "（无）"}

### 评判标准
- critical：严重影响叙事质量的问题（如因果断裂、人设崩塌、规则冲突）
- warning：需要改进但不影响核心的问题（如节奏问题、语言瑕疵）
- info：优化建议（非问题）

### 输出格式（JSON）
{{
  "chapter_number": {chapter_number},
  "overall_score": 0-100,
  "dimension_scores": [
    {{"dimension": "情节", "score": 85, "issues": [
      {{"severity": "warning", "description": "节奏稍显拖沓", "suggestion": "增加紧张感"}}
    ]}}
  ],
  "consistency_scores": [
    {{"dimension": "逻辑", "score": 90, "issues": []}}
  ],
  "genre": "{genre}",
  "genre_fit_score": 80,
  "improvement_suggestions": ["建议1", "建议2"]
}}

只输出 JSON，不要任何说明文字。"""
        
        def _call() -> tuple[str, QualityReport]:
            resp = self.llm.complete([
                LLMMessage("system", "你是专业的小说质量评估师，输出严格符合 JSON 格式的评估报告，不输出任何说明文字。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _QualityReportSchema, "evaluate_chapter")
            
            dimension_scores = []
            for ds in parsed.dimension_scores:
                issues = []
                for issue in ds.issues:
                    issues.append(QualityIssue(
                        severity=issue.get("severity", "info"),
                        description=issue.get("description", ""),
                        location=issue.get("location"),
                        suggestion=issue.get("suggestion"),
                    ))
                dimension_scores.append(DimensionScore(
                    dimension=ds.dimension,
                    score=ds.score,
                    max_score=ds.max_score,
                    issues=issues,
                    weight=ds.weight,
                ))
            
            consistency_scores = []
            for cs in parsed.consistency_scores:
                issues = []
                for issue in cs.issues:
                    issues.append(QualityIssue(
                        severity=issue.get("severity", "info"),
                        description=issue.get("description", ""),
                        location=issue.get("location"),
                        suggestion=issue.get("suggestion"),
                    ))
                consistency_scores.append(DimensionScore(
                    dimension=cs.dimension,
                    score=cs.score,
                    max_score=cs.max_score,
                    issues=issues,
                    weight=cs.weight,
                ))
            
            quality_report = QualityReport(
                chapter_number=parsed.chapter_number,
                overall_score=parsed.overall_score,
                dimension_scores=dimension_scores,
                consistency_scores=consistency_scores,
                genre=parsed.genre,
                genre_fit_score=parsed.genre_fit_score,
                improvement_suggestions=parsed.improvement_suggestions,
            )
            
            return chapter_content, quality_report
        
        final_content, quality_report = with_retry(_call)
        
        if auto_revise and not self._is_passed(quality_report):
            revise_result = self.revise(
                content=final_content,
                quality_report=quality_report,
                mode="spot-fix",
                target_words=target_words,  # 传递目标字数参数
            )
            final_content = revise_result.content
        
        return final_content, quality_report
    
    def revise(
        self,
        content: str,
        quality_report: QualityReport,
        mode: ReviseMode = "spot-fix",
        target_words: Optional[int] = None,  # 新增：目标字数参数
    ) -> QualityReviseResult:
        """
        根据质量评估报告修订内容（参考 ReviserAgent.revise()）
        
        Args:
            content: 待修订的正文
            quality_report: 质量评估报告
            mode: 修订模式
                - spot-fix: 只修改有问题的句子/段落，其余正文一字不动
                - rewrite-section: 重写包含问题的段落
                - polish: 在不改变情节的前提下提升文笔流畅度
            target_words: 目标字数（可选），用于字数约束检查
        
        Returns:
            QualityReviseResult: 修订结果
        """
        issues = []
        word_count_issue = None
        detected_target_words = None
        
        import re
        for dim_score in quality_report.dimension_scores:
            for issue in dim_score.issues:
                if issue.severity in ["critical", "warning"]:
                    issues.append(issue)
                    # 检测字数偏差问题
                    if ("WORD_COUNT_DEVIATION" in issue.description or 
                        "字数偏差" in issue.description):
                        word_count_issue = issue
                        match = re.search(r"目标\s*(\d+)\s*字", issue.description)
                        if match:
                            detected_target_words = int(match.group(1))
        
        for cons_score in quality_report.consistency_scores:
            for issue in cons_score.issues:
                if issue.severity in ["critical", "warning"]:
                    issues.append(issue)
        
        issues.sort(key=lambda x: 0 if x.severity == "critical" else 1)
        
        # 优先使用传入的 target_words 参数，其次使用从问题中检测到的目标字数
        effective_target_words = target_words if target_words is not None else detected_target_words
        
        # 如果没有问题且没有目标字数约束，直接返回
        if not issues and not effective_target_words:
            return QualityReviseResult(
                content=content,
                change_log=["无需要修复的问题"],
                revised_issues=[],
            )
        
        prompt = self._build_revise_prompt(content, issues, mode, effective_target_words)
        
        def _call() -> QualityReviseResult:
            resp = self.llm.complete([
                LLMMessage("system", self._get_revise_system_prompt(mode)),
                LLMMessage("user", prompt),
            ])
            result = self._parse_revise_result(resp.content)
            return QualityReviseResult(
                content=result["content"],
                change_log=result["change_log"],
                revised_issues=result["revised_issues"],
            )
        
        return with_retry(_call)
    
    def _build_revise_prompt(
        self,
        content: str,
        issues: List[QualityIssue],
        mode: ReviseMode,
        target_words: Optional[int] = None,  # 新增：目标字数参数
    ) -> str:
        # 检测字数偏差问题
        word_count_issue = None
        import re
        for i in issues:
            if ("WORD_COUNT_DEVIATION" in i.description or 
                "字数偏差" in i.description):
                word_count_issue = i
                break
        
        # 构建问题列表（排除字数偏差问题，单独处理）
        issue_lines = []
        for i, issue in enumerate(issues):
            if issue == word_count_issue:
                continue  # 字数偏差问题单独处理
            line = f"{i+1}. [{issue.severity.upper()}] {issue.description}"
            if issue.location:
                line += f"\n   位置：{issue.location}"
            if issue.suggestion:
                line += f"\n   建议：{issue.suggestion}"
            issue_lines.append(line)
        
        mode_instructions = {
            "spot-fix": "只修改有问题的句子/段落，其余正文一字不动",
            "rewrite-section": "重写包含问题的段落（前后各保留一段作为锚点），保持整体情节不变",
            "polish": "在不改变情节的前提下提升文笔流畅度，禁止增删段落",
        }
        
        # 如果有目标字数，添加字数约束提示
        word_count_instruction = ""
        if target_words:
            current_words = len(content)
            is_too_long = current_words > target_words * 1.2
            is_too_short = current_words < target_words * 0.8
            
            if word_count_issue:
                # 如果已有字数偏差问题，按照原有逻辑处理
                if is_too_long:
                    operation_text = "适当精简压缩内容，删除冗余描写，保持核心情节"
                    action_text = "精简"
                else:
                    operation_text = "扩充内容，增加细节描写，丰富情节"
                    action_text = "扩充"
                
                word_count_instruction = f"""
## 特别注意：字数调整要求
- 当前字数：{current_words} 字
- 目标字数：{target_words} 字
- 操作：{operation_text}
- 要求：请直接对全文进行{action_text}，字数接近目标字数，保持剧情走向和核心内容完全不变。
"""
            else:
                # 没有检测到字数偏差问题，但有目标字数作为参考
                word_count_instruction = f"""
## 字数参考约束
- 当前字数：{current_words} 字
- 目标字数：{target_words} 字
- 要求：修订时请尽量保持字数在目标字数的 ±20% 范围内（{int(target_words*0.8)} - {int(target_words*1.2)} 字），避免大幅增减字数。
"""
        
        return f"""\
## 修订任务
模式：{mode}
规则：{mode_instructions[mode]}
硬约束：不得引入新情节，不得修改角色名，不得改变情节走向。

{word_count_instruction}

## 需修订的问题
{chr(10).join(issue_lines) if issue_lines else "（无其他问题，只需调整字数）"}

## 原文
{content}

---
直接输出修订后的完整正文（不要任何前言），然后输出：
{chr(10)}
["改动说明1", "改动说明2", ...]"""
    
    def _get_revise_system_prompt(self, mode: ReviseMode) -> str:
        return f"你是精准的小说修订者，模式：{mode}。直接输出修订后正文，不要任何前言。"
    
    def _parse_revise_result(self, response: str) -> dict:
        parts = response.split("\n\n", 1)
        content = parts[0].strip()
        change_log = []
        revised_issues = []
        
        if len(parts) > 1:
            try:
                change_log = eval(parts[1].strip())
            except Exception:
                change_log = [parts[1].strip()[:200]]
        
        return {
            "content": content,
            "change_log": change_log,
            "revised_issues": revised_issues,
        }
    
    def _is_passed(self, quality_report: QualityReport) -> bool:
        """判断评估是否通过（无 critical 问题）"""
        for dim_score in quality_report.dimension_scores:
            for issue in dim_score.issues:
                if issue.severity == "critical":
                    return False
        for cons_score in quality_report.consistency_scores:
            for issue in cons_score.issues:
                if issue.severity == "critical":
                    return False
        return True
    
    def _get_genre_criteria(self, genre: str) -> GenreCriteria:
        """获取类型特征矩阵"""
        for gc in GENRE_MATRIX:
            if genre in gc.genre or gc.genre in genre:
                return gc
        return GENRE_MATRIX[0]  # 默认返回悬疑/推理
