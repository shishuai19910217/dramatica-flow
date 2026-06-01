"""
叙事引擎
修复：
- generate_chapter_outlines 增加 max_chapters 控制，防止章数爆炸
- StoryOutlineSchema 增加 estimated_total_chapters 字段

整合用户设计：
- Dan Harmon 8步故事圈
- 四大硬性故事线
- 四大关键锚点
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, parse_llm_json_list, with_retry, _fix_df
from ..types.narrative import (
    Character, StoryEvent, DramaticFunction,
)
from ..types.state import CausalLink, AffectedDecision


# ── Dan Harmon 8步故事圈（整合用户设计）─────────────────────────────────────
STORY_CIRCLE_STEPS = {
    1: {"name": "身处安逸", "description": "主角处于日常状态，介绍世界观和角色"},
    2: {"name": "渴望之物", "description": "主角产生欲望或目标，触发冒险动机"},
    3: {"name": "进入未知", "description": "主角离开舒适区，进入陌生环境"},
    4: {"name": "适应过程", "description": "主角学习新规则，遭遇挑战"},
    5: {"name": "得到宝物", "description": "主角获得关键物品/知识/能力"},
    6: {"name": "付出代价", "description": "主角为获得的东西付出代价"},
    7: {"name": "返回考验", "description": "主角带着收获返回，但面临最终考验"},
    8: {"name": "蜕变新生", "description": "主角成长，获得新身份/能力/理解"},
}

STORY_CIRCLE_DF_MAP = {
    1: "setup",        # 身处安逸 → 建立
    2: "inciting",     # 渴望之物 → 激励事件
    3: "turning",      # 进入未知 → 转折点
    4: "transition",   # 适应过程 → 过渡
    5: "midpoint",     # 得到宝物 → 中点
    6: "crisis",       # 付出代价 → 危机
    7: "climax",       # 返回考验 → 高潮
    8: "consequence",  # 蜕变新生 → 后果
}


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class BeatSchema(BaseModel):
    id: str
    description: str
    dramatic_function: DramaticFunction
    target_words: int | None = None
    emotional_target: str | None = None
    detail: str = ""  # 节拍的详细写作指导
    story_circle_step: int | None = None  # Dan Harmon 8步故事圈步骤编号 (1-8)


class SequenceSchema(BaseModel):
    id: str
    number: int
    act: int
    summary: str
    narrative_goal: str
    dramatic_function: DramaticFunction
    key_events: list[str] = Field(default_factory=list)
    estimated_scenes: int = 3
    end_hook: str = ""
    # Dan Harmon 8步故事圈配置
    story_circle_start_step: int = 1  # 该序列从8步故事圈的第几步开始
    story_circle_end_step: int = 8    # 该序列到8步故事圈的第几步结束
    # 该序列服务的故事线
    storylines: list[str] = Field(default_factory=list)


class ChapterOutlineSchema(BaseModel):
    chapter_number: int
    title: str
    summary: str
    sequence_id: str
    beats: list[BeatSchema] = Field(default_factory=list)
    emotional_arc: dict[str, str] = Field(default_factory=dict)
    mandatory_tasks: list[str] = Field(default_factory=list)
    target_words: int = 4000
    writing_notes: str = ""  # 整章写作基调指导
    pov: str = ""  # 视角角色说明


class SceneCardSchema(BaseModel):
    id: str
    chapter_number: int
    heading: str
    location: str
    characters: list[str] = Field(default_factory=list)
    dramatic_function: DramaticFunction
    scene_goal: str
    beats: list[BeatSchema] = Field(default_factory=list)
    conflict_core: str
    end_state: str = "worse"


class AffectedDecisionSchema(BaseModel):
    character_id: str
    decision: str


class CausalLinkSchema(BaseModel):
    id: str
    chapter: int
    cause: str
    event: str
    consequence: str
    affected_decisions: list[AffectedDecisionSchema] = Field(default_factory=list)
    triggered_events: list[str] = Field(default_factory=list)


# ── 四大硬性故事线 Schema（整合用户设计）───────────────────────────────────
class CoreStorylinesSchema(BaseModel):
    protagonist_growth: str = ""      # 主角内心成长线
    antagonist_conflict: str = ""     # 反派/影响角色博弈线
    relationship_dynamics: str = ""   # 核心人物关系拉扯线
    external_events: str = ""         # 外部客观事件线（复仇/逆袭/权谋）


# ── 四大关键锚点 Schema（整合用户设计）─────────────────────────────────────
class KeyAnchorsSchema(BaseModel):
    opening_hook: str = ""    # 开篇强钩子（第1章）
    midpoint_twist: str = ""  # 中点反转（约50%处）
    soul_night: str = ""      # 灵魂黑夜（约75%处）
    final_climax: str = ""    # 终局高潮（结尾）


class StoryOutlineSchema(BaseModel):
    id: str
    title: str
    logline: str
    genre: str
    sequences: list[SequenceSchema]
    emotional_roadmap: list[dict[str, str]] = Field(default_factory=list)
    # 四大硬性故事线（整合用户设计）
    core_storylines: CoreStorylinesSchema = Field(default_factory=CoreStorylinesSchema)
    # 四大关键锚点（整合用户设计）
    key_anchors: KeyAnchorsSchema = Field(default_factory=KeyAnchorsSchema)


# ── NarrativeEngine ───────────────────────────────────────────────────────────

class NarrativeEngine:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    # ── 1. 生成故事大纲 ──────────────────────────────────────────────────────────

    def generate_outline(
        self,
        seed_event: StoryEvent,
        protagonist: Character,
        world_context: str,
        target_chapters: int,
        genre: str,
    ) -> StoryOutlineSchema:
        act1 = round(target_chapters * 0.25)
        act2 = round(target_chapters * 0.50)
        act3 = target_chapters - act1 - act2

        # 序列数量控制：每个序列约覆盖 8-15 章
        seq_count_hint = max(6, target_chapters // 10)

        # 计算关键锚点位置
        midpoint_chapter = round(target_chapters * 0.5)
        soul_night_chapter = round(target_chapters * 0.75)
        climax_chapter = target_chapters

        prompt = f"""\
