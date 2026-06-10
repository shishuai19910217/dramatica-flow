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
    ) -> list[ChapterOutlineSchema]:
        """
        将一个序列展开为 estimated_scenes 个章纲。
        严格按照 estimated_scenes 控制生成章数。
        如果章数过多则分批调用 LLM，避免输出超出 max_tokens 被截断。
        previous_chapter_titles: 前面序列已生成的章节标题列表，用于防止跨序列重复。
        genre: 书籍题材，用于选择对应事件类型词汇库。
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
            
            # 2. 如果 key_events 数量不足，补充预定义词汇库事件
            if len(derived_events) < n_chapters:
                # 获取题材相关的预定义事件类型词汇库
                genre_events = {
                    # 都市题材
                    "都市": [
                        "职场博弈", "商业谈判", "创业逆袭", "都市奇遇", "豪门恩怨",
                        "科技创业", "金融对决", "职场晋升", "都市传说", "爱情纠葛",
                        "卧底行动", "商业间谍", "行业黑幕", "资本运作", "职场危机",
                        "明星绯闻", "时尚潮流", "美食探店", "房产投资", "网络红人"
                    ],
                    # 玄幻题材
                    "玄幻": [
                        "功法突破", "秘境探险", "宗门斗争", "神兽契约", "丹道炼丹",
                        "器道炼器", "符道制符", "阵道布阵", "血脉觉醒", "武魂融合",
                        "渡劫飞升", "仙魔大战", "秘境寻宝", "传承获得", "奇遇机缘",
                        "正邪对立", "宗门大比", "丹会论道", "拍卖会风波", "古遗迹探险"
                    ],
                    # 科幻题材
                    "科幻": [
                        "星际探索", "人工智能", "时间旅行", "外星接触", "机械改造",
                        "量子跃迁", "维度穿越", "赛博空间", "基因编辑", "纳米科技",
                        "宇宙战争", "文明碰撞", "虫洞探险", "意识上传", "虚拟世界",
                        "太空殖民", "反物质能源", "黑洞奥秘", "平行宇宙", "时间悖论"
                    ],
                    # 科幻末世题材
                    "科幻末世": [
                        "病毒爆发", "末日求生", "废土重建", "变异生物", "资源争夺",
                        "基地建设", "幸存者联盟", "科技残留", "外星入侵", "时间重置",
                        "地下避难", "辐射变异", "机甲战斗", "基因改造", "人工智能反叛",
                        "生态崩溃", "星际移民", "旧日支配者", "秘境探索", "文明火种"
                    ],
                    # 历史题材
                    "历史": [
                        "王朝更迭", "宫廷权谋", "战场厮杀", "丝绸之路", "文化交融",
                        "帝王传奇", "名将征战", "文人墨客", "商业传奇", "民族融合",
                        "变法图强", "农民起义", "外交谋略", "宗教兴衰", "科技发明",
                        "艺术巅峰", "航海探险", "贸易繁荣", "城市崛起", "家族兴衰"
                    ],
                    # 悬疑题材
                    "悬疑": [
                        "连环凶案", "密室杀人", "身份谜团", "记忆碎片", "真假难辨",
                        "卧底迷局", "密码破译", "离奇失踪", "幽灵传说", "心理操控",
                        "连环陷阱", "真假证词", "隐匿身份", "暗中观察", "致命游戏",
                        "时间胶囊", "记忆篡改", "梦境入侵", "虚拟现实", "意识操控"
                    ],
                    # 悬疑脑洞题材
                    "悬疑脑洞": [
                        "无限循环", "记忆植入", "平行世界", "时间悖论", "梦境嵌套",
                        "意识上传", "虚拟实境", "记忆篡改", "量子纠缠", "因果律武器",
                        "蝴蝶效应", "时空折叠", "维度穿越", "意识入侵", "数字幽灵",
                        "神经接口", "脑机交互", "记忆碎片", "意识投影", "时间裂隙"
                    ],
                    # 仙侠题材
                    "仙侠": [
                        "修仙问道", "御剑飞行", "仙府探秘", "丹药炼制", "法宝祭炼",
                        "灵根觉醒", "功法传承", "仙缘奇遇", "渡劫飞升", "仙界纷争",
                        "神魔大战", "秘境探险", "仙侣情缘", "宗门竞争", "上古遗迹",
                        "天道感悟", "法则领悟", "仙魔一念", "轮回转世", "因果纠缠"
                    ],
                    # 言情题材
                    "言情": [
                        "一见钟情", "日久生情", "误会重重", "破镜重圆", "豪门虐恋",
                        "青梅竹马", "欢喜冤家", "霸道总裁", "温柔学长", "校园初恋",
                        "职场恋情", "异地相思", "日久见人心", "深情守护", "爱而不得",
                        "命中注定", "跨越阶层", "家族恩怨", "追妻火葬场", "双向奔赴"
                    ],
                    # 游戏题材
                    "游戏": [
                        "虚拟游戏", "游戏重生", "NPC觉醒", "游戏入侵现实", "数据成神",
                        "职业选择", "副本挑战", "公会争霸", "装备锻造", "技能升级",
                        "隐藏任务", "BOSS击杀", "游戏货币", "虚拟爱情", "游戏直播",
                        "电竞比赛", "游戏开发", "游戏测试", "游戏BUG", "游戏管理员"
                    ],
                    # 无限流题材
                    "无限流": [
                        "轮回空间", "副本挑战", "主神空间", "无限任务", "强化升级",
                        "团队协作", "智斗布局", "恐怖副本", "科幻世界", "玄幻位面",
                        "武侠世界", "末日求生", "动漫穿越", "电影世界", "神话传说",
                        "因果律武器", "时间能力", "空间能力", "基因锁", "最终进化"
                    ],
                    # 默认通用事件类型
                    "其他": [
                        "冲突爆发", "危机化解", "秘密揭露", "盟友背叛", "关键抉择",
                        "绝境逆袭", "真相大白", "计划失败", "意外发现", "命运转折",
                        "阴谋败露", "危机升级", "盟友加入", "技能突破", "真相反转",
                        "陷阱布置", "危机解除", "秘密潜入", "身份暴露", "决战前夕"
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

### 事件分配（每章必须严格按照此分配生成，不得擅自修改）：
{events_assignment}

### 严格禁止：
1. ❌ 禁止在标题中使用"第N节"、"第N章"等简单编号形式
2. ❌ 禁止多个章节使用相同或相似的核心动词（如"对策"、"计划"、"行动"等）
3. ❌ 禁止标题只是简单在相同名词后加章节号（如"事务局对策1"、"事务局对策2"）
4. ❌ 禁止使用通用词汇如"情节推进"、"剧情发展"作为标题
5. ❌ 禁止标题重复或高度相似

### 正确标题设计示例：
假如分配了："第 1 章 → 核心事件：入职冲突", "第 2 章 → 核心事件：盟友背叛", "第 3 章 → 核心事件：秘密揭露"
那么应该设计为：
- 第 1 章 → 标题："入职风波"或"考核危机"（与其他章节完全不同）
- 第 2 章 → 标题："背后捅刀"或"盟友反目"（使用不同的动词和名词）
- 第 3 章 → 标题："惊天秘密"或"真相浮出"（使用独特的核心词汇）

### 错误示例（禁止使用，将导致生成失败）：
- ❌ 第1章-事务局对策1
- ❌ 第2章-事务局对策2  
- ❌ 第3章-事务局对策3
- ❌ 第1章-执行任务
- ❌ 第2章-执行计划
- ❌ 第3章-执行行动

### 标题多样性要求：
- 每章标题必须使用**不同的核心动词**（如"风波"、"危机"、"秘闻"、"奇遇"、"决战"等）
- 每章标题必须使用**不同的核心名词**（避免重复使用相同的地点、组织、物品名称）
- 鼓励使用生动的动作词汇和具象化的场景描述

## 章节标题要求（非常重要，必须严格遵守）
章节标题是读者对章节内容的第一印象，必须**直接反映该章分配的唯一核心事件**，禁止使用"情节推进""剧情发展"等通用词汇。

**标题格式**：第 N 章 - 核心主题（主题 4-8 字，简洁有力）
**标题示例**：
- 第 1 章 - 退婚之辱
- 第 2 章 - 神秘玉佩
- 第 3 章 - 青锋山脉
- 第 4 章 - 意外传承
- 第 5 章 - 宗门考核
- 第 6 章 - 秘境奇遇
- 第 7 章 - 生死之战
- 第 8 章 - 真相大白
（注意：以上只是格式参考，内容必须根据你当前序列的实际情况设计）

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
                    co.chapter_number = actual_ch_start + i
                    # 始终使用书籍设置中的目标字数覆盖所有章节
                    co.target_words = words_per_chapter
                    # 后处理：替换通用标题为有意义的标题
                    if co.title and ("情节推进" in co.title or "剧情发展" in co.title or "章-" == co.title[-2:]):
                        # 尝试从 beats 或 summary 提取关键词
                        keywords = []
                        if co.beats:
                            for beat in co.beats:
                                if beat.description:
                                    keywords.extend(beat.description[:4].split()[:2])
                        if co.summary:
                            keywords.extend(co.summary[:8].split()[:2])
                        if keywords:
                            co.title = f"第{co.chapter_number}章-{''.join(keywords[:2])[:6]}"
                        elif sequence.key_events:
                            # 用 chapter_number 做偏移，保证同一批次内即使 key_events 不够也不重复
                            event_index = (i * 7 + batch_idx * 13) % max(len(sequence.key_events), 1)
                            co.title = f"第{co.chapter_number}章-{sequence.key_events[event_index][:6]}"
                        else:
                            co.title = f"第{co.chapter_number}章-序章{co.chapter_number}"
                    # 清理标题末尾的标点符号
                    if co.title:
                        co.title = co.title.rstrip("，。！？：；、,.:;!?")
                    
                    # 强制去重：如果本章标题与同批次中前几章重复，用完全不同的标题替换
                    unique_suffixes = ["风波", "危机", "秘闻", "奇遇", "决战", "逆袭", "阴谋", "真相", "抉择", "转折"]
                    for prev_j in range(i):
                        if co.title == outlines[prev_j].title or (co.title[3:] and outlines[prev_j].title[3:] and co.title[3:].startswith(outlines[prev_j].title[3:])):
                            # 使用完全不同的标题，而不是追加章节号
                            original_title = co.title
                            base_title = original_title[3:] if len(original_title) > 3 else ""
                            # 如果标题包含"节"或简单编号，完全重写
                            if "节" in original_title or any(c.isdigit() for c in base_title[-3:]):
                                suffix = unique_suffixes[(i + batch_idx) % len(unique_suffixes)]
                                co.title = f"第{co.chapter_number}章-{sequence.key_events[0][:4] if sequence.key_events else '剧情'}{suffix}"
                            else:
                                # 追加一个有意义的后缀
                                suffix = unique_suffixes[(i + batch_idx) % len(unique_suffixes)]
                                co.title = f"{original_title}{suffix}"
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
