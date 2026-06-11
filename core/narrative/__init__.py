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

import json
import re

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

        # 提取主角反差设定（如果有）
        contrast_info = ""
        if hasattr(protagonist, 'contrast') and protagonist.contrast:
            contrast_info = f"""\
- 显性标签：{protagonist.contrast.surface_label}
- 隐藏反差：{protagonist.contrast.hidden_truth}"""
        
        prompt = f"""\
你是精通 Dramatica 叙事理论和三幕式结构的故事架构师，深谙番茄小说平台爆款逻辑。

## 任务
为一部 {target_chapters} 章的{genre}小说生成完整故事大纲。
序列数量建议：{seq_count_hint} 个左右（不要过多也不要过少）。

## 种子事件（第一幕激励事件）
名称：{seed_event.name}
描述：{seed_event.description}
效果：{'、'.join(seed_event.effects)}

## 主角（打造反差成长人设）
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
角色弧线：{protagonist.arc}（positive=成长变好 negative=堕落 flat=不变 corrupt=腐化）
性格锁定：{'、'.join(protagonist.behavior_lock)}
{contrast_info}

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

## 番茄爆款逻辑要求（重中之重）
1. **反常识世界观**：设计一条反常识的核心规则，打破读者惯性认知（例如："丧尸病毒爆发后，人类死者会重生为自己生前最恐惧的怪物"）
2. **主角反差设定**：主角必须有显性标签+隐藏反差（例如："唯利是图的外卖员，实则身负时间回溯异能"）
3. **执念型性格缺陷**：给主角设定一个执念型缺陷，成为人物成长的核心根基（例如："拒绝信任任何人，坚信心软必死"）
4. **两难抉择试炼**：在关键节点设计两难抉择，倒逼人物成长，加深读者代入感
5. **情绪爆点密度**：每3章至少设置1次强情绪爆点（愤怒/委屈/狂喜/揪心）
6. **伏笔限时回收**：所有长线伏笔必须在30章内首次呼应，60章内彻底闭环

## 核心要求
1. 因果链：每个序列的发生必须是前一序列后果的直接结果
2. 钩子：每个序列的 end_hook 必须制造具体的悬念（不能是模糊的"xxx 将何去何从"）
3. Logline 格式：「[主角] 必须在 [时限/代价] 内 [目标]，但 [障碍]」
4. 序列 estimated_scenes 是这个序列预计展开的章节数，所有序列的 estimated_scenes 之和必须等于 {target_chapters}
5. 每个序列必须明确服务于四大硬性故事线中的至少一条
6. 确保四大关键锚点在对应章节位置落地
7. 世界观描述必须包含至少一条反常识规则，突出差异化
8. **key_events 数量要求**：每个序列的 `key_events` 数组必须包含至少 `estimated_scenes` 个**不同的**关键事件（例如序列有 10 章就需要 10 个不同的事件），不能有重复

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
      "summary": "序列内容摘要（2 句话）",
      "narrative_goal": "这个序列要完成的叙事任务",
      "dramatic_function": "inciting",
      "key_events": ["关键事件1", "关键事件2", "关键事件3", "关键事件4", "关键事件5"],
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
        progress_callback=None,
        previous_chapter_titles: list[str] | None = None,
        genre: str = "都市",  # 新增参数：书籍题材，用于选择对应事件类型词汇库
        use_predefined_events: bool = True,  # 新增参数：是否使用预定义事件类型词汇库
    ) -> list[ChapterOutlineSchema]:
        """
        将一个序列展开为 estimated_scenes 个章纲。
        严格按照 estimated_scenes 控制生成章数。
        如果章数过多则分批调用 LLM，避免输出超出 max_tokens 被截断。
        previous_chapter_titles: 前面序列已生成的章节标题列表，用于防止跨序列重复。
        genre: 书籍题材，用于选择对应事件类型词汇库。
        use_predefined_events: 是否使用预定义事件类型词汇库。
        """
        n_chapters = sequence.estimated_scenes
        # 每批最多生成 5 章，防止 JSON 太长被截断
        BATCH_SIZE = 5
        all_outlines = []
        total_batches = (n_chapters + BATCH_SIZE - 1) // BATCH_SIZE

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
                item["title"] = f"第{item.get('chapter_number', '?')}章-情节推进"
            # 确保 sequence_id 存在
            if "sequence_id" not in item or not item["sequence_id"]:
                item["sequence_id"] = sequence.id
            # 设置目标字数（使用传入的配置值）
            if "target_words" not in item or not item["target_words"]:
                item["target_words"] = words_per_chapter
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

        for batch_idx, batch_start in enumerate(range(0, n_chapters, BATCH_SIZE)):
            batch_end = min(batch_start + BATCH_SIZE, n_chapters)
            batch_count = batch_end - batch_start
            actual_ch_start = chapter_start + batch_start
            
            # 进度回调：通知当前批次开始
            if progress_callback:
                progress_callback({
                    "stage": "generating",
                    "sequence_id": sequence.id,
                    "sequence_name": f"序列{sequence.id}",
                    "batch_index": batch_idx,
                    "total_batches": total_batches,
                    "chapters_completed": batch_start,
                    "total_chapters": n_chapters,
                    "message": f"正在生成第 {actual_ch_start}-{actual_ch_start + batch_count - 1} 章大纲..."
                })

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

            # 计算当前批次在序列中的进度位置
            progress_ratio_start = batch_start / n_chapters
            progress_ratio_end = batch_end / n_chapters
            
            # 计算当前批次对应的故事圈步骤范围（处理边界情况）
            try:
                story_circle_start = max(1, round(1 + (sequence.story_circle_start_step - 1) + (sequence.story_circle_end_step - sequence.story_circle_start_step) * progress_ratio_start))
                story_circle_end = min(8, round((sequence.story_circle_start_step - 1) + (sequence.story_circle_end_step - sequence.story_circle_start_step + 1) * progress_ratio_end))
                # 确保结束步骤不小于开始步骤
                if story_circle_end < story_circle_start:
                    story_circle_end = story_circle_start
            except (AttributeError, TypeError):
                # 如果序列没有设置故事圈步骤，使用默认值
                story_circle_start = max(1, round(1 + 7 * progress_ratio_start))
                story_circle_end = min(8, round(1 + 7 * progress_ratio_end))

            # 构建跨序列上下文：已完成的章节标题列表
            previous_context = ""
            if previous_chapter_titles:
                prev_list = "\n".join(f"  - {t}" for t in previous_chapter_titles)
                previous_context = f"""\
