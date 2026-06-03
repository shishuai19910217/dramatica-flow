"""
写作管线核心模块

本模块实现了 Dramatica-Flow 的核心写作管线，将长篇小说创作流程工程化为可量化、可追踪的15步流程：

流程架构（优化后）：
    [快照备份] → [建筑师规划] → [写手写章] → [写后验证] → [审计→修订闭环] 
        → [质量评估+修订] → [因果链提取] → [摘要生成] → [保存最终稿] → [状态更新] → [时间轴记录] → [掉线预警]

核心特性：
    1. 多线叙事支持：根据线程权重动态调整字数分配
    2. 跨线程感知：建筑师/写手/审计员均可获得其他线程上下文
    3. 修订闭环：审计不通过自动触发修订，最多 MAX_REVISE_ROUNDS 轮
    4. 写后结算表：系统记录角色位置/情感/关系/伏笔/信息的变化
    5. 支线掉线预警：超过阈值章节未活跃的线程自动告警
    6. 质量评估体系：六个核心维度 + 六大连贯性层次的全面质量评估

修改记录：
    - AuditIssue 构造不再传 excerpt 到 location
    - 章后调用 update_current_state_md
    - 集成 SummaryAgent，写完生成摘要注入 chapter_summaries.md
    - WriterAgent 获得前情摘要上下文
    - _apply_settlement 完整处理位置/情感/关系变化
    - 新增 QualityAgent 集成，支持全面质量评估和自动修订
    - 流程优化：摘要生成在保存之前，确保状态完整性
"""
from __future__ import annotations

import uuid
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# Agent 层导入
from .agents import (
    ArchitectAgent, ArchitectBlueprint,
    WriterAgent, WriterOutput,
    AuditorAgent, AuditReport, AuditIssue,
    ReviserAgent, ReviseResult,
    SummaryAgent,
    QualityAgent, QualityReport,
)
# 叙事引擎导入
from .narrative import NarrativeEngine, ChapterOutlineSchema
# 状态管理导入
from .state import StateManager
# 类型定义导入
from .types.narrative import Character, NarrativeThread, TimelineEvent
from .types.state import (
    TruthFileKey, EmotionalSnapshot, CausalLink, AffectedDecision,
    Hook, HookType, HookStatus,
)
# 验证器导入
from .validators import PostWriteValidator


@dataclass
class PipelineResult:
    """
    写作管线执行结果数据结构
    
    用于封装单章写作完成后的所有关键输出信息，供上层调用者（CLI/Web）使用。
    
    Fields:
        chapter_number: 章节号
        content: 最终生成的章节正文
        audit_report: 审计报告（包含所有审计问题）
        validation_passed: 写后验证是否通过
        revision_rounds: 修订轮数（0-MAX_REVISE_ROUNDS）
        causal_links: 提取到的因果链数量
        word_count: 章节字数
        thread_id: 所属叙事线程ID
        pov_character_id: 视角角色ID
        dormancy_warnings: 支线掉线预警列表
        quality_score: 质量综合评分（0-100）
        quality_report: 质量评估报告
    """
    chapter_number: int
    content: str
    audit_report: AuditReport
    validation_passed: bool
    revision_rounds: int
    causal_links: int
    word_count: int
    # 多线叙事扩展字段
    thread_id: str = ""
    pov_character_id: str = ""
    dormancy_warnings: list[str] = field(default_factory=list)
    # 质量评估扩展字段
    quality_score: Optional[int] = None
    quality_report: Optional[QualityReport] = None


