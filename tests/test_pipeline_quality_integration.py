"""
Pipeline 质量评估集成测试

验证流程顺序：
1. 写手写章 → 审计修订 → 质量评估+修订 → 因果链提取 → 摘要生成 → 保存

确保：
- QualityAgent 正确集成到 Pipeline
- 流程顺序符合设计文档要求
- PipelineResult 包含质量评估字段
"""
import pytest
from unittest.mock import Mock, MagicMock, call
from dataclasses import dataclass
from typing import List, Optional


class TestPipelineQualityIntegration:
    """Pipeline 质量评估集成测试"""

    def test_pipeline_with_quality_agent(self):
        """测试 Pipeline 集成 QualityAgent"""
        from core.pipeline import WritingPipeline, PipelineResult
        from core.agents import (
            ArchitectAgent, WriterAgent, AuditorAgent, ReviserAgent,
            SummaryAgent, QualityAgent, QualityReport
        )
        from core.narrative import ChapterOutlineSchema, BeatSchema
        from core.types.narrative import Character, CharacterNeed, CharacterWorldview, DramaticFunction
        
        # 创建模拟对象
        mock_sm = Mock()
        mock_sm.create_snapshot = Mock()
        mock_sm.read_truth_bundle = Mock(return_value="test context")
        mock_sm.read_truth = Mock(return_value="")
        mock_sm.read_world_state = Mock(return_value=Mock(
            threads=[],
            timeline=[],
            causal_chain=[],
            settings=Mock(genre="悬疑/推理"),
            current_chapter=0,
            dormant_threads=Mock(return_value=[]),
            get_thread=Mock(return_value=None)
        ))
        mock_sm.write_world_state = Mock()
        mock_sm.save_draft = Mock()
        mock_sm.save_final = Mock()
        mock_sm.add_causal_link = Mock()
        mock_sm.append_truth = Mock()
        mock_sm.update_current_state_md = Mock()
        mock_sm.update_thread_status_md = Mock()
        mock_sm.read_draft = Mock(return_value="")
        
        mock_architect = Mock(spec=ArchitectAgent)
        mock_architect.plan_chapter = Mock(return_value=Mock(
            core_conflict="测试冲突",
            hooks_to_advance=[],
            hooks_to_plant=[],
            emotional_journey={"start": "start", "end": "end"},
            chapter_end_hook="钩子",
            pace_notes="适中",
            pre_write_checklist=Mock(
                active_characters=["主角"],
                required_locations=["地点"],
                resources_in_play=[],
                hooks_status=[],
                risk_scan="无"
            )
        ))
        
        mock_writer = Mock(spec=WriterAgent)
        mock_writer.write_chapter = Mock(return_value=Mock(
            content="测试章节内容",
            settlement=Mock(
                resource_changes=[],
                new_hooks=[],
                resolved_hooks=[],
                relationship_changes=[],
                info_revealed=[],
                character_position_changes=[],
                emotional_changes=[]
            )
        ))
        
        mock_validator = Mock()
        mock_validator.validate = Mock(return_value=Mock(passed=True, issues=[]))
        
        mock_auditor = Mock(spec=AuditorAgent)
        mock_auditor.audit_chapter = Mock(return_value=Mock(
            passed=True,
            critical_count=0,
            warning_count=0,
            issues=[]
        ))
        
        mock_reviser = Mock(spec=ReviserAgent)
        mock_reviser.revise = Mock(return_value=Mock(content="修订后内容"))
        
        mock_engine = Mock()
        mock_engine.extract_causal_links = Mock(return_value=[])
        
        mock_summary = Mock(spec=SummaryAgent)
        mock_summary.generate_summary = Mock(return_value=Mock(
            chapter_number=1,
            title="测试章",
            summary="测试摘要",
            key_events=[],
            characters_appeared=[],
            state_changes=[],
            hook_updates=[],
            emotional_note="情感变化"
        ))
        mock_summary.format_for_truth_file = Mock(return_value="格式化摘要")
        
        # 关键：创建模拟的 QualityAgent
        mock_quality = Mock(spec=QualityAgent)
        mock_quality.evaluate_chapter = Mock(return_value=(
            "质量评估后内容",
            Mock(overall_score=85)
        ))
        
        protagonist = Character(
            id="protagonist",
            name="主角",
            need=CharacterNeed(external="外部目标", internal="内在渴望"),
            obstacles=[],
            worldview=CharacterWorldview(power="seeks", trust="trusting", coping="fight"),
            arc="positive",
            profile="测试角色",
            behavior_lock=[]
        )
        
        # 创建 Pipeline
        pipeline = WritingPipeline(
            state_manager=mock_sm,
            architect=mock_architect,
            writer=mock_writer,
            auditor=mock_auditor,
            reviser=mock_reviser,
            narrative_engine=mock_engine,
            summary_agent=mock_summary,
            validator=mock_validator,
            protagonist=protagonist,
            all_characters=[protagonist],
            quality_agent=mock_quality  # 集成 QualityAgent
        )
        
        # 创建章纲
        chapter_outline = ChapterOutlineSchema(
            chapter_number=1,
            title="测试章",
            summary="测试摘要",
            sequence_id="seq_1",
            beats=[BeatSchema(id="beat_1", description="测试节拍", dramatic_function=DramaticFunction.SETUP)],
            emotional_arc={"start": "开始", "end": "结束"},
            mandatory_tasks=["任务1"],
            target_words=1000
        )
        
        # 执行 Pipeline
        result = pipeline.run(chapter_outline, verbose=False)
        
        # 验证结果
        assert isinstance(result, PipelineResult)
        assert result.chapter_number == 1
        assert result.content == "质量评估后内容"
        assert result.quality_score == 85
        assert result.quality_report is not None
        
        # 验证流程顺序：质量评估在摘要生成之前，摘要生成在保存之前
        call_order = [c[0] for c in mock_sm.method_calls]
        
        # 检查方法调用顺序
        assert 'save_draft' in call_order
        assert 'save_final' in call_order
        assert 'append_truth' in call_order
        
        # save_final 应该在 append_truth（摘要写入）之后
        append_truth_idx = call_order.index('append_truth')
        save_final_idx = call_order.index('save_final')
        assert append_truth_idx < save_final_idx, "摘要生成应该在保存之前"

    def test_pipeline_without_quality_agent(self):
        """测试没有 QualityAgent 时 Pipeline 正常工作"""
        from core.pipeline import WritingPipeline, PipelineResult
        from core.agents import (
            ArchitectAgent, WriterAgent, AuditorAgent, ReviserAgent, SummaryAgent
        )
        from core.narrative import ChapterOutlineSchema, BeatSchema
        from core.types.narrative import Character, CharacterNeed, CharacterWorldview, DramaticFunction
        
        # 创建模拟对象
        mock_sm = Mock()
        mock_sm.create_snapshot = Mock()
        mock_sm.read_truth_bundle = Mock(return_value="test context")
        mock_sm.read_truth = Mock(return_value="")
        mock_sm.read_world_state = Mock(return_value=Mock(
            threads=[],
            timeline=[],
            causal_chain=[],
            settings=Mock(genre="悬疑/推理"),
            current_chapter=0,
            dormant_threads=Mock(return_value=[]),
            get_thread=Mock(return_value=None)
        ))
        mock_sm.write_world_state = Mock()
        mock_sm.save_draft = Mock()
        mock_sm.save_final = Mock()
        mock_sm.add_causal_link = Mock()
        mock_sm.append_truth = Mock()
        mock_sm.update_current_state_md = Mock()
        mock_sm.update_thread_status_md = Mock()
        
        mock_architect = Mock(spec=ArchitectAgent)
        mock_architect.plan_chapter = Mock(return_value=Mock(
            core_conflict="测试冲突",
            hooks_to_advance=[],
            hooks_to_plant=[],
            emotional_journey={"start": "start", "end": "end"},
            chapter_end_hook="钩子",
            pace_notes="适中",
            pre_write_checklist=Mock(
                active_characters=["主角"],
                required_locations=["地点"],
                resources_in_play=[],
                hooks_status=[],
                risk_scan="无"
            )
        ))
        
        mock_writer = Mock(spec=WriterAgent)
        mock_writer.write_chapter = Mock(return_value=Mock(
            content="测试章节内容",
            settlement=Mock(
                resource_changes=[],
                new_hooks=[],
                resolved_hooks=[],
                relationship_changes=[],
                info_revealed=[],
                character_position_changes=[],
                emotional_changes=[]
            )
        ))
        
        mock_validator = Mock()
        mock_validator.validate = Mock(return_value=Mock(passed=True, issues=[]))
        
        mock_auditor = Mock(spec=AuditorAgent)
        mock_auditor.audit_chapter = Mock(return_value=Mock(
            passed=True,
            critical_count=0,
            warning_count=0,
            issues=[]
        ))
        
        mock_reviser = Mock(spec=ReviserAgent)
        
        mock_engine = Mock()
        mock_engine.extract_causal_links = Mock(return_value=[])
        
        mock_summary = Mock(spec=SummaryAgent)
        mock_summary.generate_summary = Mock(return_value=Mock(
            chapter_number=1,
            title="测试章",
            summary="测试摘要",
            key_events=[],
            characters_appeared=[],
            state_changes=[],
            hook_updates=[],
            emotional_note="情感变化"
        ))
        mock_summary.format_for_truth_file = Mock(return_value="格式化摘要")
        
        protagonist = Character(
            id="protagonist",
            name="主角",
            need=CharacterNeed(external="外部目标", internal="内在渴望"),
            obstacles=[],
            worldview=CharacterWorldview(power="seeks", trust="trusting", coping="fight"),
            arc="positive",
            profile="测试角色",
            behavior_lock=[]
        )
        
        # 创建 Pipeline（不传入 quality_agent）
        pipeline = WritingPipeline(
            state_manager=mock_sm,
            architect=mock_architect,
            writer=mock_writer,
            auditor=mock_auditor,
            reviser=mock_reviser,
            narrative_engine=mock_engine,
            summary_agent=mock_summary,
            validator=mock_validator,
            protagonist=protagonist,
            all_characters=[protagonist],
            quality_agent=None  # 不传入 QualityAgent
        )
        
        # 创建章纲
        chapter_outline = ChapterOutlineSchema(
            chapter_number=1,
            title="测试章",
            summary="测试摘要",
            sequence_id="seq_1",
            beats=[BeatSchema(id="beat_1", description="测试节拍", dramatic_function=DramaticFunction.SETUP)],
            emotional_arc={"start": "开始", "end": "结束"},
            mandatory_tasks=["任务1"],
            target_words=1000
        )
        
        # 执行 Pipeline
        result = pipeline.run(chapter_outline, verbose=False)
        
        # 验证结果
        assert isinstance(result, PipelineResult)
        assert result.chapter_number == 1
        assert result.quality_score is None
        assert result.quality_report is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])