你是精通 Dramatica 叙事理论和三幕式结构的故事架构师。

## 任务
为一部 {target_chapters} 章的{genre}小说生成完整故事大纲。
序列数量建议：{seq_count_hint} 个左右（不要过多也不要过少）。

## 种子事件（第一幕激励事件）
名称：{seed_event.name}
描述：{seed_event.description}
效果：{'、'.join(seed_event.effects)}

## 主角
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
角色弧线：{protagonist.arc}（positive=成长变好 negative=堕落 flat=不变 corrupt=腐化）
性格锁定：{'、'.join(protagonist.behavior_lock)}

## 世界背景
{world_context[:2000]}

## 三幕章节分配
- 第一幕（第1-{act1}章）：建立世界+角色+冲突，激励事件发生
- 第二幕（第{act1+1}-{act1+act2}章）：持续升级对抗，中点处有重大转折，危机最低点
- 第三幕（第{act1+act2+1}-{target_chapters}章）：高潮对决，解决冲突，角色完成弧线

## 四大硬性故事线（贯穿全书，不可偏离）
1. 主角内心成长线：主角如何从初始状态成长到最终状态
2. 反派/影响角色博弈线：主角与反派/影响角色的较量
3. 核心人物关系拉扯线：主角与关键人物的关系变化
4. 外部客观事件线：复仇/逆袭/权谋等主线事件

## 四大关键锚点必须预埋
1. **开篇强钩子**（第1章）：必须在第一章就抓住读者注意力，制造强烈悬念
2. **中点反转**（约第{midpoint_chapter}章）：主角获得重大信息/能力，或遭遇重大转折
3. **灵魂黑夜**（约第{soul_night_chapter}章）：主角陷入最低谷，失去一切，面临终极考验
4. **终局高潮**（第{climax_chapter}章）：终极对决，解决核心冲突

## 核心要求
1. 因果链：每个序列的发生必须是前一序列后果的直接结果
2. 钩子：每个序列的 end_hook 必须制造具体的悬念（不能是模糊的"xxx将何去何从"）
3. Logline 格式：「[主角] 必须在 [时限/代价] 内 [目标]，但 [障碍]」
4. 序列 estimated_scenes 是这个序列预计展开的章节数，所有序列的 estimated_scenes 之和必须等于 {target_chapters}
5. 每个序列必须明确服务于四大硬性故事线中的至少一条
6. 确保四大关键锚点在对应章节位置落地

