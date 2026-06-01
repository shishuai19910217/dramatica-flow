"""
Agent 通信协议模块
实现结构化只读文档传递机制：
- 上层输出为「结构化只读文档」
- 下层 Agent 只有读取权，没有修改权
- 所有传递数据为标准化 Markdown + JSON 结构化数据
- 下级创作必须逐条对上校验，不满足则触发审计报错

整合用户设计中的核心思想：
- 流水线串行 + 逐级约束
- Agent 通信协议标准化
- 审计闭环逻辑
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, Any
from enum import Enum
from pathlib import Path


class DocumentType(str, Enum):
    GLOBAL_OUTLINE = "global_outline"       # 全局三幕大纲（Agent1 输出）
    WORLD_SETTING = "world_setting"         # 世界观设定集（Agent2 输出）
    CHAPTER_OUTLINES = "chapter_outlines"   # 章节细纲（Agent3 输出）
    CHAPTER_CONTENT = "chapter_content"     # 章节正文（Agent4 输出）
    AUDIT_REPORT = "audit_report"           # 审计报告（Agent5 输出）


class ConstraintLevel(str, Enum):
    HARD = "hard"      # 硬约束：不可违反，违反则审计 critical
    SOFT = "soft"      # 软约束：建议性，违反则审计 warning
    INFO = "info"      # 信息性：仅供参考


@dataclass
class ConstraintRule:
    id: str
    level: ConstraintLevel
    description: str
    source_agent: str           # 来自哪个 Agent
    target_agents: list[str]    # 约束哪些 Agent
    validation_rule: str = ""   # 校验规则描述


@dataclass
class StructuredDocument:
    """
    结构化只读文档：Agent 之间传递的数据载体
    """
    doc_type: DocumentType
    source_agent: str
    target_agents: list[str]
    content_json: dict[str, Any]        # JSON 格式的结构化数据
    content_md: str = ""                # Markdown 格式的可读版本
    constraints: list[ConstraintRule] = field(default_factory=list)
    version: int = 1
    is_read_only: bool = True           # 标记为只读，下层不可修改
    checksum: str = ""                  # 数据校验和，防止篡改

    def to_json(self) -> str:
        return json.dumps({
            "doc_type": self.doc_type.value,
            "source_agent": self.source_agent,
            "target_agents": self.target_agents,
            "content_json": self.content_json,
            "content_md": self.content_md,
            "constraints": [
                {
                    "id": c.id,
                    "level": c.level.value,
                    "description": c.description,
                    "source_agent": c.source_agent,
                    "target_agents": c.target_agents,
                    "validation_rule": c.validation_rule,
                }
                for c in self.constraints
            ],
            "version": self.version,
            "is_read_only": self.is_read_only,
            "checksum": self.checksum,
        }, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> StructuredDocument:
        data = json.loads(json_str)
        constraints = [
            ConstraintRule(
                id=c["id"],
                level=ConstraintLevel(c["level"]),
                description=c["description"],
                source_agent=c["source_agent"],
                target_agents=c["target_agents"],
                validation_rule=c.get("validation_rule", ""),
            )
            for c in data.get("constraints", [])
        ]
        return cls(
            doc_type=DocumentType(data["doc_type"]),
            source_agent=data["source_agent"],
            target_agents=data["target_agents"],
            content_json=data["content_json"],
            content_md=data.get("content_md", ""),
            constraints=constraints,
            version=data.get("version", 1),
            is_read_only=data.get("is_read_only", True),
            checksum=data.get("checksum", ""),
        )


# ── 全局约束规则库（整合用户设计）─────────────────────────────────────────────

GLOBAL_CONSTRAINTS: list[ConstraintRule] = [
    # Agent1 → Agent2/3/4/5 的硬约束
    ConstraintRule(
        id="C001",
        level=ConstraintLevel.HARD,
        description="三幕式框架不可修改：第一幕25%、第二幕50%、第三幕25%的章节分配",
        source_agent="Agent1_GlobalArchitect",
        target_agents=["Agent2_WorldBuilder", "Agent3_ChapterPlanner", "Agent4_Writer", "Agent5_Auditor"],
        validation_rule="章节分布必须符合三幕比例",
    ),
    ConstraintRule(
        id="C002",
        level=ConstraintLevel.HARD,
        description="四大关键锚点必须落地：开篇钩子、中点反转、灵魂黑夜、终局高潮",
        source_agent="Agent1_GlobalArchitect",
        target_agents=["Agent3_ChapterPlanner", "Agent4_Writer", "Agent5_Auditor"],
        validation_rule="关键锚点必须在对应章节位置实现",
    ),
    ConstraintRule(
        id="C003",
        level=ConstraintLevel.HARD,
        description="四大硬性故事线贯穿全书：主角成长线、反派博弈线、关系拉扯线、外部事件线",
        source_agent="Agent1_GlobalArchitect",
        target_agents=["Agent2_WorldBuilder", "Agent3_ChapterPlanner", "Agent4_Writer", "Agent5_Auditor"],
        validation_rule="每个序列必须服务至少一条故事线",
    ),
    # Agent2 → Agent3/4/5 的硬约束
    ConstraintRule(
        id="C004",
        level=ConstraintLevel.HARD,
        description="Dramatica 四大故事线锁定：主角内心成长线、反派博弈线、关系拉扯线、外部事件线不可偏离",
        source_agent="Agent2_WorldBuilder",
        target_agents=["Agent3_ChapterPlanner", "Agent4_Writer", "Agent5_Auditor"],
        validation_rule="角色行为必须符合故事线设定",
    ),
    ConstraintRule(
        id="C005",
        level=ConstraintLevel.HARD,
        description="人设锁定：角色的 behavior_lock 绝对不可违反",
        source_agent="Agent2_WorldBuilder",
        target_agents=["Agent4_Writer", "Agent5_Auditor"],
        validation_rule="角色不能做性格锁定中禁止的事",
    ),
    ConstraintRule(
        id="C006",
        level=ConstraintLevel.HARD,
        description="信息边界：角色只能知道亲眼所见/亲耳所闻的信息",
        source_agent="Agent2_WorldBuilder",
        target_agents=["Agent4_Writer", "Agent5_Auditor"],
        validation_rule="角色信息获取必须有合理来源",
    ),
    # Agent3 → Agent4/5 的硬约束
    ConstraintRule(
        id="C007",
        level=ConstraintLevel.HARD,
        description="章节细纲必须服从：mandatory_tasks 必须完成，核心冲突必须落地",
        source_agent="Agent3_ChapterPlanner",
        target_agents=["Agent4_Writer", "Agent5_Auditor"],
        validation_rule="正文必须完成章纲的所有 mandatory_tasks",
    ),
    ConstraintRule(
        id="C008",
        level=ConstraintLevel.SOFT,
        description="Dan Harmon 8步故事圈节奏建议：每章应有小冲突、小欲望、小挫折、小反转",
        source_agent="Agent3_ChapterPlanner",
        target_agents=["Agent4_Writer", "Agent5_Auditor"],
        validation_rule="章节节奏应符合故事圈步骤",
    ),
    ConstraintRule(
        id="C009",
        level=ConstraintLevel.HARD,
        description="章节末悬念钩子必须实现：章末必须有驱动读者继续读的钩子",
        source_agent="Agent3_ChapterPlanner",
        target_agents=["Agent4_Writer", "Agent5_Auditor"],
        validation_rule="章末钩子必须有效实现",
    ),
    # Agent4 → Agent5 的约束
    ConstraintRule(
        id="C010",
        level=ConstraintLevel.HARD,
        description="写后结算表必须与正文一致：结算表记录的状态变化必须在正文中有体现",
        source_agent="Agent4_Writer",
        target_agents=["Agent5_Auditor"],
        validation_rule="结算表与正文交叉验证",
    ),
]


# ── Agent 通信协议校验器 ────────────────────────────────────────────────────────

class ProtocolValidator:
    """
    校验 Agent 之间的数据传递是否符合协议规范
    """

    def __init__(self, constraints: list[ConstraintRule] = None):
        self.constraints = constraints or GLOBAL_CONSTRAINTS

    def validate_document(
        self,
        doc: StructuredDocument,
        target_agent: str,
    ) -> list[dict[str, Any]]:
        """
        校验文档对目标 Agent 的约束是否满足
        返回违反的约束列表
        """
        violations = []
        for c in self.constraints:
            if target_agent not in c.target_agents:
                continue
            if c.source_agent != doc.source_agent:
                continue
            violations.append({
                "constraint_id": c.id,
                "level": c.level.value,
                "description": c.description,
                "validation_rule": c.validation_rule,
            })
        return violations

    def get_hard_constraints_for_agent(
        self,
        source_agent: str,
        target_agent: str,
    ) -> list[ConstraintRule]:
        """获取指定 Agent 之间的硬约束"""
        return [
            c for c in self.constraints
            if c.level == ConstraintLevel.HARD
            and c.source_agent == source_agent
            and target_agent in c.target_agents
        ]


# ── 审计闭环公式（整合用户设计）───────────────────────────────────────────────

AUDIT_FORMULA = """
最终正文 = (
    三幕全局框架约束
    + Dramatica 四线逻辑约束
    + 8步章节细纲约束
    + 四大关键锚点约束
) + 自动纠错修正

校验流程：
1. 大纲对齐审计：正文 VS 章纲
2. 人设逻辑审计：正文 VS Dramatica 设定
3. 节奏合规审计：正文 VS 三幕式节奏

审计动作：
- 轻微偏离：自动改写修正正文
- 中度偏离：局部重写段落
- 严重偏离：拒绝输出、回滚重绘
"""


def format_audit_formula() -> str:
    """返回审计闭环公式（用于审计 Agent 提示词）"""
    return AUDIT_FORMULA.strip()