class WritingPipeline:
    """
    单章写作管线核心类
    
    实现完整的单章写作流程，协调多个 Agent 协同工作。
    
    管线流程详解（优化后）：
        1. 快照备份：保存当前世界状态，支持回滚
        2. 建筑师规划：分析章纲和世界状态，生成写作蓝图
        3. 写手写章：基于蓝图生成正文 + 写后结算表
        4. 写后验证：零 LLM 硬规则检测（字数、格式等）
        5. 审计修订：叙事质量审计，critical问题触发自动修订
        6. 质量评估+修订：六个核心维度 + 六大连贯性层次全面评估
        7. 因果链提取：从正文中提取因果关系链
        8. 摘要生成：生成章节摘要注入 chapter_summaries.md（最后处理环节）
        9. 保存最终稿：写入正式章节文件（最后保存步骤）
        10. 状态更新：将结算表应用到 world_state
        11. 时间轴记录：添加 TimelineEvent
        12. 掉线预警：检测超过阈值未活跃的支线
    
    多线程支持：
        - 根据章纲的 thread_id 解析视角角色和线程上下文
        - 跨线程感知：建筑师/写手/审计员均获得其他线程状态
        - 线程权重管理：根据线程 weight 调整字数分配
        - 支线掉线预警：章后检测并报告长时间未活跃的线程
    
    质量评估体系：
        - 六个核心维度：情节、人物、设定、语言、阅读体验、类型适配
        - 六大连贯性层次：时间、空间、逻辑、情绪、信息、风格
    """

    # 最大修订轮数，防止无限循环
    MAX_REVISE_ROUNDS = 2

    def __init__(
        self,
        state_manager: StateManager,
        architect: ArchitectAgent,
        writer: WriterAgent,
        auditor: AuditorAgent,
        reviser: ReviserAgent,
        narrative_engine: NarrativeEngine,
        summary_agent: SummaryAgent,
        validator: PostWriteValidator,
        protagonist: Character,
        all_characters: list[Character],
        quality_agent: Optional[QualityAgent] = None,
    ):
        """
        初始化写作管线
        
        Args:
            state_manager: 状态管理器，负责真相文件读写和世界状态维护
            architect: 建筑师 Agent，负责生成章节写作蓝图
            writer: 写手 Agent，负责生成章节正文
            auditor: 审计员 Agent，负责叙事质量审计
            reviser: 修订者 Agent，负责根据审计结果修订内容
            narrative_engine: 叙事引擎，负责因果链提取等核心叙事逻辑
            summary_agent: 摘要 Agent，负责生成章节摘要（最后处理环节）
            validator: 写后验证器，负责零 LLM 的硬规则检测
            protagonist: 主角角色对象
            all_characters: 所有角色列表
            quality_agent: 质量评估 Agent（可选，用于全面质量评估和修订）
        """
        self.sm = state_manager              # 状态管理器
        self.architect = architect            # 建筑师 Agent
        self.writer = writer                  # 写手 Agent
        self.auditor = auditor                # 审计员 Agent
        self.reviser = reviser                # 修订者 Agent
        self.engine = narrative_engine        # 叙事引擎
        self.summary_agent = summary_agent    # 摘要生成 Agent（最后处理环节）
        self.validator = validator            # 写后验证器
        self.protagonist = protagonist        # 主角
        self.all_characters = all_characters  # 所有角色列表
        self.quality_agent = quality_agent    # 质量评估 Agent（新增）

    def run(
        self,
        chapter_outline: ChapterOutlineSchema,
        verbose: bool = False,
    ) -> PipelineResult:
        """
        执行完整的单章写作管线
        
        Args:
            chapter_outline: 章纲 Schema，包含章节号、标题、节拍、目标字数等
            verbose: 是否输出详细日志
        
        Returns:
            PipelineResult: 管线执行结果，包含最终内容、审计报告等
        """
        ch = chapter_outline.chapter_number  # 当前章节号
        title = chapter_outline.title        # 当前章节标题

        # 内部日志函数，仅在 verbose 模式下输出
        def log(msg: str) -> None:
            if verbose:
                print(f"  [{ch}] {msg}")

        # ── 步骤1: 快照备份 ─────────────────────────────────────────────────────
        # 在修改状态前保存快照，支持失败时回滚
        log("创建快照...")
        self.sm.create_snapshot(ch - 1)  # 保存到上一章节快照

        # ── 步骤2: 读取上下文 ──────────────────────────────────────────────────
        # 读取当前世界状态和角色矩阵作为上下文
        world_context = self.sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE,      # 当前状态
            TruthFileKey.CHARACTER_MATRIX,   # 角色信息边界矩阵
        ])
        # 读取待处理伏笔
        pending_hooks = self.sm.read_truth(TruthFileKey.PENDING_HOOKS)
        # 读取因果链和情感弧线（写手需要看到完整的叙事脉络）
        causal_chain = self.sm.read_truth(TruthFileKey.CAUSAL_CHAIN)
        emotional_arcs = self.sm.read_truth(TruthFileKey.EMOTIONAL_ARCS)
        # 读取前情摘要（最近3章），帮助保持叙事连贯性
        full_summaries = self.sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES)
        prior_summaries = _extract_recent_summaries(full_summaries, n=3)

        # ── 步骤3: 多线程上下文解析 ────────────────────────────────────────────
        ws = self.sm.read_world_state()
        # 获取当前线程ID，默认为主线程
        thread_id = getattr(chapter_outline, "thread_id", "thread_main") or "thread_main"
        # 获取视角角色ID
        pov_char_id = getattr(chapter_outline, "pov_character_id", "") or ""

        # 解析视角角色对象
        pov_character: Optional[Character] = None
        if pov_char_id:
            for c in self.all_characters:
                if c.id == pov_char_id:
                    pov_character = c
                    break
        # 如果章纲未指定视角角色，回退到线程配置的视角角色
        if not pov_character and thread_id:
            thread = ws.get_thread(thread_id)
            if thread and thread.pov_character_id:
                for c in self.all_characters:
                    if c.id == thread.pov_character_id:
                        pov_character = c
                        break

        # 构建跨线程上下文（供建筑师和写手了解其他线程状态）
        thread_context = self._build_thread_context(ws, thread_id, ch)

        # 根据线程权重调整目标字数（支线权重较低，字数相应减少）
        effective_thread = ws.get_thread(thread_id) if thread_id else None
        thread_weight = effective_thread.weight if effective_thread else 1.0
        adjusted_target_words = max(
            int(chapter_outline.target_words * thread_weight),  # 按权重计算
            int(chapter_outline.target_words * 0.5),           # 最低不低于50%
        )

        if verbose and effective_thread:
            log(f"线程：{effective_thread.name}（{thread_id}），权重={thread_weight}，调整字数={adjusted_target_words}")

        # ── 步骤4: 建筑师规划 ─────────────────────────────────────────────────
        # 建筑师分析章纲和世界状态，生成详细的写作蓝图
        log("建筑师规划...")
        blueprint = self.architect.plan_chapter(
            chapter_outline=chapter_outline,
            world_context=world_context,
            pending_hooks=pending_hooks,
            prior_chapter_summary=prior_summaries,
            pov_character=pov_character,
            thread_context=thread_context,
        )

        # ── 步骤 5: 写手写章 ───────────────────────────────────────────────────
        # 写手根据蓝图和节拍生成正文，同时输出写后结算表
        log("写手写章...")
        scene_summaries = _format_beats(chapter_outline)  # 格式化节拍为写手可读格式
        
        # 读取前一章最后 800 字，用于开头衔接
        prev_chapter_tail = ""
        if ch > 1:
            prev_final = self.sm.read_final(ch - 1) or self.sm.read_draft(ch - 1)
            if prev_final:
                prev_chapter_tail = prev_final[-800:]
        log(f"前一章尾部：{prev_chapter_tail}")
        writer_output = self.writer.write_chapter(
            scene_summaries=scene_summaries,
            blueprint=blueprint,
            protagonist=self.protagonist,
            world_context=world_context,
            chapter_number=ch,
            target_words=adjusted_target_words,
            prior_summaries=prior_summaries,
            prev_chapter_tail=prev_chapter_tail,
            chapter_title=title,
            pov_character=pov_character,
            thread_context=thread_context,
            pending_hooks=pending_hooks,
            causal_chain=causal_chain,
            emotional_arcs=emotional_arcs,
            writing_notes=chapter_outline.writing_notes,
            pov_instruction=chapter_outline.pov,
        )
        # 保存草稿（用于回滚和审计）
        self.sm.save_draft(ch, writer_output.content)
        log(f"草稿 {len(writer_output.content)} 字")

        # ── 步骤6: 写后验证（零 LLM） ─────────────────────────────────────────
        # 使用硬规则验证，不调用 LLM，快速检测明显问题
        log("写后验证...")
        val_result = self.validator.validate(
            writer_output.content,
            target_words=adjusted_target_words,
        )
        current_content = writer_output.content

        # 如果验证未通过，收集 error 级问题并进行 spot-fix
        if not val_result.passed:
            error_issues = [
                AuditIssue(
                    dimension="写后验证",
                    severity="critical",
                    description=i.description,
                    location=i.excerpt,
                )
                for i in val_result.issues
                if i.severity == "error"
            ]
            log(f"验证未通过（{len(error_issues)} 个 error），spot-fix...")
            fix_result = self.reviser.revise(current_content, error_issues, mode="spot-fix")
            current_content = fix_result.content

        # ── 步骤7: 审计 → 修订闭环 ────────────────────────────────────────────
        # 审计员进行叙事质量审计（temperature=0 确保客观）
        log("审计员审计...")
        audit_truth_ctx = self.sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE,
            TruthFileKey.CHARACTER_MATRIX,
            TruthFileKey.PENDING_HOOKS,
            TruthFileKey.EMOTIONAL_ARCS,
            TruthFileKey.CAUSAL_CHAIN,
        ])

        # 构建跨线程审计上下文（检测跨线程冲突）
        cross_thread_audit_ctx = self._build_cross_thread_audit_context(ws, thread_id, ch)

        audit_report = self.auditor.audit_chapter(
            chapter_content=current_content,
            chapter_number=ch,
            blueprint=blueprint,
            truth_context=audit_truth_ctx,
            settlement=writer_output.settlement,
            cross_thread_context=cross_thread_audit_ctx,
        )

        # 修订闭环：审计不通过时自动触发修订，最多 MAX_REVISE_ROUNDS 轮
        revision_rounds = 0
        while not audit_report.passed and revision_rounds < self.MAX_REVISE_ROUNDS:
            log(f"修订第 {revision_rounds + 1} 轮（{audit_report.critical_count} critical）...")
            revise_result = self.reviser.revise(
                current_content,
                audit_report.issues,
                mode="spot-fix",
            )
            current_content = revise_result.content
            revision_rounds += 1

            # 修订后重新审计
            audit_report = self.auditor.audit_chapter(
                chapter_content=current_content,
                chapter_number=ch,
                blueprint=blueprint,
                truth_context=audit_truth_ctx,
                settlement=writer_output.settlement,
                cross_thread_context=cross_thread_audit_ctx,
            )

        # ── 步骤8: 质量评估+修订（新增）─────────────────────────────────────────
        # 六个核心维度 + 六大连贯性层次全面评估，自动修订
        quality_report: Optional[QualityReport] = None
        quality_score: Optional[int] = None
        if self.quality_agent:
            log("质量评估...")
            prev_content = ""
            if ch > 1:
                prev_content = self.sm.read_draft(ch - 1) or ""
            genre = getattr(ws.settings, "genre", "general")
            current_content, quality_report = self.quality_agent.evaluate_chapter(
                chapter_content=current_content,
                chapter_number=ch,
                genre=genre,
                blueprint=blueprint,
                truth_context=audit_truth_ctx,
                settlement=writer_output.settlement,
                prev_chapter_content=prev_content,
                cross_thread_context=cross_thread_audit_ctx,
                audit_report=audit_report,
                auto_revise=True,
            )
            quality_score = quality_report.overall_score
            log(f"质量评分：{quality_score}")

        # ── 步骤9: 因果链提取（前置到摘要生成之前）───────────────────────────────
        # 从正文中提取因果关系链，构建叙事逻辑图谱
        log("提取因果链...")
        causal_schemas = self.engine.extract_causal_links(
            chapter_content=current_content,
            chapter_number=ch,
            characters=self.all_characters,
        )
        # 将提取的因果链保存到状态管理器
        for link_schema in causal_schemas:
            cl = CausalLink(
                id=link_schema.id,
                chapter=link_schema.chapter,
                cause=link_schema.cause,
                event=link_schema.event,
                consequence=link_schema.consequence,
                affected_decisions=[
                    AffectedDecision(d.character_id, d.decision)
                    for d in link_schema.affected_decisions
                ],
                triggered_events=link_schema.triggered_events,
                thread_id=thread_id,
            )
            self.sm.add_causal_link(cl)
        log(f"因果链：{len(causal_schemas)} 条")

        # ── 步骤10: 生成章节摘要（最后处理环节，前置到保存之前）──────────────────
        # 生成章节摘要并注入 chapter_summaries.md，供后续章节参考
        log("生成章节摘要...")
        import re
        try:
            summary = self.summary_agent.generate_summary(
                chapter_content=current_content,
                chapter_number=ch,
                chapter_title=title,
                settlement=writer_output.settlement,
            )
            summary_md = self.summary_agent.format_for_truth_file(summary)
        except Exception as e:
            # 摘要生成失败不阻塞主线程，使用 fallback
            summary_md = (
                f"\n## 第 {ch} 章《{title}》\n"
                f"{chapter_outline.summary}\n"
                f"- 审计：{'通过' if audit_report.passed else '未通过'}"
                f"，修订 {revision_rounds} 轮\n---\n"
            )
            log(f"摘要生成失败（{e}），使用 fallback")
        
        # 检查是否已存在该章节摘要，存在则替换，否则追加
        full_summaries = self.sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES) or ""
        chapter_pattern = rf"\n## 第 {ch} 章.*?(?=\n## 第|$)"
        if re.search(chapter_pattern, full_summaries, re.DOTALL):
            full_summaries = re.sub(chapter_pattern, summary_md, full_summaries, flags=re.DOTALL)
        else:
            full_summaries = f"{full_summaries}{summary_md}"
        self.sm.write_truth(TruthFileKey.CHAPTER_SUMMARIES, full_summaries.strip())

        # ── 步骤11: 保存最终稿（最后保存步骤）───────────────────────────────────
        self.sm.save_final(ch, current_content)
        log(f"最终稿保存（{len(current_content)} 字）")

        # ── 步骤12: 应用结算表到世界状态 ───────────────────────────────────────
        # 将写后结算表中的变化应用到世界状态
        log("应用结算表...")
        self._apply_settlement(ch, writer_output, blueprint)

        # ── 步骤13: 记录时间轴事件 + 更新线程状态 ─────────────────────────────
        log("更新时间轴和线程状态...")
        self._record_timeline_events(ch, writer_output, blueprint, thread_id, ws)

        # ── 步骤14: 更新当前章节 + current_state.md ───────────────────────────
        # 刷新世界状态并更新状态文档
        ws = self.sm.read_world_state()
        ws.current_chapter = ch
        self.sm.write_world_state(ws)
        self.sm.update_current_state_md()
        log("current_state.md 已更新")

        # ── 步骤15: 更新线程状态 + 掉线预警 ───────────────────────────────────
        # 检测超过阈值章节未活跃的支线线程并告警
        dormancy_warnings: list[str] = []
        if ws.threads:
            self.sm.update_thread_status_md()
            # 检测阈值为5章未活跃的线程
            dormant = ws.dormant_threads(ch, threshold=5)
            for t in dormant:
                gap = ch - t.last_active_chapter
                dormancy_warnings.append(f"{t.name}（{t.id}）：已 {gap} 章未活跃")
            if dormancy_warnings and verbose:
                for w in dormancy_warnings:
                    print(f"  [预警] 支线掉线：{w}")

        # 返回管线执行结果
        return PipelineResult(
            chapter_number=ch,
            content=current_content,
            audit_report=audit_report,
            validation_passed=val_result.passed,
            revision_rounds=revision_rounds,
            causal_links=len(causal_schemas),
            word_count=len(current_content),
            thread_id=thread_id,
            pov_character_id=pov_character.id if pov_character else "",
            dormancy_warnings=dormancy_warnings,
            quality_score=quality_score,
            quality_report=quality_report,
        )

    # ── 多线程辅助方法 ────────────────────────────────────────────────────────

    def _build_thread_context(
        self, ws, current_thread_id: str, chapter: int,
    ) -> str:
        """
        构建跨线程感知上下文（供建筑师和写手使用）
        
        让当前线程的写作 Agent 了解其他活跃线程的状态，避免叙事冲突和重复。
        
        Args:
            ws: 世界状态对象
            current_thread_id: 当前线程ID
            chapter: 当前章节号
        
        Returns:
            跨线程上下文字符串，包含其他线程的基本信息、当前悬念和目标
        """
        if not ws.threads:
            return ""

        lines = []
        for t in ws.get_active_threads():
            # 跳过当前线程
            if t.id == current_thread_id:
                continue
            # 线程基本信息：名称、ID、上次活跃章节、期待感指数
            lines.append(
                f"- {t.name}（{t.id}）：上次活跃 Ch.{t.last_active_chapter}，"
                f"期待感 {t.hook_score}/100"
            )
            # 当前悬念钩子
            if t.end_hook:
                lines.append(f"  当前悬念：{t.end_hook}")
            # 线程目标
            if t.goal:
                lines.append(f"  目标：{t.goal}")

        if not lines:
            return ""
        return "\n".join(lines)

    def _build_cross_thread_audit_context(
        self, ws, current_thread_id: str, chapter: int,
    ) -> str:
        """
        构建跨线程审计上下文（供审计员检测跨线程冲突）
        
        提供详细的跨线程事件和因果链信息，帮助审计员发现线程间的逻辑冲突。
        
        Args:
            ws: 世界状态对象
            current_thread_id: 当前线程ID
            chapter: 当前章节号
        
        Returns:
            跨线程审计上下文字符串，包含其他线程的近期事件和跨线程因果链
        """
        parts = []

        # 其他线程的近期时间轴事件（最近5个）
        for t in ws.threads:
            if t.id == current_thread_id:
                continue
            thread_events = [e for e in ws.timeline 
                           if e.thread_id == t.id and e.chapter <= chapter]
            if thread_events:
                parts.append(f"### {t.name}（{t.id}）近期事件\n")
                for te in thread_events[-5:]:
                    parts.append(
                        f"- Ch.{te.chapter} {te.physical_time}：{te.character_id} 在 {te.location_id} "
                        f"做了 {te.action[:40]}"  # 截断到40字
                    )
                parts.append("")

        # 跨线程因果链（其他线程影响当前线程的事件）
        cross_links = [cl for cl in ws.causal_chain
                       if cl.source_thread_id and cl.source_thread_id != cl.thread_id
                       and cl.thread_id == current_thread_id]
        if cross_links:
            parts.append("### 受其他线程影响的因果链\n")
            for cl in cross_links[-5:]:
                parts.append(f"- Ch.{cl.chapter}：{cl.event}（因：来自 {cl.source_thread_id} 的 {cl.cause}）")
            parts.append("")

        return "\n".join(parts)

    def _record_timeline_events(
        self,
        chapter: int,
        writer_output: WriterOutput,
        blueprint: ArchitectBlueprint,
        thread_id: str,
        ws,
    ) -> None:
        """
        根据结算表和蓝图记录时间轴事件
        
        从写后结算表中提取关键事件，构建全局时间轴，用于跨线程协调和回溯。
        
        Args:
            chapter: 当前章节号
            writer_output: 写手输出，包含结算表
            blueprint: 建筑师蓝图
            thread_id: 当前线程ID
            ws: 世界状态对象
        """
        # 时间顺序值，基于章节号 + 计数器，保证事件有序
        time_order = float(chapter)
        counter = 0

        # 获取下一个时间顺序值
        def _next_order():
            nonlocal counter
            counter += 1
            return time_order + counter * 0.1

        # 1. 从角色位置变化中提取时间轴事件
        for change in writer_output.settlement.character_position_changes:
            char_id = change.get("character_id", "")
            loc_id = change.get("location_id", "")
            if char_id and loc_id:
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    location_id=loc_id,
                    action=f"移动到 {loc_id}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 2. 从情感变化中提取关键情感转折事件（仅记录强度>=7的）
        for ec in writer_output.settlement.emotional_changes:
            char_id = ec.get("character_id", "")
            intensity = int(ec.get("intensity", 0))
            emotion = ec.get("emotion", "")
            trigger = ec.get("trigger", "")
            if char_id and intensity >= 7:  # 高强度情感变化才记录
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    action=f"情感转折：{emotion}（强度{intensity}/10），触发：{trigger[:30]}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 3. 从信息揭示中提取事件
        for info in writer_output.settlement.info_revealed:
            char_id = info.get("character_id", "")
            info_key = info.get("info_key", "")
            if char_id and info_key:
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    action=f"得知：{info_key}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 4. 从核心冲突中提取主线事件
        if blueprint.core_conflict:
            pov_id = blueprint.pov_character_id or self.protagonist.id
            event = TimelineEvent(
                id=f"te_{uuid.uuid4().hex[:8]}",
                chapter=chapter,
                physical_time="",
                time_order=_next_order(),
                character_id=pov_id,
                action=blueprint.core_conflict[:60],  # 截断到60字
                thread_id=thread_id,
            )
            self.sm.add_timeline_event(event)

    # ── 结算表应用 ────────────────────────────────────────────────────────────

    def _apply_settlement(
        self,
        chapter: int,
        writer_output: WriterOutput,
        blueprint: ArchitectBlueprint,
    ) -> None:
        """
        应用写后结算表到世界状态
        
        将写手输出的结算表中的所有变化（位置、情感、关系、伏笔、信息）应用到
        世界状态和真相文件中，确保叙事状态的一致性和可追踪性。
        
        Args:
            chapter: 当前章节号
            writer_output: 写手输出，包含结算表
            blueprint: 建筑师蓝图
        """
        s = writer_output.settlement  # 写后结算表

        # 1. 角色位置变化
        for change in s.character_position_changes:
            char_id = change.get("character_id", "")
            loc_id = change.get("location_id", "")
            if char_id and loc_id:
                self.sm.move_character(char_id, loc_id)

        # 2. 情感变化
        for ec in s.emotional_changes:
            char_id = ec.get("character_id", "")
            if not char_id:
                continue
            # 创建情感快照
            snap = EmotionalSnapshot(
                character_id=char_id,
                emotion=ec.get("emotion", "未知"),
                intensity=int(ec.get("intensity", 5)),
                chapter=chapter,
                trigger=ec.get("trigger", ""),
            )
            self.sm.record_emotion(snap)
            # 更新 emotional_arcs.md
            self.sm.append_truth(
                TruthFileKey.EMOTIONAL_ARCS,
                f"- Ch.{chapter} [{char_id}] {snap.emotion}（{snap.intensity}/10）：{snap.trigger}\n",
            )

        # 3. 关系变化（格式：「角色A-角色B：delta，原因」）
        # 示例："林尘-慕雪：+20，慕雪开始动摇"
        for rel_str in s.relationship_changes:
            try:
                parts = rel_str.split("：", 1)  # 按中文冒号分割
                if len(parts) == 2:
                    chars_part = parts[0].strip()
                    detail = parts[1].strip()
                    chars = chars_part.split("-", 1)  # 按连字符分割两个角色
                    if len(chars) == 2:
                        char_a = chars[0].strip()
                        char_b = chars[1].strip()
                        # 从 detail 中提取变化量（如 +20 或 -10）
                        m = re.search(r'([+-]\d+)', detail)
                        delta = int(m.group(1)) if m else 0
                        # 提取原因（移除数字部分）
                        reason = re.sub(r'[+-]\d+[，,]?\s*', '', detail).strip()
                        # 更新关系
                        self.sm.update_relationship(char_a, char_b, delta, chapter, reason)
            except Exception:
                pass  # 关系变化解析失败静默跳过

        # 4. 新开伏笔（来自写手结算表）
        for hook_desc in s.new_hooks:
            hook = Hook(
                id=f"hook_{uuid.uuid4().hex[:8]}",
                type=HookType.FORESHADOW,
                description=hook_desc,
                planted_in_chapter=chapter,
                expected_resolution_range=(chapter + 3, chapter + 25),  # 预期回收范围
                status=HookStatus.OPEN,
            )
            self.sm.open_hook(hook)

        # 5. 建筑师计划埋下的伏笔（来自蓝图）
        for hook_desc in blueprint.hooks_to_plant:
            if hook_desc and hook_desc not in s.new_hooks:  # 避免重复
                hook = Hook(
                    id=f"hook_{uuid.uuid4().hex[:8]}",
                    type=HookType.FORESHADOW,
                    description=hook_desc,
                    planted_in_chapter=chapter,
                    expected_resolution_range=(chapter + 5, chapter + 30),  # 稍长的回收周期
                    status=HookStatus.OPEN,
                )
                self.sm.open_hook(hook)

        # 6. 回收伏笔（标记为已解决）
        for hook_id in s.resolved_hooks:
            self.sm.resolve_hook(hook_id, chapter)

        # 7. 信息揭示（角色得知新信息）
        for info in s.info_revealed:
            char_id = info.get("character_id", "")
            info_key = info.get("info_key", "")
            content = info.get("content", "")
            if char_id and info_key:
                # 更新信息边界
                self.sm.learn_info(char_id, info_key, content, chapter, "witnessed")
                # 更新 character_matrix.md
                self.sm.append_truth(
                    TruthFileKey.CHARACTER_MATRIX,
                    f"\n- Ch.{chapter} [{char_id}] 得知：{info_key} — {content}\n",
                )

        # 8. 资源变化（附加记录到当前状态）
        if s.resource_changes:
            changes_str = "；".join(s.resource_changes)
            self.sm.append_truth(
                TruthFileKey.CURRENT_STATE,
                f"\n### Ch.{chapter} 资源变化\n{changes_str}\n",
            )


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _format_beats(chapter_outline: ChapterOutlineSchema) -> str:
    """
    将章纲节拍格式化为写手可读的场景序列
    
    将结构化的节拍数据转换为自然语言描述，便于写手理解和执行。
    
    Args:
        chapter_outline: 章纲 Schema
    
    Returns:
        格式化后的节拍字符串
    """
    lines = []
    for i, b in enumerate(chapter_outline.beats):
        fn_label = f"【{b.dramatic_function.value}】"
        line = f"节拍{i+1}{fn_label}：{b.description}"
        if b.emotional_target:
            line += f"（情感目标：{b.emotional_target}）"
        if b.target_words:
            line += f"（约 {b.target_words} 字）"
        lines.append(line)
        if b.detail:
            lines.append(f"  写作指导：{b.detail}")
    return "\n".join(lines) if lines else "（无节拍信息，根据章节摘要自由发挥）"


def _extract_recent_summaries(full_summaries: str, n: int = 3) -> str:
    """
    从 chapter_summaries.md 中提取最近 n 章的摘要
    
    用于构建前情摘要上下文，帮助保持叙事连贯性。
    
    Args:
        full_summaries: chapter_summaries.md 的完整内容
        n: 提取最近几章的摘要，默认为3
    
    Returns:
        最近 n 章的摘要字符串
    """
    if not full_summaries.strip():
        return ""
    # 按 "## 第X章" 正则模式分割
    sections = re.split(r'\n(?=## 第\d+章)', full_summaries)
    # 筛选以章节标题开头的部分
    recent = [s for s in sections if s.strip().startswith("## 第")]
    if not recent:
        return ""
    # 返回最近 n 章
    return "\n".join(recent[-n:])