## 跨序列上下文（已完成的章节）
以下章节已经在前面的序列中完成，你即将生成的章节**不能与它们重复**：
{prev_list}

"""

            # 为当前批次每章分配一个差异化的事件种子
            # 优化策略：优先使用 key_events，不足时使用预定义词汇库 + AI增强
            derived_events = []
            
            # 1. 优先使用 key_events（故事大纲阶段生成，质量最高）
            for ke in sequence.key_events:
                if ke and ke not in derived_events:
                    derived_events.append(ke)
            
            # 2. 如果 key_events 数量不足，且配置允许，则补充预定义词汇库事件
            if use_predefined_events and len(derived_events) < n_chapters:
                # 获取题材相关的预定义事件类型词汇库
                # 优化：增加更多元化的事件类型，避免模式化重复（如"危机"、"秘闻"、"奇遇"过多）
                genre_events = {
                    # 都市题材 - 动作导向，避免模式化
                    "都市": [
                        "职场博弈", "商业谈判", "创业逆袭", "豪门恩怨", "商业间谍",
                        "科技创业", "金融对决", "职场晋升", "都市传说", "爱情纠葛",
                        "卧底行动", "行业黑幕", "资本运作", "明星绯闻", "时尚潮流",
                        "美食探店", "房产投资", "网络红人", "猎头挖角", "创业融资",
                        "产品发布", "市场竞争", "品牌危机", "公关危机", "数据泄露",
                        "职场站队", "办公室恋情", "升职加薪", "辞职创业", "行业转型"
                    ],
                    # 玄幻题材 - 去除"奇遇"等模式化词汇，增加动作导向
                    "玄幻": [
                        "功法突破", "秘境探险", "宗门斗争", "神兽契约", "丹道炼丹",
                        "器道炼器", "符道制符", "阵道布阵", "血脉觉醒", "武魂融合",
                        "渡劫飞升", "仙魔大战", "秘境寻宝", "传承获得", "正邪对立",
                        "宗门大比", "丹会论道", "拍卖会风波", "古遗迹探险", "妖族入侵",
                        "魔族来袭", "天道感悟", "法则领悟", "道侣双修", "轮回转世",
                        "因果纠缠", "时空穿梭", "位面战争", "秘境崩塌", "神器认主"
                    ],
                    # 科幻题材
                    "科幻": [
                        "星际探索", "人工智能", "时间旅行", "外星接触", "机械改造",
                        "量子跃迁", "维度穿越", "赛博空间", "基因编辑", "纳米科技",
                        "宇宙战争", "文明碰撞", "虫洞探险", "意识上传", "虚拟世界",
                        "太空殖民", "反物质能源", "黑洞奥秘", "平行宇宙", "时间悖论",
                        "星际贸易", "星球开发", "人工智能反叛", "机械飞升", "意识网络",
                        "量子计算", "暗物质探索", "宇宙遗迹", "星际联盟", "银河帝国"
                    ],
                    # 科幻末世题材 - 去除"危机"等模式化词汇
                    "科幻末世": [
                        "病毒爆发", "末日求生", "废土重建", "变异生物", "资源争夺",
                        "基地建设", "幸存者联盟", "科技残留", "外星入侵", "时间重置",
                        "地下避难", "辐射变异", "机甲战斗", "基因改造", "生态崩溃",
                        "星际移民", "旧日支配者", "文明火种", "废墟探索", "能源枯竭",
                        "水源争夺", "粮食短缺", "疾病蔓延", "暴力冲突", "希望曙光",
                        "新文明崛起", "旧世界遗物", "科技复兴", "幸存者营地", "危险区域"
                    ],
                    # 历史题材
                    "历史": [
                        "王朝更迭", "宫廷权谋", "战场厮杀", "丝绸之路", "文化交融",
                        "帝王传奇", "名将征战", "文人墨客", "商业传奇", "民族融合",
                        "变法图强", "农民起义", "外交谋略", "宗教兴衰", "科技发明",
                        "艺术巅峰", "航海探险", "贸易繁荣", "城市崛起", "家族兴衰",
                        "科举之路", "官场沉浮", "边疆征战", "和亲联姻", "文化传承",
                        "诗词歌赋", "书画艺术", "建筑奇迹", "医学发展", "农业革新"
                    ],
                    # 悬疑题材 - 去除"秘闻"等模式化词汇
                    "悬疑": [
                        "连环凶案", "密室杀人", "身份谜团", "记忆碎片", "真假难辨",
                        "卧底迷局", "密码破译", "离奇失踪", "幽灵传说", "心理操控",
                        "连环陷阱", "真假证词", "隐匿身份", "暗中观察", "致命游戏",
                        "时间胶囊", "记忆篡改", "梦境入侵", "虚拟现实", "意识操控",
                        "神秘组织", "阴谋诡计", "线索追踪", "真相大白", "罪案调查",
                        "证人保护", "证据分析", "犯罪心理", "侦探推理", "悬疑反转"
                    ],
                    # 悬疑脑洞题材
                    "悬疑脑洞": [
                        "无限循环", "记忆植入", "平行世界", "时间悖论", "梦境嵌套",
                        "意识上传", "虚拟实境", "记忆篡改", "量子纠缠", "因果律武器",
                        "蝴蝶效应", "时空折叠", "维度穿越", "意识入侵", "数字幽灵",
                        "神经接口", "脑机交互", "记忆碎片", "意识投影", "时间裂隙",
                        "多元宇宙", "时空悖论", "记忆重构", "虚拟记忆", "意识复制",
                        "数字意识", "网络幽灵", "数据生命", "程序觉醒", "模拟世界"
                    ],
                    # 仙侠题材 - 去除"奇遇"等模式化词汇
                    "仙侠": [
                        "修仙问道", "御剑飞行", "仙府探秘", "丹药炼制", "法宝祭炼",
                        "灵根觉醒", "功法传承", "机缘巧合", "渡劫飞升", "仙界纷争",
                        "神魔大战", "秘境探险", "仙侣情缘", "宗门竞争", "上古遗迹",
                        "天道感悟", "法则领悟", "仙魔一念", "轮回转世", "因果纠缠",
                        "飞升仙界", "神界大战", "仙宫探秘", "神兽坐骑", "仙草灵药",
                        "仙法对决", "仙人下凡", "洞天福地", "仙门传承", "修仙大道"
                    ],
                    # 言情题材
                    "言情": [
                        "一见钟情", "日久生情", "误会重重", "破镜重圆", "豪门虐恋",
                        "青梅竹马", "欢喜冤家", "霸道总裁", "温柔学长", "校园初恋",
                        "职场恋情", "异地相思", "日久见人心", "深情守护", "爱而不得",
                        "命中注定", "跨越阶层", "家族恩怨", "追妻火葬场", "双向奔赴",
                        "暗恋成真", "甜蜜告白", "浪漫约会", "深情告白", "爱情长跑",
                        "婚姻生活", "爱情考验", "分分合合", "真爱永恒", "幸福美满"
                    ],
                    # 游戏题材
                    "游戏": [
                        "虚拟游戏", "游戏重生", "NPC觉醒", "游戏入侵现实", "数据成神",
                        "职业选择", "副本挑战", "公会争霸", "装备锻造", "技能升级",
                        "隐藏任务", "BOSS击杀", "游戏货币", "虚拟爱情", "游戏直播",
                        "电竞比赛", "游戏开发", "游戏测试", "游戏BUG", "游戏管理员",
                        "玩家互动", "游戏策略", "团队协作", "PVP对战", "PVE挑战",
                        "游戏剧情", "角色养成", "装备收集", "成就解锁", "排行榜竞争"
                    ],
                    # 无限流题材
                    "无限流": [
                        "轮回空间", "副本挑战", "主神空间", "无限任务", "强化升级",
                        "团队协作", "智斗布局", "恐怖副本", "科幻世界", "玄幻位面",
                        "武侠世界", "末日求生", "动漫穿越", "电影世界", "神话传说",
                        "因果律武器", "时间能力", "空间能力", "基因锁", "最终进化",
                        "团战协作", "个人突破", "隐藏剧情", "支线任务", "主线推进",
                        "世界探索", "能力融合", "团队组建", "资源争夺", "最终决战"
                    ],
                    # 默认通用事件类型 - 彻底去除模式化词汇
                    "其他": [
                        "冲突爆发", "矛盾激化", "秘密揭露", "盟友背叛", "关键抉择",
                        "绝境逆袭", "真相大白", "计划失败", "意外发现", "命运转折",
                        "阴谋败露", "危机升级", "盟友加入", "技能突破", "真相反转",
                        "陷阱布置", "危机解除", "秘密潜入", "身份暴露", "决战前夕",
                        "计划实施", "行动失败", "意外收获", "形势逆转", "转机出现",
                        "谜团解开", "真相浮现", "阴谋粉碎", "困境突围", "胜利在望"
                    ]
                }
                
                # 获取当前题材的事件类型
                base_event_types = genre_events.get(genre, genre_events["其他"])
                
                # 补充预定义事件类型
                for event_type in base_event_types:
                    if len(derived_events) >= n_chapters:
                        break
                    if event_type not in derived_events:
                        derived_events.append(event_type)
            
            # 3. 如果仍然不足，AI增强生成（仅在必要时调用）
            if len(derived_events) < n_chapters:
                try:
                    needed = n_chapters - len(derived_events)
                    prompt = f"""
                    请根据以下故事序列信息，生成{needed}个独特的事件类型：
                    
                    序列摘要：{sequence.summary}
                    叙事目标：{sequence.narrative_goal}
                    戏剧功能：{sequence.dramatic_function.value}
                    已有关键事件：{','.join(sequence.key_events[:5])}
                    
                    要求：
                    1. 每个事件类型4-8个字，包含动作和状态
                    2. 符合{genre}题材的世界观
                    3. 避免与已有事件重复：{','.join(derived_events[-5:])}
                    4. 覆盖冲突、成长、反转、揭秘等故事要素
                    
                    输出格式：直接输出事件类型列表，每行一个，不加编号
                    """
                    resp = self.llm.complete([
                        LLMMessage("system", "你是故事事件生成专家，只输出事件类型列表。"),
                        LLMMessage("user", prompt),
                    ])
                    # 解析输出
                    for line in resp.content.strip().split('\n'):
                        line = line.strip()
                        if line and len(line) >= 4 and len(line) <= 12 and line not in derived_events:
                            derived_events.append(line)
                            if len(derived_events) >= n_chapters:
                                break
                except Exception as e:
                    # AI生成失败时，使用备用策略
                    pass
            
            # 4. 最终确保事件数量足够（兜底策略）
            while len(derived_events) < n_chapters:
                # 从叙事文本中提取关键词 + 序号
                full_narrative = (sequence.narrative_goal + sequence.summary).replace(" ", "")
                text_pos = (len(derived_events) * 5) % max(len(full_narrative) - 3, 1)
                keyword = full_narrative[text_pos:text_pos+3] if len(full_narrative) > 3 else ""
                new_event = f"{keyword}事件{len(derived_events) + 1}"
                if new_event not in derived_events:
                    derived_events.append(new_event)
            
            # 5. 为当前批次分配事件种子（使用循环偏移确保每批不同）
            slice_start = (batch_idx * 3) % max(len(derived_events), 1)
            batch_events = []
            for i in range(batch_count):
                idx = (slice_start + i) % len(derived_events)
                batch_events.append(derived_events[idx])
            
            # 生成事件分配字符串，强调唯一性
            events_assignment = "\n".join(
                f"  第{actual_ch_start + i}章 → 核心事件：{batch_events[i]}（必须与其他章节完全不同）"
                for i in range(batch_count)
            )

            prompt = f"""\
