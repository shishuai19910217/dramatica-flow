"""
质量评估 Agent 单元测试

测试内容：
1. QualityAgent 初始化测试
2. 六个核心维度评估测试
3. 六大连贯性层次检查测试
4. 类型适配评估测试
5. 修订功能测试
6. Pipeline 集成测试
"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Optional

# 导入测试目标
from core.agents import QualityAgent
from core.types.quality import (
    QualityIssue, DimensionScore, QualityReport, QualityReviseResult,
    GENRE_MATRIX, QUALITY_DIMENSIONS, CONSISTENCY_LEVELS
)
from core.agents import ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement


class TestQualityAgent:
    """QualityAgent 单元测试类"""

    def setup_method(self):
        """测试前准备：创建模拟 LLM Provider"""
        self.mock_llm = Mock()
        self.mock_llm.complete = Mock(return_value=Mock(content="""{
            "chapter_number": 1,
            "overall_score": 85,
            "dimension_scores": [
                {"dimension": "情节", "score": 88, "issues": []},
                {"dimension": "人物", "score": 82, "issues": []},
                {"dimension": "设定", "score": 85, "issues": []},
                {"dimension": "语言", "score": 88, "issues": []},
                {"dimension": "阅读体验", "score": 80, "issues": []},
                {"dimension": "类型适配", "score": 85, "issues": []}
            ],
            "consistency_scores": [
                {"dimension": "时间", "score": 90, "issues": []},
                {"dimension": "空间", "score": 88, "issues": []},
                {"dimension": "逻辑", "score": 85, "issues": []},
                {"dimension": "情绪", "score": 82, "issues": []},
                {"dimension": "信息", "score": 88, "issues": []},
                {"dimension": "风格", "score": 90, "issues": []}
            ],
            "genre": "悬疑/推理",
            "genre_fit_score": 85,
            "improvement_suggestions": ["增加悬念设置", "提升节奏张力"]
        }"""))
        
        self.quality_agent = QualityAgent(self.mock_llm)
        
        # 创建测试数据
        self.blueprint = ArchitectBlueprint(
            core_conflict="主角发现神秘事件",
            hooks_to_advance=[],
            hooks_to_plant=["神秘玉佩"],
            emotional_journey={"start": "疑惑", "end": "震惊"},
            chapter_end_hook="神秘人出现",
            pace_notes="适中",
            pre_write_checklist=PreWriteChecklist(
                active_characters=["主角", "配角"],
                required_locations=["房间"],
                resources_in_play=["玉佩"],
                hooks_status=[],
                risk_scan="无"
            )
        )
        
        self.settlement = PostWriteSettlement(
            resource_changes=["玉佩发光"],
            new_hooks=["玉佩之谜"],
            resolved_hooks=[],
            relationship_changes=["主角-配角：+10"],
            info_revealed=[{"character_id": "主角", "info_key": "秘密", "content": "发现秘密"}],
            character_position_changes=[{"character_id": "主角", "location_id": "房间"}],
            emotional_changes=[{"character_id": "主角", "emotion": "震惊", "intensity": 8, "trigger": "发现秘密"}]
        )

    def test_init(self):
        """测试 QualityAgent 初始化"""
        assert self.quality_agent.llm == self.mock_llm
        assert self.quality_agent.DIMENSIONS == ["情节", "人物", "设定", "语言", "阅读体验", "类型适配"]
        assert self.quality_agent.CONSISTENCY_LEVELS == ["时间", "空间", "逻辑", "情绪", "信息", "风格"]
        assert self.quality_agent.MAX_REVISE_ROUNDS == 2

    def test_evaluate_chapter(self):
        """测试章节质量评估功能"""
        content = "第一章 神秘事件\n主角走进房间，发现了一块发光的玉佩。"
        
        result_content, report = self.quality_agent.evaluate_chapter(
            chapter_content=content,
            chapter_number=1,
            genre="悬疑/推理",
            blueprint=self.blueprint,
            truth_context="测试上下文",
            settlement=self.settlement,
            auto_revise=False
        )
        
        assert isinstance(report, QualityReport)
        assert report.chapter_number == 1
        assert report.overall_score == 85
        assert report.genre == "悬疑/推理"
        assert report.genre_fit_score == 85
        
        # 验证六个核心维度
        dimension_names = [d.dimension for d in report.dimension_scores]
        assert set(dimension_names) == set(["情节", "人物", "设定", "语言", "阅读体验", "类型适配"])
        
        # 验证六大连贯性层次
        consistency_names = [c.dimension for c in report.consistency_scores]
        assert set(consistency_names) == set(["时间", "空间", "逻辑", "情绪", "信息", "风格"])

    def test_revise(self):
        """测试修订功能"""
        # 创建包含问题的质量报告
        issues = [
            QualityIssue(
                severity="warning",
                description="节奏稍显拖沓",
                suggestion="增加紧张感"
            )
        ]
        dimension_score = DimensionScore(
            dimension="情节",
            score=75,
            issues=issues
        )
        quality_report = QualityReport(
            chapter_number=1,
            overall_score=75,
            dimension_scores=[dimension_score],
            consistency_scores=[],
            genre="悬疑/推理",
            genre_fit_score=75
        )
        
        content = "主角慢慢地走进房间，四处看了看，然后发现了玉佩。"
        
        # 模拟修订响应
        self.mock_llm.complete = Mock(return_value=Mock(content="""主角快步走进房间，目光锐利地扫视四周，突然发现了那块发光的玉佩。