## JSON 输出格式
{{
  "id": "outline_001",
  "title": "书名",
  "logline": "...",
  "genre": "{genre}",
  "core_storylines": {{
    "protagonist_growth": "主角内心成长线描述",
    "antagonist_conflict": "反派/影响角色博弈线描述",
    "relationship_dynamics": "核心人物关系拉扯线描述",
    "external_events": "外部客观事件线描述"
  }},
  "key_anchors": {{
    "opening_hook": "开篇强钩子描述",
    "midpoint_twist": "中点反转描述",
    "soul_night": "灵魂黑夜描述",
    "final_climax": "终局高潮描述"
  }},
  "sequences": [
    {{
      "id": "seq_01",
      "number": 1,
      "act": 1,
      "summary": "序列内容摘要（2句话）",
      "narrative_goal": "这个序列要完成的叙事任务",
      "dramatic_function": "inciting",
      "key_events": ["关键事件1", "关键事件2"],
      "estimated_scenes": 5,
      "end_hook": "具体的悬念钩子（一句话，要有画面感）",
      "storylines": ["主角内心成长线", "外部客观事件线"],
      "story_circle_start_step": 1,
      "story_circle_end_step": 8
    }}
  ],
  "emotional_roadmap": [
    {{"chapter": "1", "target_emotion": "屈辱", "anchor": "opening_hook"}},
    {{"chapter": "{midpoint_chapter}", "target_emotion": "震惊", "anchor": "midpoint_twist"}},
    {{"chapter": "{soul_night_chapter}", "target_emotion": "绝望", "anchor": "soul_night"}},
    {{"chapter": "{climax_chapter}", "target_emotion": "激昂", "anchor": "final_climax"}}
  ]
}}