将以下故事序列展开为 **恰好 {batch_count} 个**章纲，符合番茄小说平台爆款标准。

## 批次位置信息（非常重要）
- 当前批次：第 {batch_idx + 1} / {total_batches} 批
- 当前章节范围：第 {actual_ch_start}-{actual_ch_start + batch_count - 1} 章（全序列共 {n_chapters} 章）
- 序列进度：{int(progress_ratio_start * 100)}% - {int(progress_ratio_end * 100)}%
- 本批次对应故事圈步骤：{story_circle_start}-{story_circle_end}

## 序列信息
**序列编号**：{sequence.number}（这是全书的第 {sequence.number} 个序列）
摘要：{sequence.summary}
叙事目标：{sequence.narrative_goal}
戏剧功能：{sequence.dramatic_function.value}
关键事件：{'、'.join(sequence.key_events)}
结尾钩子（最后一章必须实现）：{sequence.end_hook}
本序列服务的故事线：{', '.join(sequence.storylines) if sequence.storylines else '主线剧情'}

{previous_context}## 主角
{protagonist.name}：
- 外部目标：{protagonist.need.external}
- 内在渴望：{protagonist.need.internal}
- 性格锁定：{'、'.join(protagonist.behavior_lock)}

## 当前世界状态
{world_context[:1500]}