["加快了节奏，增加紧张感"]"""))
        
        result = self.quality_agent.revise(content, quality_report, mode="spot-fix")
        
        assert isinstance(result, QualityReviseResult)
        assert "快步" in result.content
        assert "目光锐利" in result.content
        assert "突然" in result.content
        assert "加快了节奏" in result.change_log[0]

    def test_is_passed(self):
        """测试评估通过判断"""
        # 通过：无 critical 问题
        report_pass = QualityReport(
            chapter_number=1,
            overall_score=85,
            dimension_scores=[DimensionScore(dimension="情节", score=85)],
            consistency_scores=[DimensionScore(dimension="逻辑", score=85)],
            genre="悬疑/推理",
            genre_fit_score=85
        )
        assert self.quality_agent._is_passed(report_pass) is True
        
        # 不通过：有 critical 问题
        issues = [QualityIssue(severity="critical", description="因果断裂")]
        report_fail = QualityReport(
            chapter_number=1,
            overall_score=60,
            dimension_scores=[DimensionScore(dimension="情节", score=60, issues=issues)],
            consistency_scores=[],
            genre="悬疑/推理",
            genre_fit_score=60
        )
        assert self.quality_agent._is_passed(report_fail) is False

    def test_get_genre_criteria(self):
        """测试类型特征矩阵获取"""
        # 测试匹配的类型
        criteria = self.quality_agent._get_genre_criteria("悬疑/推理")
        assert criteria.genre == "悬疑/推理"
        assert "逻辑严密性" in criteria.criteria
        
        criteria = self.quality_agent._get_genre_criteria("言情")
        assert criteria.genre == "言情"
        assert "情感真实性" in criteria.criteria
        
        # 测试不匹配的类型（返回默认）
        criteria = self.quality_agent._get_genre_criteria("未知类型")
        assert criteria.genre == "悬疑/推理"


class TestQualityDataStructures:
    """质量评估数据结构测试"""

    def test_quality_issue(self):
        """测试 QualityIssue 数据结构"""
        issue = QualityIssue(
            severity="warning",
            description="测试问题",
            location="第1章",
            suggestion="修复建议",
            excerpt="问题文本"
        )
        assert issue.severity == "warning"
        assert issue.description == "测试问题"

    def test_dimension_score(self):
        """测试 DimensionScore 数据结构"""
        score = DimensionScore(
            dimension="情节",
            score=85,
            weight=0.2
        )
        assert score.dimension == "情节"
        assert score.score == 85
        assert score.weight == 0.2
        assert len(score.issues) == 0

    def test_genre_matrix(self):
        """测试类型特征矩阵配置"""
        assert len(GENRE_MATRIX) == 5
        genres = [gc.genre for gc in GENRE_MATRIX]
        assert "悬疑/推理" in genres
        assert "言情" in genres
        assert "科幻/奇幻" in genres
        assert "恐怖" in genres
        assert "网文" in genres

    def test_dimensions_config(self):
        """测试评估维度配置"""
        assert len(QUALITY_DIMENSIONS) == 6
        assert len(CONSISTENCY_LEVELS) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])