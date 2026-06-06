"""
质量评估体系数据类型定义

包含六个核心评判维度（情节、人物、设定、语言、阅读体验、类型适配）
和六大连贯性层次（时间、空间、逻辑、情绪、信息、风格）的数据结构
"""
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Dict
from datetime import datetime


# ── 质量问题定义 ──────────────────────────────────────────────────────────────

@dataclass
class QualityIssue:
    """质量问题"""
    severity: Literal["critical", "warning", "info"]
    description: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    excerpt: Optional[str] = None


# ── 维度评分定义 ──────────────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    """维度评分"""
    dimension: str
    score: int  # 0-100
    max_score: int = 100
    issues: List[QualityIssue] = field(default_factory=list)
    weight: float = 1.0


# ── 质量报告定义 ──────────────────────────────────────────────────────────────

@dataclass
class QualityReport:
    """质量评估报告"""
    chapter_number: int
    overall_score: int
    dimension_scores: List[DimensionScore]
    consistency_scores: List[DimensionScore]
    genre: str
    genre_fit_score: int
    improvement_suggestions: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── 类型特征矩阵 ──────────────────────────────────────────────────────────────

@dataclass
class GenreCriteria:
    """类型特征矩阵"""
    genre: str
    criteria: List[str]
    weights: Dict[str, float]


# ── 修订结果定义 ──────────────────────────────────────────────────────────────

@dataclass
class QualityReviseResult:
    """质量评估修订结果（参考 ReviseResult）"""
    content: str
    change_log: List[str]
    revised_issues: List[str]  # 已修复的问题列表


# ── 类型特征矩阵配置 ──────────────────────────────────────────────────────────

GENRE_MATRIX: List[GenreCriteria] = [
    GenreCriteria(
        genre="悬疑/推理",
        criteria=["逻辑严密性", "线索埋设", "结局合理性"],
        weights={"逻辑严密性": 0.4, "线索埋设": 0.3, "结局合理性": 0.3}
    ),
    GenreCriteria(
        genre="言情",
        criteria=["情感真实性", "人物关系张力", "甜虐节奏"],
        weights={"情感真实性": 0.4, "人物关系张力": 0.35, "甜虐节奏": 0.25}
    ),
    GenreCriteria(
        genre="科幻/奇幻",
        criteria=["世界观完整性", "设定创新性", "设定与剧情结合"],
        weights={"世界观完整性": 0.4, "设定创新性": 0.3, "设定与剧情结合": 0.3}
    ),
    GenreCriteria(
        genre="恐怖",
        criteria=["氛围营造", "心理压迫感", "留白技巧"],
        weights={"氛围营造": 0.4, "心理压迫感": 0.35, "留白技巧": 0.25}
    ),
    GenreCriteria(
        genre="悬疑脑洞",
        criteria=["规则设定新颖性", "悬念保持度", "世界观一致性", "氛围营造"],
        weights={"规则设定新颖性": 0.3, "悬念保持度": 0.3, "世界观一致性": 0.2, "氛围营造": 0.2}
    ),
    GenreCriteria(
        genre="网文",
        criteria=["开篇钩子", "爽点密度", "追读欲望"],
        weights={"开篇钩子": 0.4, "爽点密度": 0.3, "追读欲望": 0.3}
    ),
]


# ── 评估维度配置 ──────────────────────────────────────────────────────────────

QUALITY_DIMENSIONS = [
    ("情节", "评估开篇冲突建立、因果链条完整性、节奏张弛、结局呼应"),
    ("人物", "评估主角欲望与缺陷、配角独立性、反派逻辑、人物弧光"),
    ("设定", "评估设定新意、逻辑自洽、规则与代价、服务故事"),
    ("语言", "评估视觉描写丰富度、感官细节密度、比喻新颖度、句式变化"),
    ("阅读体验", "评估结尾钩子强度、信息密度、悬念设置、情感共鸣"),
    ("类型适配", "根据类型特征矩阵评估作品与类型的契合度"),
]

CONSISTENCY_LEVELS = [
    ("时间", "检查时间线清晰、倒叙/插叙标记、时间跳跃说明"),
    ("空间", "检查移动交代、场景切换过渡、空间关系合理"),
    ("逻辑", "检查因果完整性、动机合理性、规则一致性、能力成长过程"),
    ("情绪", "检查情绪反应匹配、情绪转变过渡、性格一致性"),
    ("信息", "检查能力获得过程、信息来源交代、物品连续性"),
    ("风格", "检查语言风格统一、叙事视角统一、命名规则统一"),
]