{story_circle_guide}

## 每章差异化事件分配（★★★★★ 核心要求，必须严格遵守）
本批次 {batch_count} 章，每章必须有一个**唯一的核心事件**，每章标题必须反映各自不同的核心事件，**绝对不能重复**。

### ⚠️ 严重警告：标题唯一性强制要求
**如果本批次中有任何两个章节标题重复或高度相似，将被判定为生成失败！**
- 禁止标题包含相同的核心名词（如"事务局对策"出现在多个标题中）
- 禁止标题只是数字编号不同（如"事务局对策1"、"事务局对策2"）
- 禁止使用相同的动词（如"对策"、"计划"、"行动"等）出现在多个标题中
- 禁止使用"危机"、"秘闻"、"奇遇"等模式化词汇作为标题结尾（每个词汇最多使用1次）

### 事件分配（每章必须严格按照此分配生成，不得擅自修改）：
{events_assignment}

### 严格禁止：
1. ❌ 禁止在标题中使用"第N节"、"第N章"等简单编号形式
2. ❌ 禁止多个章节使用相同或相似的核心动词（如"对策"、"计划"、"行动"等）
3. ❌ 禁止标题只是简单在相同名词后加章节号（如"事务局对策1"、"事务局对策2"）
4. ❌ 禁止使用通用词汇如"情节推进"、"剧情发展"作为标题
5. ❌ 禁止标题重复或高度相似
6. ❌ 禁止使用相同的结尾词模式（如"XXX危机"、"XXX秘闻"、"XXX奇遇"反复出现）
7. ❌ 禁止直接使用事件类型名称作为标题（如事件类型是"危机爆发"，标题不能是"危机爆发"）