只输出 JSON，不要任何说明。"""

        def _call() -> StoryOutlineSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是精通戏剧理论的故事架构师，只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])

            _VALID_DF = {"setup", "inciting", "turning", "midpoint", "crisis", "climax", "reveal", "decision", "consequence", "transition"}

            def _patch_outline(data: dict) -> dict:
                """修复大纲中常见的 AI 输出问题"""
                for seq in data.get("sequences", []):
                    if not isinstance(seq, dict):
                        continue
                    # 补 narrative_goal
                    if not seq.get("narrative_goal"):
                        seq["narrative_goal"] = seq.get("summary", "推进剧情")
                    # 修正 dramatic_function
                    if seq.get("dramatic_function") and seq["dramatic_function"] not in _VALID_DF:
                        seq["dramatic_function"] = _fix_df(seq["dramatic_function"])
                    # estimated_scenes 至少为 1
                    if seq.get("estimated_scenes", 0) < 1:
                        seq["estimated_scenes"] = 1
                return data

            outline = parse_llm_json(resp.content, StoryOutlineSchema, "generate_outline", patch_fn=_patch_outline)

            # 校验并修正章数
            total = sum(s.estimated_scenes for s in outline.sequences)
            if total != target_chapters and total > 0:
                # 等比缩放到目标章数
                ratio = target_chapters / total
                remaining = target_chapters
                for i, seq in enumerate(outline.sequences):
                    if i == len(outline.sequences) - 1:
                        seq.estimated_scenes = remaining
                    else:
                        scaled = max(1, round(seq.estimated_scenes * ratio))
                        seq.estimated_scenes = scaled
                        remaining -= scaled

            return outline

        return with_retry(_call)

    # ── 2. 章纲生成（序列 → 章，有章数上限控制） ──────────────────────────────

    def generate_chapter_outlines(
        self,
        sequence: SequenceSchema,
        protagonist: Character,
        world_context: str,
        chapter_start: int,
        words_per_chapter: int,
    ) -> list[ChapterOutlineSchema]:
        """
        将一个序列展开为 estimated_scenes 个章纲。
        严格按照 estimated_scenes 控制生成章数。
        如果章数过多则分批调用 LLM，避免输出超出 max_tokens 被截断。
        """
        n_chapters = sequence.estimated_scenes
        # 每批最多生成 5 章，防止 JSON 太长被截断
        BATCH_SIZE = 5
        all_outlines = []

        # AI 常用的非法 dramatic_function 别名映射到合法值
        _DF_ALIASES = {
            "twist": "turning", "turn": "turning", "turning_point": "turning", "progressive complication": "turning",
            "complication": "turning", "转折": "turning",
            "hook": "inciting", "trigger": "inciting", "钩子": "inciting",
            "conflict": "crisis", "crash": "crisis", "dark night": "crisis", "all is lost": "crisis", "冲突": "crisis",
            "battle": "climax", "peak": "climax", "showdown": "climax", "confrontation": "climax", "战斗": "climax",
            "ending": "consequence", "result": "consequence", "resolution": "consequence", "denouement": "consequence", "后果": "consequence",
            "info": "reveal", "discover": "reveal", "revelation": "reveal", "揭示": "reveal",
            "choice": "decision", "select": "decision", "commitment": "decision", "选择": "decision",
            "build": "setup", "intro": "setup", "introduct": "setup", "exposition": "setup", "建立": "setup",
            "bridge": "transition", "pause": "transition", "interlude": "transition", "过渡": "transition",
            "middle": "midpoint", "mid": "midpoint", "中点": "midpoint",
        }
        _VALID_DF = {"setup", "inciting", "turning", "midpoint", "crisis", "climax", "reveal", "decision", "consequence", "transition"}

        def _patch(item: dict) -> dict:
            if "chapter" in item and "chapter_number" not in item:
                item["chapter_number"] = item.pop("chapter")
            if "summary" not in item:
                item["summary"] = item.get("title", "章节摘要")
            if "title" not in item:
                item["title"] = f"第{item.get('chapter_number', '?')}章"
            # 确保 sequence_id 存在
            if "sequence_id" not in item or not item["sequence_id"]:
                item["sequence_id"] = sequence.id
            # 修正序列级的 dramatic_function
            if item.get("dramatic_function") and item["dramatic_function"] not in _VALID_DF:
                item["dramatic_function"] = _DF_ALIASES.get(item["dramatic_function"].lower().strip(), "transition")
            for bi, beat in enumerate(item.get("beats", [])):
                if not beat.get("id"):
                    beat["id"] = f"beat_{item.get('chapter_number', bi)}_{bi+1}"
                # 修正 beat 的 dramatic_function
                if beat.get("dramatic_function") and beat["dramatic_function"] not in _VALID_DF:
                    beat["dramatic_function"] = _DF_ALIASES.get(str(beat["dramatic_function"]).lower().strip(), "transition")
                # 确保 story_circle_step 在 1-8 范围内
                if beat.get("story_circle_step"):
                    try:
                        step = int(beat["story_circle_step"])
                        if step < 1 or step > 8:
                            beat["story_circle_step"] = None
                    except ValueError:
                        beat["story_circle_step"] = None
            return item

        for batch_start in range(0, n_chapters, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, n_chapters)
            batch_count = batch_end - batch_start
            actual_ch_start = chapter_start + batch_start

            # Dan Harmon 8步故事圈指导
            story_circle_guide = ""
            if n_chapters >= 8:
                story_circle_guide = f"""\
## Dan Harmon 8步故事圈节奏分配
本序列有 {n_chapters} 章，请按照以下节奏分配：
1. 身处安逸 → 主角处于日常状态，介绍世界观和角色
2. 渴望之物 → 主角产生欲望或目标，触发冒险动机
3. 进入未知 → 主角离开舒适区，进入陌生环境
4. 适应过程 → 主角学习新规则，遭遇挑战
5. 得到宝物 → 主角获得关键物品/知识/能力
6. 付出代价 → 主角为获得的东西付出代价
7. 返回考验 → 主角带着收获返回，但面临最终考验
8. 蜕变新生 → 主角成长，获得新身份/能力/理解

请将这些步骤均匀分配到 {n_chapters} 章中，确保每章都有小冲突、小欲望、小挫折、小反转。
"""
            else:
                story_circle_guide = f"""\
## 章节节奏要求
虽然本序列只有 {n_chapters} 章，但请确保：
- 每章都有明确的小冲突和小反转
- 章节末设置悬念钩子
- 情感起伏：平静 → 紧张 → 释放 → 新悬念
"""

            prompt = f"""\
将以下故事序列展开为 **恰好 {batch_count} 个**章纲。