### 🎯 标题动词库（必须从中选择，禁止自行创造重复模式）：
- 动作类：勇闯、激战、潜入、追踪、刺杀、营救、偷袭、突围、埋伏、截杀、突袭、猛攻、智取、突围、奔袭
- 状态类：觉醒、蜕变、陨落、重生、爆发、崩溃、崛起、复苏、突破、进化、变异、融合、觉醒、升华
- 发现类：揭秘、发现、暴露、揭示、揭露、探知、洞察、察觉、挖掘、探索、搜寻、追踪、识破、揭晓
- 冲突类：交锋、对决、抗衡、博弈、较量、争斗、纷争、冲突、火拼、恶战、死斗、鏖战、血战、激战
- 情感类：背叛、重逢、决裂、守护、牺牲、救赎、复仇、宽恕、谅解、和解、别离、重逢、纠缠、牵绊
- 成长类：突破、晋级、蜕变、超越、升华、顿悟、领悟、掌握、精通、融会、贯通、精进、超越、升华

### 🏛️ 标题结构模式（必须严格交替使用，避免单一模式）：
| 结构类型 | 格式 | 示例 |
|---------|------|------|
| 主谓结构 | 主角+动作 | 林砚觉醒、苏清鸢出手 |
| 动宾结构 | 动作+对象 | 揭秘真相、追踪线索 |
| 偏正结构 | 修饰+名词 | 惊天秘密、诡异迷雾 |
| 并列结构 | 名词+名词 | 危机四伏、杀机暗藏 |
| 倒装结构 | 宾语+动作 | 真相浮现、杀机显现 |
| 动补结构 | 动作+结果 | 突围成功、阴谋败露 |

### ✅ 正确标题设计示例：
假如分配了："第 1 章 → 核心事件：入职冲突", "第 2 章 → 核心事件：盟友背叛", "第 3 章 → 核心事件：秘密揭露"
那么应该设计为：
- 第 1 章 → 标题："风波骤起"（偏正结构，不直接使用"冲突"）
- 第 2 章 → 标题："背后捅刀"（动宾结构，使用"背叛"的隐喻表达）
- 第 3 章 → 标题："惊天秘密"（偏正结构，不直接使用"揭露"）

### ❌ 错误示例（禁止使用，将导致生成失败）：
- ❌ 第1章-事务局危机
- ❌ 第2章-诡异危机  
- ❌ 第3章-死亡危机
- ❌ 第1章-神秘秘闻
- ❌ 第2章-惊人秘闻
- ❌ 第3章-核心秘闻
- ❌ 第1章-意外奇遇
- ❌ 第2章-神秘奇遇
- ❌ 第3章-惊险奇遇
- ❌ 第1章-危机爆发（直接使用事件类型名称）
- ❌ 第2章-秘密揭露（直接使用事件类型名称）

### 📋 标题多样性强制要求：
1. 每章标题必须使用**不同的核心动词**（从上方动词库中选择）
2. 每章标题必须使用**不同的核心名词**（避免重复使用相同的地点、组织、物品名称）
3. 每章标题必须使用**不同的结构模式**（交替使用主谓、动宾、偏正、并列、倒装、动补结构）
4. **"危机"、"秘闻"、"奇遇"、"风波"、"对决"等词汇整个批次最多使用2次**
5. 禁止连续2章使用相同结尾词
6. **必须从本章summary内容中提取关键元素作为标题**（如人名、地点、动作）
7. 鼓励使用生动的动作词汇和具象化的场景描述

## 🎯 章节标题生成规则（必读！）
章节标题是读者对章节内容的第一印象，**必须从本章内容中动态提取**，禁止套用固定模式！

### 标题生成步骤：
1. **阅读本章summary**，找出核心人物、关键动作、重要地点/物品
2. **选择标题结构**（必须交替使用不同结构）
3. **组合元素**形成标题（4-8字）
4. **检查唯一性**（确保与其他章节标题不重复）

### 标题生成示例（基于实际内容）：
假设本章summary是："林砚在新人培训中首次实战，意外觉醒特殊能力，震惊全场"
- ✅ 可提取：林砚（人物）、觉醒（动作）→ 标题："林砚觉醒"（主谓结构）
- ✅ 可提取：特殊能力（物品）、觉醒（动作）→ 标题："觉醒异能"（动宾结构）
- ❌ 禁止：危机、秘闻、奇遇等模式化词汇

假设本章summary是："苏清鸢带领小队潜入秘境，发现上古传承"
- ✅ 可提取：苏清鸢（人物）、潜入（动作）→ 标题："清鸢潜入"（主谓结构）
- ✅ 可提取：秘境（地点）、传承（物品）→ 标题："秘境传承"（偏正结构）
- ❌ 禁止：秘境奇遇（模式化）

### 标题格式：
**第 N 章 - 核心主题**（主题 4-8 字，简洁有力，必须反映本章内容）

### 多样化标题示例（供参考）：
- 主谓结构：林砚觉醒、清鸢出手、敌人来袭、传承显现
- 动宾结构：揭秘真相、追踪线索、突破重围、守护同伴
- 偏正结构：惊天秘密、诡异迷雾、上古传承、神秘玉佩
- 并列结构：危机四伏、杀机暗藏、祸福相依、生死相依
- 倒装结构：真相浮现、杀机显现、力量觉醒、命运交织
- 动补结构：突围成功、阴谋败露、计划失败、危机化解

## 番茄爆款硬性规则
1. **结尾钩子强制要求**：每章结尾必须设置以下三者其一：
   - 不可逆新危机（主角陷入绝境、关键人物死亡、核心目标受阻）
   - 颠覆性新线索（身世秘密曝光、反转真相揭示、隐藏反派现身）
   - 宿命感新羁绊（命运对决开启、情感关系剧变、生死契约缔结）
   禁止平淡收尾、日常结束。
   
2. **情绪爆点密度**：每 3 章至少设置 1 次强情绪爆点（愤怒/委屈/狂喜/揪心），绑定人性/认知碰撞

3. **配角高光规划**：为核心配角规划独立成长线，每 10 章安排一次专属高光时刻

4. **节奏要求**：每 500 字一个小起伏（小打脸、金手指生效、危机闪现、线索更新）

## 章节摘要差异化强制要求（★★★★★ 必须严格遵守）
⚠️ **严重警告**：如果本批次中有任何两个章节的摘要内容重复或高度相似，将被判定为生成失败！

### 摘要内容要求：
1. **唯一性**：每章摘要必须描述**本章独有的事件**，不得重复描述前面章节已经发生的内容
2. **递进性**：摘要必须体现情节推进，每章都要有**新的信息、新的冲突、新的转折**
3. **精准性**：摘要必须**具体描述本章发生的关键事件**，不能使用通用描述

### 错误示例（禁止使用）：
- ❌ "全球诡异复苏，林砚痛失亲人后通过选拔进入特殊异常事务局"（重复出现）
- ❌ "林砚在事务局的日常"（通用描述，无具体事件）
- ❌ "主角遇到新的挑战"（过于笼统）

### 正确示例：
- ✅ "林砚在新人培训中首次实战，意外觉醒特殊能力，震惊全场"（具体事件）
- ✅ "苏清鸢揭露诡异复苏背后的惊天秘密，林砚陷入两难抉择"（新信息+转折）
- ✅ "第三次副本开启，众人遭遇前所未有的强敌，林砚被迫暴露底牌"（情节推进）

### 摘要内容禁忌：
- ❌ 禁止重复描述背景设定（如"全球诡异复苏"只能在第一章出现一次）
- ❌ 禁止重复描述人物关系（如"结识苏清鸢"只能描述一次）
- ❌ 禁止重复描述已完成的事件（如"进入事务局"完成后不应再次描述）

## 严格要求
- title（章节标题）：必须严格按照上方分配的唯一核心事件来设计，**此批次 {batch_count} 章标题必须互不相同**
- summary（章节摘要）：50 字以内，简明扼要说明本章发生的关键事件
- beats 数组：每个 beat 必须包含 id、description、dramatic_function、story_circle_step 字段
- 章节编号从第 {actual_ch_start} 章开始
- 必须生成 **恰好 {batch_count} 个**章纲，不多不少
- 每章 {words_per_chapter} 字
- beats 每章 2-3 个即可，description 控制在 20 字内
- beats 的 dramatic_function 必须是以下之一：
  setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- story_circle_step 为 1-8 的整数，对应 Dan Harmon 8 步故事圈