## 序列信息
摘要：{sequence.summary}
叙事目标：{sequence.narrative_goal}
戏剧功能：{sequence.dramatic_function.value}
关键事件：{'、'.join(sequence.key_events)}
结尾钩子（最后一章必须实现）：{sequence.end_hook}

## 主角
{protagonist.name}：
- 外部目标：{protagonist.need.external}
- 内在渴望：{protagonist.need.internal}
- 性格锁定：{'、'.join(protagonist.behavior_lock)}

## 当前世界状态
{world_context[:1500]}

{story_circle_guide}
## 严格要求
- 每章必须包含 summary（章节摘要，50字以内）
- 每章必须包含 beats 数组，每个 beat 必须包含 id、description、dramatic_function、story_circle_step 字段
- 章节编号从第 {actual_ch_start} 章开始
- 必须生成 **恰好 {batch_count} 个**章纲，不多不少
- 每章 {words_per_chapter} 字
- beats 每章 2-3 个即可，description 控制在20字内
- beats 的 dramatic_function 必须是以下之一：
  setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- story_circle_step 为 1-8 的整数，对应 Dan Harmon 8步故事圈
- mandatory_tasks 列出本章不完成就审计不通过的叙事任务（1-2个）
- emotional_arc 格式：{{"start": "开始情绪", "end": "结束情绪"}}
- sequence_id 统一填 "{sequence.id}"

只输出 JSON 数组（{batch_count} 个元素），不要任何说明。"""

            def _call() -> list[ChapterOutlineSchema]:
                resp = self.llm.complete([
                    LLMMessage("system", "你是精通节拍表的故事编辑，只输出合法 JSON 数组，章数必须精确。"),
                    LLMMessage("user", prompt),
                ])
                outlines = parse_llm_json_list(
                    resp.content, ChapterOutlineSchema, "generate_chapter_outlines",
                    patch_fn=_patch,
                )
                for i, co in enumerate(outlines):
                    co.chapter_number = actual_ch_start + i
                    if co.target_words == 0:
                        co.target_words = words_per_chapter
                if len(outlines) > batch_count:
                    outlines = outlines[:batch_count]
                elif len(outlines) < batch_count:
                    for j in range(len(outlines), batch_count):
                        outlines.append(ChapterOutlineSchema(
                            chapter_number=actual_ch_start + j,
                            title=f"第{actual_ch_start + j}章",
                            summary=f"{sequence.summary}",
                            sequence_id=sequence.id,
                            beats=[BeatSchema(
                                id=f"beat_{actual_ch_start + j}_1",
                                description="情节推进",
                                dramatic_function=DramaticFunction.TRANSITION,
                            )],
                            emotional_arc={"start": "平静", "end": "紧张"},
                            mandatory_tasks=["推进情节"],
                            target_words=words_per_chapter,
                        ))
                return outlines

            batch_result = with_retry(_call)
            all_outlines.extend(batch_result)
        return all_outlines

    # ── 3. 因果链提取 ──────────────────────────────────────────────────────────

    def extract_causal_links(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[Character],
    ) -> list[CausalLinkSchema]:
        char_list = "、".join(f"{c.id}（{c.name}）" for c in characters)
        content_excerpt = chapter_content[:4000]
        if len(chapter_content) > 4000:
            content_excerpt += "\n...(截断)"

        prompt = f"""\
分析第 {chapter_number} 章，提取关键因果关系（2-5 条，不要过多）。

## 章节内容
{content_excerpt}

## 角色列表
{char_list}

## 要求
每条因果链必须回答：
- 因为什么（cause）→ 发生了什么（event）→ 导致什么后果（consequence）
- 哪个角色因此做了什么决定（affected_decisions）
- 下游会触发什么事件（triggered_events，自然语言）

ID 格式：causal_ch{chapter_number}_001

只输出 JSON 数组（CausalLinkSchema[]），不要说明。"""

        def _call() -> list[CausalLinkSchema]:
            resp = self.llm.complete([
                LLMMessage("system", "你是叙事分析师，分析因果结构，只输出合法 JSON 数组。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json_list(
                resp.content, CausalLinkSchema, "extract_causal_links"
            )

        try:
            return with_retry(_call)
        except Exception:
            return []  # 因果链提取失败不阻塞主流程