- mandatory_tasks 列出本章不完成就审计不通过的叙事任务（1-2 个）
- emotional_arc 格式：{{"start": "开始情绪", "end": "结束情绪"}}
- sequence_id 统一填 "{sequence.id}"
- chapter_end_hook：每章必须有具体的结尾钩子描述
- **标题唯一性校验**：生成后请检查，确保 {batch_count} 个章纲的 title 没有一个重复

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
                    # 智能标题生成：从章节内容中动态提取
                    # ================================================
                    
                    # 定义丰富的标题词汇库（用于构建多样化标题）
                    ACTION_VERBS = ["觉醒", "突破", "发现", "遭遇", "击败", "获得", "揭露", "对决", 
                                   "逃离", "潜入", "营救", "追踪", "探索", "揭秘", "逆袭", "逆转"]
                    STATE_WORDS = ["骤变", "惊变", "异变", "危机", "转机", "决战", "抉择", "真相",
                                   "秘密", "阴谋", "奇遇", "风波", "突破", "觉醒", "爆发", "崛起"]
                    LOCATION_WORDS = ["秘境", "遗迹", "宫殿", "森林", "山脉", "洞穴", "基地", "学院"]
                    OBJECT_WORDS = ["神器", "法宝", "丹药", "功法", "秘籍", "传承", "线索", "证据"]
                    
                    def extract_title_from_content(summary: str, beats: list) -> str:
                        """从章节内容中提取标题"""
                        # 1. 从摘要提取关键词
                        keywords = []
                        if summary:
                            # 提取人名（常见姓氏）
                            import re
                            names = re.findall(r'[林苏沈顾陆叶萧楚秦韩赵魏齐周吴郑王刘陈杨张黄何郭罗马][^\s,，.。！？]{0,2}', summary)
                            # 提取动作词
                            actions = re.findall(r'(?:觉醒|突破|发现|遭遇|击败|获得|揭露|对决|逃离|潜入|营救|追踪|探索|揭秘)', summary)
                            # 提取关键名词
                            nouns = re.findall(r'(?:秘境|遗迹|神器|法宝|危机|秘密|真相|阴谋|传承|功法)', summary)
                            
                            keywords.extend(names[:2])
                            keywords.extend(actions[:2])
                            keywords.extend(nouns[:2])
                        
                        # 2. 从 beats 提取关键词
                        if beats:
                            for beat in beats[:2]:
                                if beat.description:
                                    # 提取动作和名词
                                    beat_actions = re.findall(r'(?:觉醒|突破|发现|遭遇|击败|获得|揭露)', beat.description)
                                    beat_nouns = re.findall(r'(?:秘境|遗迹|神器|法宝|危机|秘密)', beat.description)
                                    keywords.extend(beat_actions[:1])
                                    keywords.extend(beat_nouns[:1])
                        
                        return keywords
                    
                    def generate_title_from_content(chapter_num: int, summary: str, beats: list, sequence_events: list, index: int) -> str:
                        """基于章节内容生成唯一标题"""
                        keywords = extract_title_from_content(summary, beats)
                        
                        # 优先级1: 使用提取的关键词构建标题
                        if len(keywords) >= 2:
                            title = f"第{chapter_num}章-{keywords[0]}{keywords[1][:2]}"
                        elif len(keywords) == 1:
                            # 添加一个动作词
                            verb = ACTION_VERBS[index % len(ACTION_VERBS)]
                            title = f"第{chapter_num}章-{keywords[0]}{verb[:2]}"
                        else:
                            # 优先级2: 使用 key_events
                            if sequence_events:
                                event_index = (index * 7) % len(sequence_events)
                                event_text = sequence_events[event_index]
                                # 提取事件中的关键部分
                                import re
                                event_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', event_text)
                                if event_words:
                                    title = f"第{chapter_num}章-{event_words[0]}"
                                else:
                                    title = f"第{chapter_num}章-{event_text[:6]}"
                            else:
                                # 优先级3: 使用预设词汇（最后选项）
                                state_word = STATE_WORDS[index % len(STATE_WORDS)]
                                title = f"第{chapter_num}章-{state_word}"
                        
                        # 清理标题
                        title = title[:20]  # 限制长度
                        title = title.rstrip("，。！？：；、,.:;!?")
                        return title
                    
                    # 重新生成标题：优先从内容提取
                    if co.summary or co.beats:
                        new_title = generate_title_from_content(
                            co.chapter_number, 
                            co.summary, 
                            co.beats, 
                            sequence.key_events,
                            i + batch_idx * batch_count
                        )
                        # 只在新标题更好时替换
                        if len(new_title) > 6 and not any(p in new_title for p in ["情节推进", "剧情发展", "第"]):
                            co.title = new_title
                    elif "情节推进" in co.title or "剧情发展" in co.title or len(co.title) < 6:
                        # 生成更好的标题
                        co.title = generate_title_from_content(
                            co.chapter_number, 
                            "", 
                            co.beats, 
                            sequence.key_events,
                            i + batch_idx * batch_count
                        )
                    
                    # 清理标题末尾的标点符号
                    if co.title:
                        co.title = co.title.rstrip("，。！？：；、,.:;!?")
                    
                    # 强制去重：如果本章标题与同批次中前几章重复，用完全不同的标题替换
                    for prev_j in range(i):
                        if co.title == outlines[prev_j].title or \
                           (len(co.title) > 3 and len(outlines[prev_j].title) > 3 and 
                            co.title[3:] == outlines[prev_j].title[3:]):
                            # 使用完全不同的标题，基于内容重新生成
                            new_title = generate_title_from_content(
                                co.chapter_number,
                                co.summary,
                                co.beats,
                                sequence.key_events,
                                (i + batch_idx * batch_count) * 17  # 使用不同的种子
                            )
                            co.title = new_title
                            break
                if len(outlines) > batch_count:
                    outlines = outlines[:batch_count]
                elif len(outlines) < batch_count:
                    # 使用不同的事件类型作为后缀，避免重复
                    fallback_types = ["冲突", "危机", "秘闻", "奇遇", "决战", "逆袭", "阴谋", "真相", "抉择", "转折"]
                    for j in range(len(outlines), batch_count):
                        # 用章号+批次偏移保证 fallback 标题也不重复
                        fb_offset = (j + batch_idx * 7) % max(len(sequence.key_events), 1) if sequence.key_events else 0
                        type_suffix = fallback_types[(j + batch_idx) % len(fallback_types)]
                        fallback_title = f"第{actual_ch_start + j}章-{sequence.key_events[fb_offset][:4] if sequence.key_events else '剧情'}{type_suffix}"
                        outlines.append(ChapterOutlineSchema(
                            chapter_number=actual_ch_start + j,
                            title=fallback_title,
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
            
            # 进度回调：通知当前批次完成
            if progress_callback:
                progress_callback({
                    "stage": "generating",
                    "sequence_id": sequence.id,
                    "sequence_name": f"序列{sequence.id}",
                    "batch_index": batch_idx,
                    "total_batches": total_batches,
                    "chapters_completed": batch_end,
                    "total_chapters": n_chapters,
                    "message": f"已完成第 {actual_ch_start}-{actual_ch_start + batch_count - 1} 章大纲"
                })
        
        # ═══════════════════════════════════════════════════════════════════════
        # 独立标题生成：专注生成高质量、多样化的标题
        # ═══════════════════════════════════════════════════════════════════════
        all_outlines = self._generate_titles_for_outlines(all_outlines, sequence, protagonist)
        
        return all_outlines
    
    def _generate_titles_for_outlines(
        self,
        outlines: list[ChapterOutlineSchema],
        sequence: SequenceSchema,
        protagonist: CharacterSchema
    ) -> list[ChapterOutlineSchema]:
        """独立生成标题：基于所有章节内容生成高质量、多样化的标题"""
        
        if not outlines:
            return outlines
        
        # 构建章节内容摘要列表
        chapters_info = []
        for i, co in enumerate(outlines):
            chapters_info.append({
                "chapter_number": co.chapter_number,
                "summary": co.summary,
                "beats": [b.description for b in co.beats] if co.beats else [],
            })
        
        # 先将 JSON 序列化，避免与 f-string 冲突
        chapters_json = json.dumps(chapters_info, ensure_ascii=False, indent=2)
        
        # 构建标题生成提示词
        prompt = f"""
你是一位资深的小说编辑，擅长为章节生成吸引人且多样化的标题。

## 任务：为以下 {len(outlines)} 个章节生成独特的标题

### 核心要求：
1. **唯一性**：所有标题必须互不相同，禁止重复或高度相似
2. **内容相关性**：每个标题必须直接反映对应章节的内容
3. **结构多样性**：交替使用不同的标题结构（主谓、动宾、偏正、并列、倒装、动补）
4. **词汇多样性**：禁止连续使用相同的结尾词（如"危机"、"秘闻"、"奇遇"最多使用2次）

### 标题生成规则：
- 从每个章节的summary中提取关键元素（人名、动作、地点、物品）
- 标题长度：4-8个字，简洁有力
- 格式：第N章-标题内容
- 禁止使用模式化词汇：危机、秘闻、奇遇、风波、对决（每个最多使用2次）

### 标题结构模式（必须交替使用）：
- 主谓结构：主角+动作（如"林砚觉醒"）
- 动宾结构：动作+对象（如"揭秘真相"）
- 偏正结构：修饰+名词（如"惊天秘密"）
- 并列结构：名词+名词（如"危机四伏"）
- 倒装结构：宾语+动作（如"真相浮现"）
- 动补结构：动作+结果（如"突围成功"）

### 章节内容：
{chapters_json}

### 主角信息（参考）：
- 姓名：{protagonist.name}
- 身份：{protagonist.role}

### 输出格式：
只输出JSON数组，包含{len(outlines)}个对象，每个对象包含 "chapter_number" 和 "title" 字段。

示例输出：
[
  {{"chapter_number": 1, "title": "第1章-林砚觉醒"}},
  {{"chapter_number": 2, "title": "第2章-秘境探索"}},
  {{"chapter_number": 3, "title": "第3章-传承获得"}}
]
"""
        
        def _call_titles():
            resp = self.llm.complete([
                LLMMessage("system", "你是精通标题设计的小说编辑，只输出合法JSON数组。"),
                LLMMessage("user", prompt),
            ])
            # 解析响应
            try:
                titles_data = json.loads(resp.content)
                return titles_data
            except:
                return None
        
        # 调用AI生成标题
        try:
            titles_data = with_retry(_call_titles)
            
            if titles_data and isinstance(titles_data, list):
                # 更新标题
                title_map = {t["chapter_number"]: t["title"] for t in titles_data if isinstance(t, dict)}
                for co in outlines:
                    if co.chapter_number in title_map:
                        new_title = title_map[co.chapter_number]
                        # 验证标题质量
                        if len(new_title) >= 6 and "情节推进" not in new_title and "剧情发展" not in new_title:
                            co.title = new_title
        
        except Exception as e:
            # 如果独立标题生成失败，保持原有标题（已有后处理保障）
            pass
        
        # 最后执行强制去重和优化
        return self._optimize_titles_post_process(outlines)
    
    def _optimize_titles_post_process(self, outlines: list[ChapterOutlineSchema]) -> list[ChapterOutlineSchema]:
        """后处理优化：确保所有标题唯一且多样化"""
        
        # 定义丰富的替代词汇
        RICH_VERBS = ["觉醒", "突破", "蜕变", "逆袭", "逆转", "爆发", "崛起", "陨落", "复苏", "进化",
                     "揭秘", "揭露", "发现", "洞察", "识破", "追踪", "搜寻", "探索", "挖掘", "揭晓"]
        RICH_STATES = ["骤变", "惊变", "异变", "突变", "剧变", "逆转", "逆袭", "突破", "觉醒", "爆发",
                      "崩塌", "瓦解", "粉碎", "破灭", "毁灭", "重建", "复兴", "崛起", "陨落", "复苏"]
        
        seen_titles = set()
        for i, co in enumerate(outlines):
            original = co.title
            
            # 清理标题
            if co.title:
                co.title = co.title.rstrip("，。！？：；、,.:;!?")
            
            # 确保唯一性
            counter = 0
            while co.title in seen_titles:
                # 使用丰富的后缀，避免模式化
                suffix = RICH_STATES[counter % len(RICH_STATES)]
                co.title = f"{original[:-2] if len(original) > 2 else original}{suffix[:2]}"
                counter += 1
                if counter > 20:
                    co.title = f"{original}[{counter}]"
                    break
            
            seen_titles.add(co.title)
        
        return outlines

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
