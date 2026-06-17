"""
Web UI 后端
FastAPI 提供 REST API，供前端 HTML 驱动完整创作流程
启动：uvicorn core.server:app --reload --port 8766
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import subprocess
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

# ── 依赖检查（在 import FastAPI 之前，给用户清晰的提示） ─────────────────────
_MISSING = []
try:
    from pydantic import BaseModel, Field
except ImportError:
    _MISSING.append("pydantic")
try:
    from fastapi import FastAPI, HTTPException, Form, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse
except ImportError:
    _MISSING.append("fastapi")
try:
    import python_multipart  # noqa: F401  — FastAPI Form 上传需要
except ImportError:
    _MISSING.append("python-multipart")
try:
    import uvicorn  # noqa: F401
except ImportError:
    _MISSING.append("uvicorn")

if _MISSING:
    import sys
    print("=" * 60)
    print("  [ERROR] Missing dependencies:")
    for m in _MISSING:
        print(f"    - {m}")
    print()
    print("  Run to install:")
    print(f"    pip install {' '.join(_MISSING)}")
    print()
    print("  Or re-run install.bat / install.sh")
    print("=" * 60)
    sys.exit(1)
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', stream=sys.stdout)

app = FastAPI(title="Dramatica-Flow API", version="0.4.0")

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logging.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    logging.info(f"<-- {request.method} {request.url.path} {response.status_code}")
    return response

WEB_UI_PATH = Path(__file__).resolve().parent.parent / "dramatica_flow_web_ui.html"
TIMELINE_UI_PATH = Path(__file__).resolve().parent.parent / "dramatica_flow_timeline.html"


@app.get("/")
def serve_index():
    return FileResponse(str(WEB_UI_PATH))


@app.get("/timeline")
def serve_timeline():
    return FileResponse(str(TIMELINE_UI_PATH))


@app.get("/templates/{filename}")
def serve_template(filename: str):
    """提供模板文件下载（如 novel_extract_prompt.md）"""
    filepath = TEMPLATES_DIR / filename
    # 只允许访问特定安全文件
    allowed = {"novel_extract_prompt.md", "outline_import_template.md"}
    if filename not in allowed or not filepath.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(str(filepath), media_type="text/markdown; charset=utf-8")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 数据规范化工具 ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = PROJECT_ROOT / "books"

# dramatic_function 枚举值映射（兼容 AI 输出的各种写法）
_DF_MAP = {
    "setup": "setup", "establish": "setup", "exposition": "setup", "introduction": "setup",
    "inciting": "inciting", "inciting_incident": "inciting", "inciting-incident": "inciting",
    "turning": "turning", "turning_point": "turning", "turning-point": "turning",
    "progressive complication": "turning", "complication": "turning",
    "midpoint": "midpoint", "mid_point": "midpoint", "mid-point": "midpoint",
    "crisis": "crisis", "dark night": "crisis", "all is lost": "crisis", "lowest point": "crisis",
    "climax": "climax", "climax_build": "climax", "showdown": "climax", "confrontation": "climax",
    "reveal": "reveal", "revelation": "reveal", "discovery": "reveal",
    "decision": "decision", "choice": "decision", "commitment": "decision",
    "consequence": "consequence", "resolution": "consequence", "ending": "consequence", "denouement": "consequence", "new_world": "consequence",
    "transition": "transition", "bridge": "transition", "interlude": "transition",
}


def _normalize_outline(raw: dict, sm) -> dict:
    """规范化大纲 JSON，补缺字段 + 修正枚举值，使其符合 StoryOutlineSchema"""
    # 补顶层字段
    if "id" not in raw:
        raw["id"] = sm.book_id + "_outline"
    if "genre" not in raw:
        try:
            cfg = sm.read_config()
            raw["genre"] = cfg.get("genre", "玄幻")
        except Exception:
            raw["genre"] = "玄幻"

    # 已知应该是整数的字段（AI 可能返回浮点数）
    INT_FIELDS = {"number", "act", "estimated_scenes", "chapter_number", "target_words"}

    # 规范化每个序列
    for i, seq in enumerate(raw.get("sequences", [])):
        if "id" not in seq:
            seq["id"] = f"seq_{str(i+1).zfill(3)}"
        # 修正 dramatic_function
        df = seq.get("dramatic_function", "setup")
        seq["dramatic_function"] = _DF_MAP.get(df, df)
        # 保留 narrative_goal（必须字段）
        if "narrative_goal" not in seq:
            seq["narrative_goal"] = seq.get("summary", "")
        # 修复 AI 返回的浮点数（如 0.5 → 0, 5.0 → 5）
        for key in INT_FIELDS:
            if key in seq and isinstance(seq[key], float):
                seq[key] = int(seq[key])
        # estimated_scenes 至少为 1，不能是 0 或负数
        if seq.get("estimated_scenes", 0) < 1:
            seq["estimated_scenes"] = 1

    # 回写到文件
    outline_path = sm.state_dir / "outline.json"
    outline_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    return raw



ENV_PATH = PROJECT_ROOT / ".env"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ── 数据转换工具 ──────────────────────────────────────────────────────────────

def _dc_to_dict(obj):
    """递归将 dataclass 转为 dict，处理 enum 等"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dc_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dc_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        return obj.value
    return obj


def _sm(book_id: str):
    from core.state import StateManager
    return StateManager(PROJECT_ROOT, book_id)


def _load_env():
    """加载 .env 到 os.environ"""
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)


def _create_llm(temperature: float | None = None, model_env: str = "DEEPSEEK_MODEL", max_tokens: int | None = None):
    """创建 LLM 实例（支持 deepseek / ollama / openai / zhipu / moonshot / qwen / custom）"""
    from core.llm import LLMConfig, create_provider
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    temp = temperature if temperature is not None else float(os.environ.get("DEFAULT_TEMPERATURE", "0.7"))
    if max_tokens is None:
        max_tokens = int(os.environ.get("MAX_TOKENS", "0"))

    if provider == "ollama":
        cfg = LLMConfig(
            api_key="ollama",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
            temperature=temp,
            max_tokens=max_tokens,
        )
        return create_provider(cfg)

    # 通用 OpenAI 兼容模式（deepseek / openai / zhipu / moonshot / qwen / custom 都走这里）
    env_prefix = provider.upper() + "_"  # 如 ZHIPU_, MOONSHOT_, CUSTOM_
    
    # 获取 API Key
    key = os.environ.get(f"{env_prefix}API_KEY", "")
    if not key:
        # custom provider 不回退到 DEEPSEEK_API_KEY
        if provider == "custom":
            raise HTTPException(400, f"请先配置 {provider} 的 API Key")
        key = os.environ.get("DEEPSEEK_API_KEY", "")
    
    if not key:
        raise HTTPException(400, f"请先配置 {provider} 的 API Key")
    
    # 获取 Base URL
    base_url = os.environ.get(f"{env_prefix}BASE_URL", "")
    if not base_url:
        # custom provider 不回退到 DEEPSEEK_BASE_URL
        if provider != "custom":
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    
    if not base_url:
        raise HTTPException(400, f"请先配置 {provider} 的 BASE_URL")
    
    # 获取模型（优先使用当前 provider 的模型配置，如 CUSTOM_MODEL）
    model = os.environ.get(f"{env_prefix}MODEL", "")
    if not model:  # 如果当前 provider 没有配置，使用指定的 model_env（如 AUDITOR_MODEL）
        model = os.environ.get(model_env, "")
        if not model and provider != "custom":
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    
    if not model:
        raise HTTPException(400, f"请先配置模型（{env_prefix}MODEL 或 {model_env}）")
    
    cfg = LLMConfig(api_key=key, base_url=base_url, model=model, temperature=temp, max_tokens=max_tokens)
    return create_provider(cfg)


# ── 请求模型 ──────────────────────────────────────────────────────────────────

class CreateBookReq(BaseModel):
    title: str
    genre: str = "玄幻"
    chapters: int = 90
    words: int = 4000
    forbidden: str = ""
    style_guide: str = ""
    use_predefined_events: bool = True  # 是否使用预定义事件类型词汇库

class SaveSettingsReq(BaseModel):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434/v1"
    default_temperature: str = "0.7"
    max_tokens: str = "8192"
    auditor_model: str = ""
    # 各 Agent 模型配置
    architect_model: str = ""
    writer_model: str = ""
    reviser_model: str = ""
    # LLM 高级配置
    llm_timeout: str = "300"
    llm_max_retries: str = "3"
    llm_retry_delay: str = "5"
    # 新增：自定义提供商配置
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""

class SaveSetupReq(BaseModel):
    file_type: str  # "characters" / "world" / "events"
    content: str    # JSON string

class AiGenerateSetupReq(BaseModel):
    genre: str
    book_title: str
    idea: str = ""
    style: str = "standard"  # standard / detailed / minimalist

class SaveOutlineReq(BaseModel):
    outline: dict  # 完整大纲 JSON

class SaveChapterOutlinesReq(BaseModel):
    outlines: list  # 章纲列表

class UpdateBookConfigReq(BaseModel):
    title: str | None = None
    genre: str | None = None
    style_guide: str = ""
    forbidden: str = ""
    protagonist_id: str = ""
    target_chapters: int | None = None
    target_words_per_chapter: int | None = None

class AiGenerateOutlineReq(BaseModel):
    idea: str = ""  # 用户自定义想法（可选）

class AiContinueOutlineReq(BaseModel):
    extra_sequences: int = 2  # 要追加的序列数量
    idea: str = ""

class ThreeLayerAuditReq(BaseModel):
    chapter: int
    mode: Literal["language", "structure", "drama", "full"] = "full"


class ExtractFromNovelReq(BaseModel):
    text: str  # 小说文本（可上传文件内容或粘贴文本）
    genre: str = "玄幻"  # 题材（辅助理解）


@app.post("/api/books/{book_id}/upload-novel")
async def upload_novel(book_id: str, text: str = Form(...), genre: str = Form("玄幻")):
    """上传本地小说文件进行导入（支持 .txt .md 格式），自动提取角色和世界设定"""
    from fastapi import Form as FormData
    # 调用现有的 extract-from-novel 逻辑
    req = ExtractFromNovelReq(text=text, genre=genre)
    return await extract_from_novel(book_id, req)


@app.post("/api/books/{book_id}/import-chapters")
async def import_chapters(book_id: str, text: str = Form(...), start_chapter: int = Form(1)):
    """将上传的小说文本按章节分割导入为已有章节，用于续写已有小说"""
    sm = _sm(book_id)
    chapters = re.split(r'第[零一二三四五六七八九十百千万\d]+[章节回]', text)
    chapter_titles = re.findall(r'(第[零一二三四五六七八九十百千万\d]+[章节回].*?)[\n\r]', text)
    
    imported = 0
    ch_num = start_chapter
    for i, content in enumerate(chapters):
        content = content.strip()
        if not content or len(content) < 50:
            continue
        title = chapter_titles[i] if i < len(chapter_titles) else f"第{ch_num}章"
        # 保存为最终稿
        sm.save_draft(ch_num, content)
        draft_path = sm.chapter_dir / f"ch{ch_num:04d}_draft.md"
        final_path = sm.chapter_dir / f"ch{ch_num:04d}_final.md"
        if draft_path.exists():
            shutil.copy2(str(draft_path), str(final_path))
        imported += 1
        ch_num += 1
    
    # 更新当前章节进度
    try:
        cfg = sm.read_config()
        if (cfg.get("current_chapter") or 0) < ch_num - 1:
            cfg["current_chapter"] = ch_num - 1
        if cfg.get("target_chapters", 0) < ch_num - 1:
            cfg["target_chapters"] = ch_num - 1
        sm._write_json("config.json", cfg)
    except Exception:
        pass
    
    return {"ok": True, "imported": imported, "last_chapter": ch_num - 1}


# ── /api/books ────────────────────────────────────────────────────────────────

@app.get("/api/books")
def list_books():
    if not BOOKS_DIR.exists():
        return []
    books = []
    for d in BOOKS_DIR.iterdir():
        if not d.is_dir():
            continue
        config_path = d / "state" / "config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            ws_path = d / "state" / "world_state.json"
            current_ch = 0
            if ws_path.exists():
                ws = json.loads(ws_path.read_text(encoding="utf-8"))
                current_ch = ws.get("current_chapter", 0)
            # 检测各阶段状态
            has_setup = (d / "state" / "setup_state.json").exists()
            has_outline = (d / "state" / "outline.json").exists()
            has_chapters = bool(list((d / "chapters").glob("*_final.md")))
            books.append({
                **cfg,
                "current_chapter": current_ch,
                "finals": len(list((d / "chapters").glob("*_final.md"))),
                "drafts": len(list((d / "chapters").glob("*_draft.md"))),
                "stage": 4 if has_chapters else 3 if has_outline else 2 if has_setup else 1,
            })
    return books


@app.post("/api/books")
def create_book(req: CreateBookReq):
    """通过 Web UI 创建新书"""
    from core.state import StateManager
    from core.types.state import BookConfig

    book_id = req.title.replace(" ", "_").replace("/", "_")[:20]
    config = BookConfig(
        id=book_id,
        title=req.title,
        genre=req.genre,
        target_words_per_chapter=req.words,
        target_chapters=req.chapters,
        protagonist_id="",
        status="planning",
        created_at=datetime.now(timezone.utc).isoformat(),
        custom_forbidden_words=[w.strip() for w in req.forbidden.split(",") if w.strip()],
        style_guide=req.style_guide,
        use_predefined_events=req.use_predefined_events,
    )
    sm = StateManager(PROJECT_ROOT, book_id)
    sm.init(config)
    return {"ok": True, "book_id": book_id, "title": req.title}


@app.get("/api/books/{book_id}")
def get_book(book_id: str):
    sm = _sm(book_id)
    try:
        config = sm.read_config()
        ws = sm.read_world_state()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")

    from core.types.state import TruthFileKey
    hooks_md = sm.read_truth(TruthFileKey.PENDING_HOOKS)
    open_hooks = hooks_md.count("| open |")

    has_setup = (sm.state_dir / "setup_state.json").exists()
    has_outline = (sm.state_dir / "outline.json").exists()
    has_chapters = bool(list(sm.chapter_dir.glob("*_final.md")))

    return {
        **config,
        "current_chapter": ws.current_chapter,
        "open_hooks": open_hooks,
        "character_positions": ws.character_positions,
        "finals": len(list(sm.chapter_dir.glob("*_final.md"))),
        "drafts": len(list(sm.chapter_dir.glob("*_draft.md"))),
        "stage": 4 if has_chapters else 3 if has_outline else 2 if has_setup else 1,
    }


@app.delete("/api/books/{book_id}")
def delete_book(book_id: str):
    book_dir = BOOKS_DIR / book_id
    if not book_dir.exists():
        raise HTTPException(404, f"书籍不存在：{book_id}")
    shutil.rmtree(book_dir, ignore_errors=True)
    return {"ok": True}


# ── /api/books/{book_id}/setup  世界观配置 ───────────────────────────────────

@app.get("/api/books/{book_id}/setup/status")
def setup_status(book_id: str):
    """获取 setup 阶段状态"""
    sm = _sm(book_id)
    setup_dir = sm.book_dir / "setup"
    has_templates = setup_dir.exists() and any(setup_dir.glob("*.json"))
    has_setup_state = (sm.state_dir / "setup_state.json").exists()
    has_outline = (sm.state_dir / "outline.json").exists()

    files_status = {}
    for fname in ["characters.json", "world.json", "events.json"]:
        path = setup_dir / fname
        key = fname.replace(".json", "")
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # 根据文件类型确定列表键
                list_keys = {
                    "characters": "characters",
                    "world": "locations",
                    "events": "events",
                }
                lk = list_keys.get(key, list(data.keys())[0] if data else "")
                items = data.get(lk, []) if lk else []
                files_status[key] = {
                    "exists": True,
                    "modified": True,
                    "items": len(items) if isinstance(items, list) else 0,
                }
            except Exception:
                files_status[key] = {"exists": True, "modified": False, "items": 0}
        else:
            files_status[key] = {"exists": False}

    return {
        "has_templates": has_templates,
        "has_setup_state": has_setup_state,
        "has_outline": has_outline,
        "files": files_status,
    }


@app.post("/api/books/{book_id}/setup/init")
def setup_init_templates(book_id: str):
    """初始化世界观模板 JSON"""
    from core.setup import SetupLoader
    loader = SetupLoader(PROJECT_ROOT, book_id)
    loader.init_templates()
    return {"ok": True}


@app.get("/api/books/{book_id}/setup/{file_type}")
def setup_read(book_id: str, file_type: str):
    """读取 setup 下的 JSON 文件"""
    sm = _sm(book_id)
    setup_dir = sm.book_dir / "setup"
    filename = f"{file_type}.json"
    if file_type == "characters":
        filename = "characters.json"
    elif file_type == "world":
        filename = "world.json"
    elif file_type == "events":
        filename = "events.json"
    else:
        raise HTTPException(400, "只支持 characters / world / events")

    path = setup_dir / filename
    if not path.exists():
        raise HTTPException(404, f"{filename} 不存在，请先初始化模板")

    # 获取模板默认值作为参考
    tmpl_path = TEMPLATES_DIR / filename
    template_default = ""
    if tmpl_path.exists():
        template_default = tmpl_path.read_text(encoding="utf-8")

    return {
        "content": path.read_text(encoding="utf-8"),
        "template": template_default,
    }


@app.put("/api/books/{book_id}/setup/{file_type}")
def setup_save(book_id: str, file_type: str, req: SaveSetupReq):
    """保存 setup 下的 JSON 文件（带格式校验）"""
    sm = _sm(book_id)
    setup_dir = sm.book_dir / "setup"

    filename_map = {"characters": "characters.json", "world": "world.json", "events": "events.json"}
    filename = filename_map.get(file_type)
    if not filename:
        raise HTTPException(400, "只支持 characters / world / events")

    # 校验 JSON 格式
    try:
        data = json.loads(req.content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON 格式错误：{e}")

    setup_dir.mkdir(parents=True, exist_ok=True)
    path = setup_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"{filename} 已保存"}


@app.post("/api/books/{book_id}/setup/load")
def setup_load(book_id: str):
    """加载世界观配置（等同于 df setup load）"""
    from core.setup import SetupLoader
    try:
        loader = SetupLoader(PROJECT_ROOT, book_id)
        state = loader.load_all()
        return {
            "ok": True,
            "characters": list(state.characters.keys()),
            "locations": list(state.locations.keys()),
            "factions": list(state.factions.keys()),
            "events": len(state.seed_events),
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"加载失败：{e}")



# ── /api/books/{book_id}/chapters ────────────────────────────────────────────

@app.get("/api/books/{book_id}/chapters")
def list_chapters(book_id: str):
    sm = _sm(book_id)
    chapters = []
    for f in sorted(sm.chapter_dir.glob("ch*.md")):
        stem = f.stem
        parts = stem.split("_")
        num = int(parts[0].replace("ch", ""))
        kind = parts[1] if len(parts) > 1 else "draft"
        chapters.append({
            "number": num,
            "kind": kind,
            "chars": len(f.read_text(encoding="utf-8")),
            "filename": f.name,
        })
    return chapters


@app.post("/api/books/{book_id}/chapters/{chapter}/promote")
def promote_chapter(book_id: str, chapter: int):
    """将草稿升级为最终稿"""
    sm = _sm(book_id)
    draft = sm.read_draft(chapter)
    if not draft:
        raise HTTPException(404, f"第 {chapter} 章草稿不存在")
    sm.save_final(chapter, draft)
    # 更新 current_chapter
    try:
        cfg = sm.read_config()
        if (cfg.current_chapter or 0) < chapter:
            cfg.current_chapter = chapter
            sm.write_config(cfg)
    except Exception:
        pass
    return {"ok": True, "message": f"第 {chapter} 章已升级为最终稿"}


@app.get("/api/books/{book_id}/chapters/{chapter}")
def get_chapter(book_id: str, chapter: int):
    sm = _sm(book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        raise HTTPException(404, f"第 {chapter} 章不存在")
    kind = "final" if (sm.chapter_dir / f"ch{chapter:04d}_final.md").exists() else "draft"
    return {"number": chapter, "kind": kind, "content": content, "chars": len(content)}


# ── /api/books/{book_id}/causal-chain ────────────────────────────────────────

@app.get("/api/books/{book_id}/causal-chain")
def get_causal_chain(book_id: str):
    sm = _sm(book_id)
    ws = sm.read_world_state()
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list): return [to_dict(i) for i in obj]
        if hasattr(obj, "value"): return obj.value
        return obj
    return [to_dict(link) for link in ws.causal_chain]


# ── /api/books/{book_id}/emotional-arcs ──────────────────────────────────────

@app.get("/api/books/{book_id}/emotional-arcs")
def get_emotional_arcs(book_id: str):
    sm = _sm(book_id)
    ws = sm.read_world_state()
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list): return [to_dict(i) for i in obj]
        return obj
    arcs: dict[str, list] = {}
    for snap in ws.emotional_snapshots:
        arcs.setdefault(snap.character_id, []).append(to_dict(snap))
    return arcs


# ── /api/books/{book_id}/hooks ────────────────────────────────────────────────

@app.get("/api/books/{book_id}/hooks")
def get_hooks(book_id: str, status: str | None = None):
    sm = _sm(book_id)
    ws = sm.read_world_state()
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list): return [to_dict(i) for i in obj]
        if hasattr(obj, "value"): return obj.value
        return obj
    hooks = [to_dict(h) for h in ws.pending_hooks]
    if status:
        hooks = [h for h in hooks if h.get("status") == status]
    return hooks


@app.post("/api/books/{book_id}/hooks/{hook_id}/resolve")
def resolve_hook_api(book_id: str, hook_id: str, body: dict | None = None):
    """手动标记伏笔为已回收"""
    sm = _sm(book_id)
    chapter = (body or {}).get("chapter")
    if not chapter:
        chapter = sm.read_world_state().current_chapter or 0
    sm.resolve_hook(hook_id, int(chapter))
    sm.update_current_state_md()
    return {"ok": True, "hook_id": hook_id, "resolved_in_chapter": int(chapter)}


@app.post("/api/books/{book_id}/hooks/{hook_id}/reopen")
def reopen_hook_api(book_id: str, hook_id: str):
    """重新打开已回收的伏笔"""
    from core.types.state import HookStatus
    sm = _sm(book_id)
    ws = sm.read_world_state()
    for hook in ws.pending_hooks:
        if hook.id == hook_id:
            hook.status = HookStatus.OPEN
            hook.resolved_in_chapter = None
            break
    sm.write_world_state(ws)
    sm.update_current_state_md()
    return {"ok": True, "hook_id": hook_id}


# ── /api/books/{book_id}/relationships ───────────────────────────────────────

@app.get("/api/books/{book_id}/relationships")
def get_relationships(book_id: str):
    sm = _sm(book_id)
    ws = sm.read_world_state()
    import dataclasses
    def to_dict(obj):
        if dataclasses.is_dataclass(obj): return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list): return [to_dict(i) for i in obj]
        if hasattr(obj, "value"): return obj.value
        return obj
    return [to_dict(r) for r in ws.relationships]


# ── /api/books/{book_id}/threads  叙事线程管理 ─────────────────────────────

class CreateThreadReq(BaseModel):
    id: str
    name: str
    type: str = "subplot"           # main / subplot / parallel / flashback
    pov_character_id: str = ""
    character_ids: list[str] = []
    goal: str = ""
    growth_arc: str = ""
    start_chapter: int = 1
    weight: float = 0.7
    merge_chapter: int | None = None
    end_hook: str = ""


class UpdateThreadReq(BaseModel):
    name: str | None = None
    pov_character_id: str | None = None
    character_ids: list[str] | None = None
    goal: str | None = None
    growth_arc: str | None = None
    weight: float | None = None
    status: str | None = None          # active / dormant / resolved / merged
    hook_score: int | None = None
    end_hook: str | None = None
    merge_target_thread: str | None = None
    merge_chapter: int | None = None


@app.get("/api/books/{book_id}/threads")
def get_threads(book_id: str):
    """获取所有叙事线程"""
    sm = _sm(book_id)
    ws = sm.read_world_state()
    return _dc_to_dict(ws.threads)


@app.post("/api/books/{book_id}/threads")
def create_thread_api(book_id: str, req: CreateThreadReq):
    """创建新的叙事线程"""
    from core.types.narrative import NarrativeThread, ThreadType
    sm = _sm(book_id)
    thread = NarrativeThread(
        id=req.id,
        name=req.name,
        type=ThreadType(req.type),
        pov_character_id=req.pov_character_id,
        character_ids=req.character_ids,
        goal=req.goal,
        growth_arc=req.growth_arc,
        start_chapter=req.start_chapter,
        weight=req.weight,
        merge_chapter=req.merge_chapter,
        end_hook=req.end_hook,
    )
    sm.create_thread(thread)
    sm.update_thread_status_md()
    return {"ok": True, "thread_id": req.id}


@app.post("/api/books/{book_id}/auto-generate-threads")
def auto_generate_threads(book_id: str):
    """
    从已有角色列表出发，扫描章节大纲，为每个作为 POV 出现的角色生成叙事线程。
    匹配方式：角色名出现在章纲的 pov 文本、pov_character_id 或 beats 描述中。
    已有同名线程不会重复创建，只更新其关联章节信息。
    """
    from core.types.narrative import NarrativeThread, ThreadType
    from core.setup import SetupLoader
    sm = _sm(book_id)
    ws = sm.read_world_state()

    # 1. 从 setup 加载角色列表（角色在前面就已经配好了）
    try:
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
        characters = state.characters  # dict[str, Character]
    except FileNotFoundError:
        raise HTTPException(404, "请先完成世界观配置（Step 3）")

    if not characters:
        return {"ok": True, "threads_created": 0, "threads_updated": 0,
                "message": "角色列表为空，请先配置角色"}

    # 2. 读取章纲
    co_path = sm.state_dir / "chapter_outlines.json"
    if not co_path.exists():
        raise HTTPException(404, "请先生成章节大纲")
    all_cos = json.loads(co_path.read_text(encoding="utf-8"))

    # 3. 按名字长度降序排列，优先匹配长名字（"慕容玄霜" > "慕容"）
    char_list = sorted(characters.values(), key=lambda c: len(c.name), reverse=True)
    char_names = [c.name for c in char_list]
    char_id_map = {c.name: c.id for c in char_list}  # 名字 → ID

    # 4. 对每个章节，找出 POV 角色
    pov_chapters: dict[str, list[int]] = {}
    for co in all_cos:
        ch = co.get("chapter_number", 0)
        found_pov = ""
        pov_id = co.get("pov_character_id", "").strip()
        if pov_id:
            found_pov = characters[pov_id].name if pov_id in characters else pov_id
        if not found_pov:
            pov_text = co.get("pov", "")
            if pov_text:
                for name in char_names:
                    if name in pov_text:
                        found_pov = name
                        break
        if not found_pov:
            for beat in co.get("beats", []):
                bp = beat.get("pov_character_id", "").strip()
                if bp:
                    found_pov = characters[bp].name if bp in characters else bp
                    break
                bd = beat.get("description", "")
                if bd:
                    for name in char_names:
                        if name in bd:
                            found_pov = name
                            break
                if found_pov:
                    break
        if found_pov:
            pov_chapters.setdefault(found_pov, []).append(ch)

    if not pov_chapters:
        names = char_names[:5]
        if len(char_names) > 5:
            names.append("等" + str(len(char_names)) + "个角色")
        return {"ok": True, "threads_created": 0, "threads_updated": 0,
                "message": "章纲中未匹配到 POV 角色。已有角色：" + "、".join(names)}

    # 5. 创建/更新线程
    existing_thread_ids: set[str] = {t.id for t in ws.threads}

    created = 0
    updated = 0
    max_ch_count = max(len(v) for v in pov_chapters.values())

    for pov_name, chapters in sorted(pov_chapters.items()):
        # 检查是否已有该 POV 角色的线程
        existing = None
        for t in ws.threads:
            if t.pov_character_id == pov_name:
                existing = t
                break
            if pov_name in (t.character_ids or []):
                existing = t
                break

        start_ch = min(chapters)
        char_id = char_id_map.get(pov_name, "")

        if existing:
            updates = {}
            if existing.start_chapter > start_ch:
                updates["start_chapter"] = start_ch
            if existing.last_active_chapter < max(chapters):
                updates["last_active_chapter"] = max(chapters)
            if len(chapters) == max_ch_count and existing.type != ThreadType.MAIN:
                updates["type"] = ThreadType.MAIN
                updates["weight"] = 1.0
            if updates:
                sm.update_thread(existing.id, **updates)
                updated += 1
        else:
            if len(chapters) == max_ch_count:
                thread_type = ThreadType.MAIN
                weight = 1.0
            else:
                thread_type = ThreadType.SUBPLOT
                weight = 0.7

            final_id = f"thread_{pov_name}"
            if final_id in existing_thread_ids:
                final_id = f"thread_{pov_name}_{uuid.uuid4().hex[:4]}"

            new_thread = NarrativeThread(
                id=final_id,
                name=f"{pov_name}线",
                type=thread_type,
                pov_character_id=char_id or pov_name,
                start_chapter=start_ch,
                last_active_chapter=max(chapters),
                weight=weight,
                goal="",
                growth_arc="",
                status="active",
                character_ids=[],
                end_hook="",
            )
            sm.create_thread(new_thread)
            existing_thread_ids.add(final_id)
            created += 1

    sm.update_thread_status_md()

    return {
        "ok": True,
        "threads_created": created,
        "threads_updated": updated,
        "pov_characters_found": list(pov_chapters.keys()),
        "detail": {pov: {"chapters": chs, "count": len(chs)} for pov, chs in pov_chapters.items()},
    }


@app.put("/api/books/{book_id}/threads/{thread_id}")
def update_thread_api(book_id: str, thread_id: str, req: UpdateThreadReq):
    """更新叙事线程"""
    sm = _sm(book_id)
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    if kwargs:
        sm.update_thread(thread_id, **kwargs)
        sm.update_thread_status_md()
    return {"ok": True}


@app.delete("/api/books/{book_id}/threads/{thread_id}")
def delete_thread_api(book_id: str, thread_id: str):
    """删除叙事线程及其时间轴事件"""
    sm = _sm(book_id)
    sm.delete_thread(thread_id)
    sm.update_thread_status_md()
    return {"ok": True}


@app.get("/api/books/{book_id}/threads/status")
def get_thread_status(book_id: str):
    """获取线程状态报告（含掉线预警和时间轴）"""
    sm = _sm(book_id)
    ws = sm.read_world_state()
    return {
        "current_chapter": ws.current_chapter,
        "threads": _dc_to_dict(ws.threads),
        "dormant": _dc_to_dict(ws.dormant_threads(ws.current_chapter, threshold=5)),
        "timeline": _dc_to_dict(ws.timeline[-30:]),
        "thread_chapter_map": ws.thread_chapter_map(),
        "cross_thread_causal_links": _dc_to_dict(sm.get_cross_thread_causal_links()),
    }


@app.get("/api/books/{book_id}/timeline")
def get_timeline(book_id: str, thread_id: str | None = None, character_id: str | None = None,
                 from_chapter: int | None = None, to_chapter: int | None = None):
    """获取全局时间轴（可按线程/角色/章节范围过滤）"""
    sm = _sm(book_id)
    if thread_id:
        events = sm.get_thread_timeline(thread_id)
    elif character_id:
        events = sm.get_character_timeline(character_id)
    else:
        ws = sm.read_world_state()
        events = ws.timeline
    # 章节范围过滤
    if from_chapter is not None:
        events = [e for e in events if (e.chapter if hasattr(e, 'chapter') else e.get('chapter', 0)) >= from_chapter]
    if to_chapter is not None:
        events = [e for e in events if (e.chapter if hasattr(e, 'chapter') else e.get('chapter', 0)) <= to_chapter]
    return _dc_to_dict(events)


# ── /api/books/{book_id}/outline ─────────────────────────────────────────────

@app.get("/api/books/{book_id}/outline")
def get_outline(book_id: str):
    sm = _sm(book_id)
    outline_path = sm.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "大纲尚未生成，请先运行 df write")
    return json.loads(outline_path.read_text(encoding="utf-8"))


@app.get("/api/books/{book_id}/chapter-outlines")
def get_chapter_outlines(book_id: str):
    sm = _sm(book_id)
    path = sm.state_dir / "chapter_outlines.json"
    if not path.exists():
        raise HTTPException(404, "章纲尚未生成")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/api/books/{book_id}/outline")
def save_outline(book_id: str, req: SaveOutlineReq):
    """保存/更新大纲"""
    sm = _sm(book_id)
    outline_path = sm.state_dir / "outline.json"
    outline_path.write_text(json.dumps(req.outline, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": "大纲已保存"}


@app.put("/api/books/{book_id}/chapter-outlines")
def save_chapter_outlines(book_id: str, req: SaveChapterOutlinesReq):
    """保存/更新章纲"""
    sm = _sm(book_id)
    path = sm.state_dir / "chapter_outlines.json"
    path.write_text(json.dumps(req.outlines, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"已保存 {len(req.outlines)} 章章纲"}


# ── 导入大纲（外部大模型提取后导入） ──────────────────────────────────────────

class ImportOutlineReq(BaseModel):
    outline: dict  # 故事大纲 JSON


@app.post("/api/books/{book_id}/import/outline")
def import_outline(book_id: str, req: ImportOutlineReq):
    """导入故事大纲：规范化补缺 + 保存"""
    sm = _sm(book_id)
    from core.state import StateManager

    raw = req.outline

    # 校验必要字段
    if not raw.get("sequences"):
        raise HTTPException(400, "大纲缺少 sequences 数组")
    if not isinstance(raw["sequences"], list):
        raise HTTPException(400, "sequences 必须是数组")

    # 规范化（复用 _normalize_outline）
    try:
        raw = _normalize_outline(raw, sm)
    except Exception as e:
        raise HTTPException(400, f"大纲规范化失败：{e}")

    # 用 Pydantic 验证
    try:
        from core.narrative import StoryOutlineSchema
        StoryOutlineSchema.model_validate_json(json.dumps(raw, ensure_ascii=False))
    except Exception as e:
        # 即使 Pydantic 验证失败也保存（用户可手动修正），只给警告
        logging.warning(f"大纲 Pydantic 验证警告：{e}")

    # 保存
    outline_path = sm.state_dir / "outline.json"
    outline_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新 config 中的 target_chapters
    try:
        cfg = sm.read_config()
        total = sum(s.get("estimated_scenes", 0) for s in raw.get("sequences", []))
        if total > 0:
            cfg["target_chapters"] = total
            sm._write_json("config.json", cfg)
    except Exception:
        pass

    seq_count = len(raw.get("sequences", []))
    total_ch = sum(s.get("estimated_scenes", 0) for s in raw.get("sequences", []))
    return {
        "ok": True,
        "message": f"大纲导入成功：{seq_count} 个序列，共 {total_ch} 章",
        "sequences": seq_count,
        "total_chapters": total_ch,
    }


class ImportChapterOutlinesReq(BaseModel):
    outlines: list  # 章纲列表 JSON 数组
    merge: bool = False  # True=追加到已有章纲，False=覆盖


@app.post("/api/books/{book_id}/import/chapter-outlines")
def import_chapter_outlines(book_id: str, req: ImportChapterOutlinesReq):
    """导入章节大纲：规范化补缺 + 保存，支持追加或覆盖"""
    sm = _sm(book_id)

    if not req.outlines or not isinstance(req.outlines, list):
        raise HTTPException(400, "章纲数据为空或格式错误")

    if len(req.outlines) > 500:
        raise HTTPException(400, f"单次导入上限 500 章，当前 {len(req.outlines)} 章，请分批导入")

    # 修正每个章纲
    fixed_count = 0
    for i, co in enumerate(req.outlines):
        if not isinstance(co, dict):
            continue

        # 修正 chapter_number
        if "chapter_number" not in co and "chapter" in co:
            co["chapter_number"] = co.pop("chapter")
        if "chapter_number" not in co:
            co["chapter_number"] = i + 1

        # 补缺字段
        co.setdefault("title", f"第{co['chapter_number']}章-情节推进")
        co.setdefault("summary", "")
        co.setdefault("sequence_id", "")
        co.setdefault("beats", [])
        co.setdefault("emotional_arc", {"start": "平静", "end": "紧张"})
        co.setdefault("mandatory_tasks", [])
        co.setdefault("target_words", 4000)

        # 修正浮点数
        for key in ("chapter_number", "target_words"):
            if key in co and isinstance(co[key], float):
                co[key] = int(co[key])

        # 修正 beats
        for bi, beat in enumerate(co.get("beats", [])):
            if not isinstance(beat, dict):
                continue
            if not beat.get("id"):
                beat["id"] = f"beat_{co['chapter_number']}_{bi+1}"
            df = beat.get("dramatic_function", "transition")
            beat["dramatic_function"] = _DF_MAP.get(df, df)

        if not co.get("beats"):
            co["beats"] = [{
                "id": f"beat_{co['chapter_number']}_1",
                "description": "情节推进",
                "dramatic_function": "transition",
            }]

    # 读取或初始化已有章纲
    co_path = sm.state_dir / "chapter_outlines.json"
    if req.merge and co_path.exists():
        all_cos = json.loads(co_path.read_text(encoding="utf-8"))
        if not isinstance(all_cos, list):
            all_cos = []
        # 找到已有章纲的最大编号
        max_ch = max((c.get("chapter_number", 0) for c in all_cos), default=0)
        # 重新编号导入的章纲（从 max_ch+1 开始）
        for co in req.outlines:
            co["chapter_number"] = max_ch + req.outlines.index(co) + 1
            # 同步更新 beat id
            for bi, beat in enumerate(co.get("beats", [])):
                beat["id"] = f"beat_{co['chapter_number']}_{bi+1}"
        all_cos.extend(req.outlines)
    else:
        all_cos = req.outlines
        # 确保 chapter_number 连续
        for i, co in enumerate(all_cos):
            co["chapter_number"] = i + 1
            for bi, beat in enumerate(co.get("beats", [])):
                beat["id"] = f"beat_{co['chapter_number']}_{bi+1}"

    # 保存
    co_path.write_text(json.dumps(all_cos, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新 config
    try:
        cfg = sm.read_config()
        if len(all_cos) > (cfg.get("target_chapters") or 0):
            cfg["target_chapters"] = len(all_cos)
            sm._write_json("config.json", cfg)
    except Exception:
        pass

    # 更新当前章节
    try:
        ws = sm.read_world_state()
        max_written = max(
            (int(f.stem.split("_")[0].replace("ch", ""))
             for f in sm.chapter_dir.glob("*_final.md")),
            default=0,
        )
        if ws.current_chapter < max_written:
            ws.current_chapter = max_written
            sm.write_world_state(ws)
    except Exception:
        pass

    return {
        "ok": True,
        "message": f"章纲导入成功：{len(req.outlines)} 章（{'追加' if req.merge else '覆盖'}模式）",
        "imported": len(req.outlines),
        "total": len(all_cos),
    }


class ContinueWritingReq(BaseModel):
    extra_chapters: int = 10  # 续写章数


@app.post("/api/books/{book_id}/continue-writing")
async def continue_writing(book_id: str, req: ContinueWritingReq):
    """续写：为已完成的书籍追加新章纲，支持超过 target_chapters 后继续写作"""
    _load_env()
    sm = _sm(book_id)
    co_path = sm.state_dir / "chapter_outlines.json"
    if not co_path.exists():
        raise HTTPException(404, "请先生成章节大纲")
    
    all_cos = json.loads(co_path.read_text(encoding="utf-8"))
    current_count = len(all_cos)
    start_ch = current_count + 1
    end_ch = current_count + req.extra_chapters

    # 读取大纲和配置获取上下文
    outline_data = {}
    outline_path = sm.state_dir / "outline.json"
    if outline_path.exists():
        outline_data = json.loads(outline_path.read_text(encoding="utf-8"))

    try:
        cfg_data = sm.read_config()
    except FileNotFoundError:
        raise HTTPException(404, "书籍不存在")

    # 读取最后几章的摘要作为上下文
    summaries_path = sm.state_dir / "chapter_summaries.md"
    recent_summaries = ""
    if summaries_path.exists():
        recent_summaries = summaries_path.read_text(encoding="utf-8")[-3000:]

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    title = cfg_data.get("title", "未命名")
    genre = cfg_data.get("genre", "玄幻")
    target_words = cfg_data.get("target_words_per_chapter", 4000)

    # 读取最后5章大纲作为衔接上下文
    last_cos = all_cos[-5:] if len(all_cos) >= 5 else all_cos

    # 计算故事大纲中尚未被章节大纲覆盖的序列
    sequences = outline_data.get("sequences", [])
    ch_cursor = 1
    uncovered_seqs = []
    for seq in sequences:
        est = seq.get("estimated_scenes", 0)
        if ch_cursor + est - 1 > current_count:
            uncovered_seqs.append({
                "number": seq.get("number", "?"),
                "act": seq.get("act", "?"),
                "summary": seq.get("summary", ""),
                "narrative_goal": seq.get("narrative_goal", ""),
                "dramatic_function": seq.get("dramatic_function", ""),
                "key_events": seq.get("key_events", []),
                "end_hook": seq.get("end_hook", ""),
                "estimated_scenes": est,
            })
        ch_cursor += est

    from core.llm import LLMMessage

    if uncovered_seqs:
        # 联动模式：基于故事大纲中未覆盖的序列来续写章节大纲
        seq_context = "\n".join(
            f"- 序列{s['number']}（第{s['act']}幕，约{s['estimated_scenes']}章）：{s['summary']}\n"
            f"  叙事目标：{s['narrative_goal']}\n"
            f"  关键事件：{', '.join(s['key_events'][:5]) if s['key_events'] else '无'}\n"
            f"  结尾钩子：{s['end_hook']}"
            for s in uncovered_seqs
        )
        total_uncovered = sum(s["estimated_scenes"] for s in uncovered_seqs)
        actual_count = min(req.extra_chapters, total_uncovered)
        end_ch = start_ch + actual_count - 1
        prompt = f"""你是一位专业的小说编辑。现在需要基于故事大纲中尚未展开的序列，续写章节大纲。

## 小说信息
- 书名：{title}
- 题材：{genre}
- 已有章节大纲：{current_count} 章
- 续写目标：第 {start_ch} 章 ~ 第 {end_ch} 章（共 {actual_count} 章）
- 每章目标字数：约 {target_words} 字

## 待展开的故事大纲序列（{len(uncovered_seqs)} 个序列，共约 {total_uncovered} 章）
{seq_context}

## 已有最后几章大纲（用于衔接）
{json.dumps(last_cos, ensure_ascii=False, indent=2)}

## 最近章节摘要
{recent_summaries[-2000:] if recent_summaries else '（无摘要）'}

## 要求
1. 严格按照待展开序列的摘要、叙事目标和关键事件来规划章节内容
2. 每章大纲包含：chapter_number, title, summary, target_words, beats, emotional_arc, mandatory_tasks
3. 序列结尾钩子必须在对应序列最后一章体现
4. 每个序列的关键事件要合理分配到各章节
5. 保持与原有大纲风格一致

请输出一个 JSON 数组，直接输出不要说明：
[
  {{
    "chapter_number": {start_ch},
    "title": "章节标题",
    "summary": "200字左右的章节摘要",
    "target_words": {target_words},
    "beats": [
      {{"description": "节拍描述", "dramatic_function": "setup"}}
    ],
    "emotional_arc": {{"start": "平静", "end": "紧张"}},
    "mandatory_tasks": ["必须完成的叙事任务"]
  }}
]"""
    else:
        # 自由续写模式：故事大纲已全部覆盖，基于已有章纲尾部自滚动
        prompt = f"""你是一位专业的小说编辑。现在需要为一本已经写完主要剧情的小说续写{req.extra_chapters}章的章节大纲。

## 小说信息
- 书名：{title}
- 题材：{genre}
- 已完成：{current_count} 章
- 续写目标：第 {start_ch} 章到第 {end_ch} 章
- 每章目标字数：约 {target_words} 字

## 已有最后几章大纲（用于衔接）
{json.dumps(last_cos, ensure_ascii=False, indent=2)}

## 最近章节摘要
{recent_summaries[-2000:] if recent_summaries else '（无摘要）'}

## 要求
1. 续写章节要自然衔接已有剧情
2. 每章大纲包含：chapter_number, title, summary, target_words, beats, emotional_arc, mandatory_tasks
3. 可以开启新的支线或深化已有伏笔
4. 保持与原有大纲风格一致

请输出一个 JSON 数组，直接输出不要说明：
[
  {{
    "chapter_number": {start_ch},
    "title": "章节标题",
    "summary": "200字左右的章节摘要",
    "target_words": {target_words},
    "beats": [
      {{"description": "节拍描述", "dramatic_function": "setup"}}
    ],
    "emotional_arc": {{"start": "平静", "end": "紧张"}},
    "mandatory_tasks": ["必须完成的叙事任务"]
  }}
]"""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是专业的小说编辑，只输出合法 JSON 数组。"), LLMMessage("user", prompt)],
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0]
        import re
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw.strip(), flags=re.MULTILINE).strip()
        new_cos = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"续写大纲 JSON 解析失败：{e}")
    except Exception as e:
        raise HTTPException(500, f"续写失败：{e}")

    # 修正 chapter_number、beats、sequence_id 并追加
    for i, co in enumerate(new_cos):
        co["chapter_number"] = start_ch + i
        # 确保 sequence_id 存在（续写模式下生成新的序列ID）
        if "sequence_id" not in co or not co["sequence_id"]:
            co["sequence_id"] = f"seq_{start_ch + i}"
        # 修正 dramatic_function 和缺失的 beat id
        if co.get("dramatic_function"):
            co["dramatic_function"] = _DF_MAP.get(co["dramatic_function"], co["dramatic_function"])
        for bi, beat in enumerate(co.get("beats", [])):
            if not beat.get("id"):
                beat["id"] = f"beat_{co['chapter_number']}_{bi+1}"
            if beat.get("dramatic_function"):
                beat["dramatic_function"] = _DF_MAP.get(beat["dramatic_function"], beat["dramatic_function"])
    all_cos.extend(new_cos)
    co_path.write_text(json.dumps(all_cos, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新 config 的 target_chapters
    cfg_data["target_chapters"] = len(all_cos)
    sm._write_json("config.json", cfg_data)

    return {
        "ok": True,
        "added": len(new_cos),
        "new_total": len(all_cos),
        "outlines": all_cos,
        "mode": "outline_driven" if uncovered_seqs else "free",
        "uncovered_sequences": len(uncovered_seqs),
    }


@app.put("/api/books/{book_id}/config")
def update_book_config(book_id: str, req: UpdateBookConfigReq):
    """更新书籍配置（文风指南、禁止词等）"""
    from core.state import StateManager
    from core.types.state import BookConfig
    sm = _sm(book_id)
    try:
        cfg_data = sm.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")
    if req.style_guide is not None:
        cfg_data["style_guide"] = req.style_guide
    if req.forbidden is not None:
        cfg_data["custom_forbidden_words"] = [w.strip() for w in req.forbidden.split(",") if w.strip()]
    if req.protagonist_id is not None:
        cfg_data["protagonist_id"] = req.protagonist_id
    if req.target_chapters is not None and req.target_chapters > 0:
        cfg_data["target_chapters"] = req.target_chapters
    if req.target_words_per_chapter is not None and req.target_words_per_chapter > 0:
        cfg_data["target_words_per_chapter"] = req.target_words_per_chapter
    if req.title is not None:
        cfg_data["title"] = req.title
    if req.genre is not None:
        cfg_data["genre"] = req.genre
    sm._write_json("config.json", cfg_data)
    return {"ok": True, "message": "配置已更新"}


@app.get("/api/books/{book_id}/config")
def get_book_config(book_id: str):
    """获取书籍配置"""
    sm = _sm(book_id)
    try:
        return sm.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")


# ── /api/books/{book_id}/ai-generate  AI 辅助生成 ────────────────────────────

@app.post("/api/books/{book_id}/ai-generate/setup")
async def ai_generate_setup(book_id: str, req: AiGenerateSetupReq):
    """AI 根据题材和想法生成完整世界观 JSON"""
    _load_env()
    from core.llm import LLMMessage
    try:
        llm = _create_llm(temperature=0.8)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    prompt = f"""\
你是一位资深的网文世界观设计师。请为以下小说生成完整的世界观配置 JSON。

## 小说信息
- 书名：{req.book_title}
- 题材：{req.genre}
- 核心想法：{req.idea or '（请自行构思一个有吸引力的核心设定）'}
- 详细程度：{'详细' if req.style == 'detailed' else '精简' if req.style == 'minimalist' else '标准'}

请严格按以下 JSON 结构输出（直接输出 JSON，不要任何说明）：

```json
{{
  "characters": [
    {{
      "id": "char_001",
      "name": "角色姓名",
      "role": "protagonist/antagonist/mentor/love_interest/supporting",
      "need": {{
        "external": "外部目标（一句话）",
        "internal": "内在渴望（一句话）"
      }},
      "personality": ["性格特征1", "性格特征2"],
      "behavior_lock": ["性格锁定的行为绝对不做的事"],
      "arc": "角色弧线：从什么状态变为什么状态",
      "backstory": "简短背景（2-3句话）"
    }}
  ],
  "world": {{
    "locations": [
      {{
        "id": "loc_001",
        "name": "地点名称",
        "description": "简短描述",
        "significance": "在故事中的意义"
      }}
    ],
    "factions": [
      {{
        "id": "fac_001",
        "name": "势力名称",
        "description": "简短描述",
        "stance": "对主角的态度"
      }}
    ],
    "rules": [
      {{
        "name": "规则名称",
        "description": "这个世界特有的规则/设定",
        "impact": "对故事的影响"
      }}
    ]
  }},
  "events": [
    {{
      "id": "evt_001",
      "name": "事件名称",
      "description": "事件描述",
      "suggested_act": 1,
      "suggested_function": "inciting_incident/turning_point/climax/resolution/setup/midpoint",
      "characters_involved": ["char_001"],
      "dramatic_question": "这个事件引发的戏剧性疑问"
    }}
  ]
}}
```

要求：
1. 设计 3-6 个角色（含主角、反派、导师、情感线角色）
2. 设计 4-8 个地点
3. 设计 2-4 个势力
4. 设计 2-5 个世界规则
5. 设计 5-10 个种子事件，覆盖三幕结构的关键节点
6. 事件必须按剧情发展顺序排列"""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是资深网文世界观设计师，只输出合法 JSON。"), LLMMessage("user", prompt)],
        )
        content = resp.content.strip()
        # 提取 JSON
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]
        data = json.loads(content)
        
        # 强制为每个序列补充 key_events，确保数量足够且每个事件都独特
        event_templates = [
            "冲突爆发", "危机化解", "秘密揭露", "盟友背叛", "关键抉择",
            "绝境逆袭", "真相大白", "计划失败", "意外发现", "命运转折",
            "阴谋败露", "危机升级", "盟友加入", "技能突破", "真相反转",
            "陷阱布置", "危机解除", "秘密潜入", "身份暴露", "决战前夕"
        ]
        for seq in data.get("sequences", []):
            if "key_events" not in seq:
                seq["key_events"] = []
            # 需要补充到 estimated_scenes 的数量
            needed = max(seq.get("estimated_scenes", 5), len(seq["key_events"]))
            summary = seq.get("summary", "")
            goal = seq.get("narrative_goal", "")
            full_text = (summary + goal).replace(" ", "")
            
            while len(seq["key_events"]) < needed:
                idx = len(seq["key_events"])
                # 使用事件模板 + 文本关键词组合，确保每个事件都独特
                event_type = event_templates[idx % len(event_templates)]
                text_pos = (idx * 5) % max(len(full_text) - 3, 1)
                keyword = full_text[text_pos:text_pos+3] if len(full_text) > 3 else ""
                new_event = f"{keyword}{event_type}{idx+1}"
                
                # 确保不重复
                if new_event not in seq["key_events"]:
                    seq["key_events"].append(new_event)
                else:
                    # 如果重复，使用纯事件模板
                    seq["key_events"].append(f"{event_type}{idx+1}")
        
        return {"ok": True, "data": data}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 输出 JSON 解析失败：{e}", "raw": content[-500:] if content else ""}
    except Exception as e:
        raise HTTPException(500, f"AI 生成失败：{e}")


@app.post("/api/books/{book_id}/extract-from-novel")
async def extract_from_novel(book_id: str, req: ExtractFromNovelReq):
    """从现有小说文本中提取角色和世界设定"""
    _load_env()
    from core.llm import LLMMessage

    # 文本截断：最多取前 15000 字
    text = req.text.strip()
    if len(text) > 15000:
        text = text[:15000] + "\n\n...（文本过长，已截断前 15000 字）"

    try:
        llm = _create_llm(temperature=0.3)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    prompt = f"""你是一位资深的小说分析师。请从以下小说文本中提取角色信息和世界设定。

## 小说题材
{req.genre}

## 小说文本
{text}

请严格按以下 JSON 结构输出（直接输出 JSON，不要任何说明）：

```json
{{
  "characters": [
    {{
      "id": "char_001",
      "name": "角色姓名",
      "role": "protagonist/antagonist/mentor/love_interest/supporting",
      "need": {{
        "external": "外部目标（一句话）",
        "internal": "内在渴望（一句话）"
      }},
      "personality": ["性格特征1", "性格特征2"],
      "behavior_lock": ["性格锁定的行为绝对不做的事"],
      "arc": "角色弧线：从什么状态变为什么状态",
      "backstory": "从文本推断的背景（2-3句话）"
    }}
  ],
  "world": {{
    "locations": [
      {{
        "id": "loc_001",
        "name": "地点名称",
        "description": "从文本推断的地点描述",
        "significance": "在故事中的意义"
      }}
    ],
    "factions": [
      {{
        "id": "fac_001",
        "name": "势力名称",
        "description": "从文本推断的势力描述",
        "stance": "对主角的态度"
      }}
    ],
    "rules": [
      {{
        "name": "规则名称",
        "description": "从文本推断的世界特有规则/设定",
        "impact": "对故事的影响"
      }}
    ]
  }},
  "events": [
    {{
      "id": "evt_001",
      "name": "事件名称",
      "description": "事件描述",
      "suggested_act": 1,
      "suggested_function": "inciting_incident/turning_point/climax/resolution/setup/midpoint",
      "characters_involved": ["char_001"],
      "dramatic_question": "这个事件引发的戏剧性疑问"
    }}
  ]
}}
```

分析要求：
1. 仔细阅读文本，提取所有出现的角色（有名字的、有台词的、有行动的）
2. 根据角色在文本中的行为、对话和他人评价推断其性格、目标和渴望
3. 提取文本中提到的所有地点、势力组织和世界规则
4. 将关键情节转化为事件，标注其戏剧功能
5. 如果文本信息不足以推断某个字段，请根据上下文合理推测并标注
6. 角色数量不限，尽可能完整提取
7. id 格式：char_001, char_002... / loc_001, loc_002... / fac_001, fac_002... / evt_001, evt_002..."""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是资深的小说分析师，擅长从文本中提取角色和世界观信息。只输出合法 JSON。"), LLMMessage("user", prompt)],
        )
        content = resp.content.strip()
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]
        data = json.loads(content)
        return {"ok": True, "data": data}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 输出 JSON 解析失败：{e}", "raw": content[-500:] if content else ""}
    except Exception as e:
        raise HTTPException(500, f"提取失败：{e}")


class ExtractStoryStateReq(BaseModel):
    chapter: int
    thread_id: str = "thread_main"


@app.post("/api/books/{book_id}/extract-story-state")
async def extract_story_state(book_id: str, req: ExtractStoryStateReq):
    """从已有章节正文提取故事状态数据（时间线事件、情感、关系、伏笔、因果链）"""
    _load_env()
    sm = _sm(book_id)
    content = sm.read_final(req.chapter) or sm.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {req.chapter} 章不存在")

    try:
        llm = _create_llm(temperature=0.2)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    from core.llm import LLMMessage
    from core.state import StateManager
    from core.types.state import EmotionalSnapshot, CausalLink, AffectedDecision, Hook, HookType, HookStatus, RelationshipRecord

    # 截断避免超token
    content_for_llm = content[:8000] + ("\n\n...（截断）" if len(content) > 8000 else "")

    # 加载角色列表，让 LLM 知道角色名
    char_list = []
    try:
        chars_data = sm.read_characters()
        if isinstance(chars_data, dict) and "characters" in chars_data:
            char_list = [c.get("name", "") for c in chars_data["characters"] if c.get("name")]
    except Exception:
        pass

    char_hint = ""
    if char_list:
        char_hint = f"\n已知角色名单：{', '.join(char_list)}\n"

    prompt = f"""你是一位小说分析专家。请仔细阅读以下章节正文，提取其中的故事状态变化。
{char_hint}
## 第 {req.chapter} 章正文
{content_for_llm}

请严格按以下 JSON 结构输出（直接输出 JSON，不要任何说明）：

```json
{{
  "position_changes": [
    {{"character": "角色名", "location": "到达地点"}}
  ],
  "emotional_changes": [
    {{"character": "角色名", "emotion": "情感描述", "intensity": 7, "trigger": "触发原因"}}
  ],
  "relationship_changes": [
    {{"character_a": "角色A名", "character_b": "角色B名", "delta": 10, "reason": "变化原因"}}
  ],
  "hooks_planted": [
    "本章埋下的伏笔描述"
  ],
  "hooks_resolved": [
    "本章回收的伏笔描述"
  ],
  "info_revealed": [
    {{"character": "角色名", "info_key": "信息标识", "content": "得知了什么"}}
  ],
  "key_events": [
    {{"action": "事件描述", "character": "主要角色名", "type": "position|emotion|info|conflict|key|other"}}
  ],
  "chapter_main_characters": ["本章主要角色的名字（按出场重要性排序，通常1-3人）"],
  "causal_link": {{
    "cause": "触发原因",
    "event": "核心事件",
    "consequence": "直接后果"
  }}
}}
```

分析要求：
1. position_changes：角色位置发生变化的记录（移动到新地点）
2. emotional_changes：角色情感发生明显变化的记录（intensity 1-10，仅记录强度>=5的）
3. relationship_changes：角色关系发生变化的记录（delta: -100到+100）
4. hooks_planted：本章新埋下的伏笔（一句话描述）
5. hooks_resolved：本章回收的伏笔（一句话描述）
6. info_revealed：角色获得了新信息的记录
7. key_events：本章的关键事件（用于时间轴，type 可选: position/emotion/info/conflict/key/other，特别重要的情节转折标记为 key）
8. chapter_main_characters：本章的主要角色名单（1-3人），用于自动分配时间线到对应角色线程

重要：所有 character / character_a / character_b 字段必须填写**角色在小说中的名字**（如"陈一帆""苏婉清"），不要填写自创的代号或 ID。请从正文中识别角色的真实名字。
9. causal_link：本章的核心因果关系（如果有的话）"""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是小说分析专家，擅长从正文提取结构化状态数据。只输出合法 JSON。"), LLMMessage("user", prompt)],
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0]
        raw = raw.strip()

        def _try_parse(text):
            import re as _re
            data = json.loads(text)
            return data

        def _repair_json(text):
            import re as _re
            fixed = text
            fixed = _re.sub(r',\s*([}\]])', r'\1', fixed)          # 尾逗号
            fixed = _re.sub(r'//.*', '', fixed)                      # 行注释
            fixed = _re.sub(r'/\*.*?\*/', '', fixed, flags=_re.DOTALL)  # 块注释
            fixed = _re.sub(r"'([^']*)'", r'"\1"', fixed)            # 单引号→双引号
            fixed = _re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', fixed)  # 转义修复
            # 去掉 control characters (除了 \n \r \t)
            fixed = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fixed)
            # 修复非法的 +前缀数字 (JSON 不允许 +10, 必须是 10 或 -10)
            fixed = _re.sub(r':\s*\+(\d)', r': \1', fixed)
            return fixed

        data = None
        try:
            data = _try_parse(raw)
        except json.JSONDecodeError:
            try:
                data = _try_parse(_repair_json(raw))
            except json.JSONDecodeError as e2:
                # 尝试截断修复（可能 LLM 输出不完整）
                from core.llm import _repair_truncated_json
                try:
                    repaired = _repair_truncated_json(raw)
                    data = _try_parse(_repair_json(repaired))
                except json.JSONDecodeError as e3:
                    # 展示出错位置附近的内容
                    pos = e3.pos if hasattr(e3, 'pos') else 0
                    start = max(0, pos - 100)
                    end = min(len(raw), pos + 100)
                    context_snippet = raw[start:end]
                    return {"ok": False, "error": f"JSON 解析失败：{e3}", "raw": raw[:1200] if raw else "", "context": f"...位置 {pos} 附近:\n{context_snippet}..."}
        if data is None:
            return {"ok": False, "error": "JSON 解析结果为空", "raw": raw[:1200] if raw else ""}
    except json.JSONDecodeError as e:
        pos = e.pos if hasattr(e, 'pos') else 0
        start = max(0, pos - 100)
        end = min(len(raw), pos + 100)
        context_snippet = raw[start:end]
        return {"ok": False, "error": f"JSON 解析失败：{e}", "raw": raw[:1200] if raw else "", "context": f"...位置 {pos} 附近:\n{context_snippet}..."}
    except Exception as e:
        raise HTTPException(500, f"提取失败：{e}")

    # 应用到 world_state
    import uuid
    ws = sm.read_world_state()
    applied = {"emotions": 0, "positions": 0, "relationships": 0, "hooks": 0, "timeline": 0, "info": 0, "causal": 0}

    # 位置变化
    for pc in data.get("position_changes", []):
        char_id = pc.get("character") or pc.get("character_id") or pc.get("character_name", "")
        loc = pc.get("location", "")
        if char_id and loc:
            ws.character_positions[char_id] = loc
            applied["positions"] += 1

    # 情感变化
    for ec in data.get("emotional_changes", []):
        char_id = ec.get("character") or ec.get("character_id") or ec.get("character_name", "")
        if not char_id:
            continue
        snap = EmotionalSnapshot(
            character_id=char_id,
            emotion=ec.get("emotion", "未知"),
            intensity=int(ec.get("intensity", 5)),
            chapter=req.chapter,
            trigger=ec.get("trigger", ""),
        )
        ws.emotional_snapshots.append(snap)
        applied["emotions"] += 1

    # 关系变化
    for rc in data.get("relationship_changes", []):
        char_a = rc.get("character_a", "")
        char_b = rc.get("character_b", "")
        delta = int(rc.get("delta", 0))
        reason = rc.get("reason", "")
        if char_a and char_b and delta != 0:
            from core.types.state import RelationshipType, RelationshipDelta
            key = ":".join(sorted([char_a, char_b]))
            rel = next((r for r in ws.relationships if r.key == key), None)
            if rel is None:
                rel = RelationshipRecord(character_a=char_a, character_b=char_b, type=RelationshipType.NEUTRAL, strength=0)
                ws.relationships.append(rel)
            rel.strength = max(-100, min(100, rel.strength + delta))
            rel.history.append(RelationshipDelta(chapter=req.chapter, delta=delta, reason=reason))
            if rel.strength >= 50:
                rel.type = RelationshipType.ALLY
            elif rel.strength <= -50:
                rel.type = RelationshipType.ENEMY
            applied["relationships"] += 1

    # 新伏笔
    for h_desc in data.get("hooks_planted", []):
        if h_desc:
            hook = Hook(
                id=f"hook_{uuid.uuid4().hex[:8]}",
                type=HookType.FORESHADOW,
                description=h_desc,
                planted_in_chapter=req.chapter,
                expected_resolution_range=(req.chapter + 3, req.chapter + 25),
                status=HookStatus.OPEN,
            )
            ws.pending_hooks.append(hook)
            applied["hooks"] += 1

    # 信息揭示
    for info in data.get("info_revealed", []):
        char_id = info.get("character") or info.get("character_id", "")
        info_key = info.get("info_key", "")
        info_content = info.get("content", "")
        if char_id and info_key:
            ws.known_info.append({"character_id": char_id, "info_key": info_key, "content": info_content, "learned_in_chapter": req.chapter, "source": "witnessed"})
            applied["info"] += 1

    # 因果链
    cl_data = data.get("causal_link", {})
    if cl_data and cl_data.get("event"):
        cl = CausalLink(
            id=f"cl_{uuid.uuid4().hex[:8]}",
            chapter=req.chapter,
            cause=cl_data.get("cause", ""),
            event=cl_data.get("event", ""),
            consequence=cl_data.get("consequence", ""),
            thread_id=req.thread_id,
        )
        ws.causal_chain.append(cl)
        applied["causal"] += 1

    # 构建角色名 → 线程ID 的映射（用于时间轴事件分配，只匹配已有线程）
    char_to_thread: dict[str, str] = {}
    for t in ws.threads:
        # 通过 pov_character_id 匹配
        if t.pov_character_id:
            char_to_thread[t.pov_character_id] = t.id
        # 通过 character_ids 匹配
        for cid in getattr(t, 'character_ids', []) or []:
            char_to_thread[cid] = t.id
        # 通过线程名中的角色名模糊匹配
        if t.name:
            char_to_thread.setdefault(t.name, t.id)

    # 尝试从章纲获取当前章节的 thread_id（优先于请求参数）
    co_path = sm.state_dir / "chapter_outlines.json"
    if co_path.exists():
        co_data = json.loads(co_path.read_text(encoding="utf-8"))
        for co in co_data:
            if co.get("chapter_number") == req.chapter and co.get("thread_id"):
                req.thread_id = co["thread_id"]
                break

    def _resolve_thread_id(character_name: str) -> str:
        """根据角色名查找对应的线程ID，找不到则回退到章纲线程或默认"""
        if not character_name:
            return req.thread_id
        # 精确匹配
        if character_name in char_to_thread:
            return char_to_thread[character_name]
        # 模糊匹配：角色名包含在线程名或pov中
        for cname, tid in char_to_thread.items():
            if cname in character_name or character_name in cname:
                return tid
        return req.thread_id

    # 时间轴事件
    time_order = float(req.chapter)
    counter = 0
    for ke in data.get("key_events", []):
        counter += 1
        ke_char = ke.get("character") or ke.get("character_id", "")
        event = {
            "id": f"te_{uuid.uuid4().hex[:8]}",
            "chapter": req.chapter,
            "physical_time": "",
            "time_order": time_order + counter * 0.1,
            "character_id": ke_char,
            "location_id": "",
            "action": ke.get("action", ""),
            "type": ke.get("type", "other"),
            "is_key": ke.get("type") == "key",
            "thread_id": _resolve_thread_id(ke_char),
        }
        ws.timeline.append(event)
        applied["timeline"] += 1

    # 更新 current_chapter
    if ws.current_chapter < req.chapter:
        ws.current_chapter = req.chapter

    sm.write_world_state(ws)

    # 更新真相文件
    sm.update_current_state_md()
    if ws.threads:
        sm.update_thread_status_md()

    return {
        "ok": True,
        "chapter": req.chapter,
        "applied": applied,
        "summary": f"提取完成：位置{applied['positions']} 情感{applied['emotions']} 关系{applied['relationships']} 伏笔{applied['hooks']} 信息{applied['info']} 因果{applied['causal']} 时间线{applied['timeline']}",
    }


@app.post("/api/books/{book_id}/extract-story-state/batch")
async def extract_story_state_batch(book_id: str):
    """一键批量提取：自动遍历所有已有章节，逐章提取故事状态数据，已提取的章节跳过"""
    _load_env()
    sm = _sm(book_id)

    # 获取所有已有章节编号
    all_chapters = set()
    for f in sm.chapter_dir.glob("*_final.md"):
        n = int(f.stem.split("_")[0].replace("ch", ""))
        all_chapters.add(n)
    for f in sm.chapter_dir.glob("*_draft.md"):
        n = int(f.stem.split("_")[0].replace("ch", ""))
        all_chapters.add(n)

    if not all_chapters:
        raise HTTPException(404, "没有找到任何章节")

    # 检查哪些章节已经提取过（通过 timeline 中是否存在对应 chapter 的事件）
    ws = sm.read_world_state()
    extracted_chapters = set()
    for te in ws.timeline:
        if isinstance(te, dict):
            extracted_chapters.add(te.get("chapter", 0))
        else:
            extracted_chapters.add(getattr(te, "chapter", 0))

    # 也检查 emotional_snapshots
    for snap in ws.emotional_snapshots:
        if isinstance(snap, dict):
            extracted_chapters.add(snap.get("chapter", 0))
        else:
            extracted_chapters.add(getattr(snap, "chapter", 0))

    to_extract = sorted(ch for ch in all_chapters if ch not in extracted_chapters)

    if not to_extract:
        return {"ok": True, "total": len(all_chapters), "skipped": len(all_chapters),
                "extracted": 0, "failed": 0, "results": [],
                "message": f"所有 {len(all_chapters)} 章均已提取过，无需重复"}

    try:
        llm = _create_llm(temperature=0.2)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    from core.llm import LLMMessage
    from core.types.state import EmotionalSnapshot, CausalLink, Hook, HookType, HookStatus, RelationshipRecord
    import uuid as _uuid

    # 加载角色列表（所有章节共用）
    char_list = []
    try:
        chars_data = sm.read_characters()
        if isinstance(chars_data, dict) and "characters" in chars_data:
            char_list = [c.get("name", "") for c in chars_data["characters"] if c.get("name")]
    except Exception:
        pass
    char_hint = ""
    if char_list:
        char_hint = f"\n已知角色名单：{', '.join(char_list)}\n"

    results = []
    extracted_count = 0

    for ch in to_extract:
        content = sm.read_final(ch) or sm.read_draft(ch)
        if not content:
            results.append({"chapter": ch, "ok": False, "error": "章节文件不存在"})
            break  # 失败就中断

        content_for_llm = content[:8000] + ("\n\n...（截断）" if len(content) > 8000 else "")

        prompt = f"""你是一位小说分析专家。请仔细阅读以下章节正文，提取其中的故事状态变化。
{char_hint}
## 第 {ch} 章正文
{content_for_llm}

请严格按以下 JSON 结构输出（直接输出 JSON，不要任何说明）：

```json
{{
  "position_changes": [
    {{"character": "角色名", "location": "到达地点"}}
  ],
  "emotional_changes": [
    {{"character": "角色名", "emotion": "情感描述", "intensity": 7, "trigger": "触发原因"}}
  ],
  "relationship_changes": [
    {{"character_a": "角色A名", "character_b": "角色B名", "delta": 10, "reason": "变化原因"}}
  ],
  "hooks_planted": [
    "本章埋下的伏笔描述"
  ],
  "hooks_resolved": [
    "本章回收的伏笔描述"
  ],
  "info_revealed": [
    {{"character": "角色名", "info_key": "信息标识", "content": "得知了什么"}}
  ],
  "key_events": [
    {{"action": "事件描述", "character": "主要角色名", "type": "position|emotion|info|conflict|key|other"}}
  ],
  "chapter_main_characters": ["本章主要角色的名字（按出场重要性排序，通常1-3人）"],
  "causal_link": {{
    "cause": "触发原因",
    "event": "核心事件",
    "consequence": "直接后果"
  }}
}}
```

分析要求：
1. position_changes：角色位置发生变化的记录
2. emotional_changes：角色情感明显变化（intensity 1-10，仅>=5）
3. relationship_changes：角色关系变化（delta: -100到+100）
4. hooks_planted：本章新埋下的伏笔
5. hooks_resolved：本章回收的伏笔
6. info_revealed：角色获得新信息
7. key_events：关键事件（type: position/emotion/info/conflict/key/other）
8. chapter_main_characters：本章主要角色（1-3人）
9. causal_link：核心因果关系

重要：所有 character 字段必须填写角色名字，不要填 ID。"""

        try:
            resp = await asyncio.to_thread(
                llm.complete,
                [LLMMessage("system", "你是小说分析专家，擅长从正文提取结构化状态数据。只输出合法 JSON。"), LLMMessage("user", prompt)],
            )
            raw = resp.content.strip()
            if "```json" in raw:
                raw = raw.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in raw:
                raw = raw.split("```", 1)[1].split("```", 1)[0]
            raw = raw.strip()

            import re as _re
            def _repair(text):
                fixed = _re.sub(r',\s*([}\]])', r'\1', text)
                fixed = _re.sub(r'//.*', '', fixed)
                fixed = _re.sub(r'/\*.*?\*/', '', fixed, flags=_re.DOTALL)
                fixed = _re.sub(r"'([^']*)'", r'"\1"', fixed)
                fixed = _re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', fixed)
                fixed = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fixed)
                fixed = _re.sub(r':\s*\+(\d)', r': \1', fixed)
                return fixed

            data = None
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    data = json.loads(_repair(raw))
                except json.JSONDecodeError:
                    from core.llm import _repair_truncated_json
                    try:
                        data = json.loads(_repair(_repair_truncated_json(raw)))
                    except json.JSONDecodeError:
                        results.append({"chapter": ch, "ok": False, "error": "JSON 解析失败"})
                        break  # 失败就中断

            if data is None:
                results.append({"chapter": ch, "ok": False, "error": "JSON 解析结果为空"})
                break

            # 应用到 world_state（和单章提取逻辑一致）
            ws = sm.read_world_state()
            applied = {"emotions": 0, "positions": 0, "relationships": 0, "hooks": 0, "timeline": 0, "info": 0, "causal": 0}

            for pc in data.get("position_changes", []):
                char_id = pc.get("character") or pc.get("character_id", "")
                loc = pc.get("location", "")
                if char_id and loc:
                    ws.character_positions[char_id] = loc
                    applied["positions"] += 1

            for ec in data.get("emotional_changes", []):
                char_id = ec.get("character") or ec.get("character_id", "")
                if not char_id:
                    continue
                snap = EmotionalSnapshot(
                    character_id=char_id,
                    emotion=ec.get("emotion", "未知"),
                    intensity=int(ec.get("intensity", 5)),
                    chapter=ch,
                    trigger=ec.get("trigger", ""),
                )
                ws.emotional_snapshots.append(snap)
                applied["emotions"] += 1

            for rc in data.get("relationship_changes", []):
                a = rc.get("character_a", "")
                b = rc.get("character_b", "")
                if a and b:
                    delta_val = int(rc.get("delta", 0))
                    reason = rc.get("reason", "")
                    from core.types.state import RelationshipType, RelationshipDelta as RelDelta
                    key = ":".join(sorted([a, b]))
                    rel = next((r for r in ws.relationships if r.key == key), None)
                    if rel is None:
                        rel = RelationshipRecord(character_a=a, character_b=b, type=RelationshipType.NEUTRAL, strength=0)
                        ws.relationships.append(rel)
                    rel.strength = max(-100, min(100, rel.strength + delta_val))
                    rel.history.append(RelDelta(chapter=ch, delta=delta_val, reason=reason))
                    if rel.strength >= 50:
                        rel.type = RelationshipType.ALLY
                    elif rel.strength <= -50:
                        rel.type = RelationshipType.RIVAL
                    applied["relationships"] += 1

            for h_desc in data.get("hooks_planted", []):
                if not h_desc or not h_desc.strip():
                    continue
                hook = Hook(
                    id=f"hook_{_uuid.uuid4().hex[:8]}",
                    type=HookType.FORESHADOW,
                    description=str(h_desc).strip(),
                    planted_in_chapter=ch,
                    expected_resolution_range=(ch + 3, ch + 25),
                    status=HookStatus.OPEN,
                )
                ws.pending_hooks.append(hook)
                applied["hooks"] += 1

            for info in data.get("info_revealed", []):
                char_id = info.get("character") or info.get("character_id", "")
                info_key = info.get("info_key", "")
                info_content = info.get("content", "")
                if char_id and info_key:
                    ws.known_info.append({"character_id": char_id, "info_key": info_key, "content": info_content, "learned_in_chapter": ch, "source": "witnessed"})
                    applied["info"] += 1

            cl_data = data.get("causal_link", {})
            if cl_data and cl_data.get("event"):
                cl = CausalLink(
                    id=f"cl_{_uuid.uuid4().hex[:8]}",
                    chapter=ch,
                    cause=cl_data.get("cause", ""),
                    event=cl_data.get("event", ""),
                    consequence=cl_data.get("consequence", ""),
                    thread_id="thread_main",
                )
                ws.causal_chain.append(cl)
                applied["causal"] += 1

            # 时间轴事件
            char_to_thread = {}
            for t in ws.threads:
                if t.pov_character_id:
                    char_to_thread[t.pov_character_id] = t.id
                for cid in getattr(t, 'character_ids', []) or []:
                    char_to_thread[cid] = t.id
                if t.name:
                    char_to_thread.setdefault(t.name, t.id)

            main_chars = data.get("chapter_main_characters", [])
            for mc in main_chars:
                mc_stripped = mc.strip()
                if not mc_stripped:
                    continue
                if mc_stripped not in char_to_thread:
                    new_thread_id = f"thread_{mc_stripped}"
                    existing_ids = {t.id for t in ws.threads}
                    if new_thread_id in existing_ids:
                        new_thread_id = f"thread_{mc_stripped}_{_uuid.uuid4().hex[:4]}"
                    from core.types.narrative import NarrativeThread, ThreadType
                    new_thread = NarrativeThread(
                        id=new_thread_id, name=f"{mc_stripped}线",
                        type=ThreadType.SUBPLOT if len(ws.threads) > 0 else ThreadType.MAIN,
                        pov_character_id=mc_stripped,
                        start_chapter=ch, last_active_chapter=ch,
                        goal="", growth_arc="", weight=0.5, status="active",
                        character_ids=[], end_hook="",
                    )
                    ws.threads.append(new_thread)
                    char_to_thread[mc_stripped] = new_thread_id

            def _resolve_tid(character_name: str) -> str:
                if not character_name:
                    return "thread_main"
                if character_name in char_to_thread:
                    return char_to_thread[character_name]
                for cn, tid in char_to_thread.items():
                    if cn in character_name or character_name in cn:
                        return tid
                return "thread_main"

            time_order = float(ch)
            counter = 0
            for ke in data.get("key_events", []):
                counter += 1
                ke_char = ke.get("character") or ke.get("character_id", "")
                event = {
                    "id": f"te_{_uuid.uuid4().hex[:8]}",
                    "chapter": ch,
                    "physical_time": "",
                    "time_order": time_order + counter * 0.1,
                    "character_id": ke_char,
                    "location_id": "",
                    "action": ke.get("action", ""),
                    "type": ke.get("type", "other"),
                    "thread_id": _resolve_tid(ke_char),
                }
                ws.timeline.append(event)
                applied["timeline"] += 1

            # 回收伏笔
            for h_desc in data.get("hooks_resolved", []):
                h_desc_stripped = str(h_desc).strip()
                if not h_desc_stripped:
                    continue
                for hook in ws.pending_hooks:
                    if hook.status == HookStatus.OPEN and h_desc_stripped in hook.description:
                        hook.status = HookStatus.RESOLVED
                        hook.resolved_in_chapter = ch

            if ws.current_chapter < ch:
                ws.current_chapter = ch

            sm.write_world_state(ws)
            sm.update_current_state_md()
            if ws.threads:
                sm.update_thread_status_md()

            summary = f"位置{applied['positions']} 情感{applied['emotions']} 关系{applied['relationships']} 伏笔{applied['hooks']} 信息{applied['info']} 因果{applied['causal']} 时间线{applied['timeline']}"
            results.append({"chapter": ch, "ok": True, "summary": summary})
            extracted_count += 1

        except Exception as e:
            results.append({"chapter": ch, "ok": False, "error": str(e)})
            break  # 失败就中断

    skipped = len(all_chapters) - len(to_extract)
    failed = sum(1 for r in results if not r["ok"])
    return {
        "ok": failed == 0,
        "total": len(all_chapters),
        "skipped": skipped,
        "extracted": extracted_count,
        "failed": failed,
        "results": results,
        "message": f"完成：{extracted_count} 章提取成功，{skipped} 章已跳过，{failed} 章失败",
    }


@app.post("/api/books/{book_id}/ai-generate/outline")
async def ai_generate_outline(book_id: str, req: AiGenerateOutlineReq):
    """AI 生成故事大纲（或基于已有配置重新生成）"""
    _load_env()
    from core.setup import SetupLoader
    from core.llm import LLMMessage

    try:
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    protagonist = state.characters.get(state.config.protagonist_id)
    pname = protagonist.name if protagonist else "主角"
    p_need = protagonist.need.external if protagonist else "未知"
    p_internal = protagonist.need.internal if protagonist else "未知"

    char_summary = "\n".join(
        f"- {c.name}（{c.id}）：外部目标={c.need.external}，弧线={c.arc}"
        for c in state.characters.values()
    )
    event_summary = "\n".join(
        f"- {e.name}（第{e.suggested_act}幕，{e.suggested_function.value if e.suggested_function else '未知'}）：{e.description}"
        for e in state.seed_events
    )

    prompt = f"""\
请为以下小说生成三幕结构大纲 JSON。

## 小说信息
- 书名：{state.config.title}
- 题材：{state.config.genre}
- 总章数：{state.config.target_chapters}
- 用户想法：{req.idea or '（按种子事件自然发展）'}

## 角色
{char_summary}

## 种子事件
{event_summary}

## 主角
- 姓名：{pname}
- 外部目标：{p_need}
- 内在渴望：{p_internal}

## 关键事件（key_events）生成要求（★★★★★ 必须严格遵守）
⚠️ **严重警告**：每个序列的 `key_events` 数组必须包含**恰好等于 estimated_scenes 数量**的不同关键事件！

### 事件类型要求：
- 每个事件类型必须符合 {state.config.genre} 题材的世界观
- 事件类型必须覆盖冲突、成长、反转、揭秘等故事要素
- 事件类型必须使用不同的动词和名词组合，避免重复

### 错误示例（禁止使用）：
- ❌ "key_events": ["关键事件1", "关键事件2"]（数量不足）
- ❌ "key_events": ["冲突爆发", "冲突升级", "冲突化解"]（动词重复）
- ❌ "key_events": ["事件1", "事件2", "事件3"]（过于笼统）

### 正确示例：
- ✅ "key_events": ["职场博弈", "商业谈判", "创业逆袭", "豪门恩怨", "商业间谍"]（5个事件，estimated_scenes=5）
- ✅ "key_events": ["功法突破", "秘境探险", "宗门斗争", "神兽契约", "丹道炼丹", "器道炼器"]（6个事件，estimated_scenes=6）

请严格按以下 JSON 结构输出（所有字段都必须有）：
```json
{{
  "id": "{state.config.id}_outline",
  "title": "大纲标题（一句话概括核心冲突）",
  "logline": "Logline（30字以内）",
  "genre": "{state.config.genre}",
  "sequences": [
    {{
      "id": "seq_001",
      "number": 1,
      "act": 1,
      "summary": "序列摘要（50-100字）",
      "narrative_goal": "这个序列的叙事目标",
      "dramatic_function": "setup",
      "key_events": ["关键事件1", "关键事件2", "关键事件3"],  // 数量必须等于 estimated_scenes
      "estimated_scenes": 3,
      "end_hook": "序列结尾钩子"
    }}
  ]
}}
```

dramatic_function 只能使用以下值：
- setup（铺垫）、inciting（激励事件）、turning（转折点）、midpoint（中点）、crisis（危机）、climax（高潮）、reveal（揭示）、decision（抉择）、consequence（后果）、transition（过渡）

要求：
1. 自动按 25%/50%/25% 分配三幕章数
2. 每幕 2-3 个序列，总计 6-10 个序列
3. estimated_scenes 的总和必须精确等于 {state.config.target_chapters}
4. 必须覆盖：setup、inciting、turning、midpoint、crisis、climax、consequence
5. 每个序列必须有唯一的 id（格式 seq_001, seq_002 ...）
6. 每个序列的 estimated_scenes 至少为 1，不能为 0
7. **每个序列的 key_events 数量必须等于 estimated_scenes，且每个事件都必须独特**"""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是故事架构师，只输出合法 JSON。"), LLMMessage("user", prompt)],
        )
        content = resp.content.strip()
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]
        data = json.loads(content)
        return {"ok": True, "data": data}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 输出解析失败：{e}", "raw": content[-500:] if content else ""}
    except Exception as e:
        raise HTTPException(500, f"AI 生成失败：{e}")


@app.post("/api/books/{book_id}/ai-continue/outline")
async def ai_continue_outline(book_id: str, req: AiContinueOutlineReq):
    """AI 续写故事大纲：在已有大纲基础上追加新序列"""
    _load_env()
    from core.setup import SetupLoader
    from core.llm import LLMMessage

    sm = _sm(book_id)
    outline_path = sm.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "请先生成大纲")

    existing = json.loads(outline_path.read_text(encoding="utf-8"))
    existing_seqs = existing.get("sequences", [])
    existing_total_scenes = sum(s.get("estimated_scenes", 0) for s in existing_seqs)

    try:
        cfg_data = sm.read_config()
    except FileNotFoundError:
        raise HTTPException(404, "书籍不存在")

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    # 构建已有大纲摘要
    seq_summary = "\n".join(
        f"序列{s.get('number',i+1)}（第{s.get('act','?')}幕）：{s.get('summary','')} | 结尾钩子：{s.get('end_hook','')}"
        for i, s in enumerate(existing_seqs)
    )

    prompt = f"""\
你是一位故事架构师。请在已有大纲基础上，续写 {req.extra_sequences} 个新序列。

## 小说信息
- 书名：{cfg_data.get('title','未命名')}
- 题材：{cfg_data.get('genre','玄幻')}
- 用户想法：{req.idea or '（按剧情自然发展）'}

## 已有大纲（{len(existing_seqs)} 个序列，{existing_total_scenes} 章）
{seq_summary}

## 续写要求
1. 追加 {req.extra_sequences} 个序列，编号从 {len(existing_seqs)+1} 开始
2. 必须衔接最后一个序列的 end_hook
3. 每个序列 estimated_scenes 建议 5-15 章
4. 必须包含：setup/inciting/turning/midpoint/crisis/climax/consequence 等戏剧功能
5. 每个序列必须有 end_hook 制造悬念

请输出一个 JSON 数组，包含 {req.extra_sequences} 个序列，格式：
```json
[
  {{
    "id": "seq_{len(existing_seqs)+1:03d}",
    "number": {len(existing_seqs)+1},
    "act": 2,
    "summary": "序列摘要",
    "narrative_goal": "叙事目标",
    "dramatic_function": "turning",
    "key_events": ["事件1"],
    "estimated_scenes": 8,
    "end_hook": "结尾钩子"
  }}
]
```
只输出 JSON 数组，不要任何说明。"""

    try:
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("system", "你是故事架构师，只输出合法 JSON 数组。"), LLMMessage("user", prompt)],
        )
        content = resp.content.strip()
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]
        new_seqs = json.loads(content.strip())
        if not isinstance(new_seqs, list):
            new_seqs = [new_seqs]
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"AI 输出解析失败：{e}", "raw": content[-500:] if content else ""}
    except Exception as e:
        raise HTTPException(500, f"AI 续写失败：{e}")

    # 修正编号并追加
    for i, seq in enumerate(new_seqs):
        seq["id"] = f"seq_{len(existing_seqs)+i+1:03d}"
        seq["number"] = len(existing_seqs) + i + 1
        # 修正 dramatic_function
        df = seq.get("dramatic_function", "transition")
        seq["dramatic_function"] = _DF_MAP.get(df, df)

    existing["sequences"].extend(new_seqs)
    # 为每个序列补充 key_events，确保数量足够
    for seq in existing["sequences"]:
        if "key_events" not in seq:
            seq["key_events"] = []
        # 需要补充到 estimated_scenes 的数量
        needed = max(seq.get("estimated_scenes", 5), len(seq["key_events"]))
        while len(seq["key_events"]) < needed:
            # 从 summary 和 narrative_goal 中提取
            summary = seq.get("summary", "")
            goal = seq.get("narrative_goal", "")
            suffix = f"事件{len(seq['key_events']) + 1}"
            # 用不同位置的字符拼凑
            start = (len(seq["key_events"]) * 7) % max(len(summary + goal), 1)
            new_event = f"{summary[start:start+3]}{goal[start+3:start+6]}{suffix}"
            if new_event not in seq["key_events"]:
                seq["key_events"].append(new_event)
            else:
                seq["key_events"].append(f"剧情转折{len(seq['key_events']) + 1}")
    # 回写
    outline_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新 target_chapters
    new_total = sum(s.get("estimated_scenes", 0) for s in existing["sequences"])
    cfg_data["target_chapters"] = new_total
    sm._write_json("config.json", cfg_data)

    return {"ok": True, "data": existing, "added": len(new_seqs), "new_total_chapters": new_total}

@app.post("/api/books/{book_id}/ai-generate/chapter-outlines")
async def ai_generate_chapter_outlines(book_id: str):
    """基于已有大纲生成全部章纲"""
    _load_env()
    from core.setup import SetupLoader
    from core.narrative import NarrativeEngine, StoryOutlineSchema

    sm = _sm(book_id)
    outline_path = sm.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "请先生成大纲")

    try:
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    # 读取大纲 JSON 并规范化后再验证
    outline_raw = json.loads(outline_path.read_text(encoding="utf-8"))
    outline_raw = _normalize_outline(outline_raw, sm)
    outline = StoryOutlineSchema.model_validate_json(json.dumps(outline_raw, ensure_ascii=False))
    protagonist = state.characters.get(state.config.protagonist_id)
    if protagonist is None:
        for ch in state.characters.values():
            if getattr(ch, "role", None) == "protagonist":
                protagonist = ch
                break
    if protagonist is None:
        protagonist = next(iter(state.characters.values()), None)
    if protagonist is None:
        raise HTTPException(400, "未找到主角角色信息，请检查角色配置")
    engine = NarrativeEngine(llm)

    try:
        all_outlines = []
        ch_start = 1
        previous_chapter_titles: list[str] = []
        for seq in outline.sequences:
            cos = await asyncio.to_thread(
                engine.generate_chapter_outlines,
                seq, protagonist,
                sm.read_truth("story_bible"),
                ch_start,
                state.config.target_words_per_chapter,
                None,
                previous_chapter_titles,
                genre=state.config.genre,
                use_predefined_events=getattr(state.config, "use_predefined_events", True),
            )
            all_outlines.extend(cos)
            ch_start += len(cos)
            # 收集已生成的章节标题，供后续序列防重
            previous_chapter_titles.extend(co.title for co in cos)

        # ═══════════════════════════════════════════════════════════════════════
        # 标题多样性强制优化（独立于事件词汇库，完全基于摘要内容）
        # ═══════════════════════════════════════════════════════════════════════
        
        # 定义模式化词汇列表（硬编码，不依赖词汇库）
        GENERIC_PATTERNS = ["危机", "秘闻", "奇遇", "风波", "冒险", "探险", "秘密", "真相", "对决", "战斗", 
                          "冲突", "阴谋", "陷阱", "危机", "挑战", "考验", "试炼", "磨难", "劫难"]
        
        # 定义丰富的替代词汇（用于重构标题）
        RICH_VERBS = ["觉醒", "突破", "蜕变", "逆袭", "逆转", "爆发", "崛起", "陨落", "复苏", "进化",
                     "揭秘", "揭露", "发现", "洞察", "识破", "追踪", "搜寻", "探索", "挖掘", "揭晓",
                     "交锋", "对决", "博弈", "较量", "抗衡", "争锋", "鏖战", "血战", "激战", "死斗",
                     "潜入", "突袭", "营救", "突围", "截杀", "埋伏", "刺杀", "追杀", "奔袭", "猛攻"]
        
        RICH_STATES = ["骤变", "惊变", "异变", "突变", "剧变", "逆转", "逆袭", "突破", "觉醒", "爆发",
                      "崩塌", "瓦解", "粉碎", "破灭", "毁灭", "重建", "复兴", "崛起", "陨落", "复苏"]
        
        def extract_title_elements(summary: str) -> dict:
            """从摘要中提取可用于构建标题的元素"""
            elements = {}
            
            # 1. 提取人名（常见姓氏）
            elements["names"] = re.findall(r'[林苏沈顾陆叶萧楚秦韩赵魏齐周吴郑王刘陈杨张黄何郭罗马][^\s,，.。！？]{0,2}', summary)
            
            # 2. 提取地点/组织/场景
            elements["locations"] = re.findall(
                r'(?:事务局|研究所|基地|学院|宗门|秘境|遗迹|古城|废墟|洞穴|森林|山脉|海域|岛屿|宫殿|府邸|公司|集团|部门|团队|小组)', 
                summary
            )
            
            # 3. 提取关键动作
            elements["actions"] = re.findall(
                r'(?:觉醒|突破|发现|遭遇|击败|获得|揭露|对决|逃离|潜入|营救|调查|探索|进入|离开|追击|反击|防守|进攻|撤退)', 
                summary
            )
            
            # 4. 提取关键物品/概念
            elements["objects"] = re.findall(
                r'(?:神器|法宝|丹药|功法|秘籍|传承|线索|证据|真相|秘密|阴谋|计划|方案|策略|情报|消息)', 
                summary
            )
            
            # 5. 提取情感/状态词
            elements["emotions"] = re.findall(
                r'(?:愤怒|悲伤|喜悦|恐惧|绝望|希望|决心|勇气|信念|意志|愤怒|震惊|惊讶|疑惑)', 
                summary
            )
            
            return elements
        
        def generate_unique_title(chapter_num: int, summary: str, used_patterns: dict, existing_titles: set) -> str:
            """基于摘要内容生成唯一标题"""
            elements = extract_title_elements(summary)
            
            # 优先级1: 人名 + 动作
            if elements["names"] and elements["actions"]:
                base = f"{elements['names'][0]}{elements['actions'][0][:2]}"
            
            # 优先级2: 地点 + 动作
            elif elements["locations"] and elements["actions"]:
                base = f"{elements['locations'][0][:3]}{elements['actions'][0][:2]}"
            
            # 优先级3: 人名 + 状态词
            elif elements["names"]:
                verb = RICH_VERBS[len(used_patterns) % len(RICH_VERBS)]
                base = f"{elements['names'][0]}{verb[:2]}"
            
            # 优先级4: 动作 + 物品
            elif elements["actions"] and elements["objects"]:
                base = f"{elements['actions'][0][:2]}{elements['objects'][0][:2]}"
            
            # 优先级5: 状态词
            elif elements["actions"]:
                base = elements["actions"][0][:4]
            
            # 优先级6: 使用丰富的替代词汇
            else:
                state = RICH_STATES[len(used_patterns) % len(RICH_STATES)]
                base = state
            
            title = f"第{chapter_num}章-{base}"
            
            # 确保唯一性
            counter = 0
            while title in existing_titles:
                suffix = RICH_VERBS[counter % len(RICH_VERBS)]
                title = f"第{chapter_num}章-{base}{suffix[:2]}"
                counter += 1
                if counter > 10:
                    title = f"第{chapter_num}章-{base}[{counter}]"
                    break
            
            return title
        
        # ── 第一层：检测并替换模式化词汇 ───────────────────────────────────────
        pattern_counts: dict[str, int] = {}
        existing_titles = set()
        
        for o in all_outlines:
            existing_titles.add(o.title)
            for pattern in GENERIC_PATTERNS:
                if pattern in o.title:
                    if pattern not in pattern_counts:
                        pattern_counts[pattern] = 0
                    pattern_counts[pattern] += 1
                    
                    # 如果同一模式出现超过 1 次，强制重构标题
                    if pattern_counts[pattern] > 1:
                        new_title = generate_unique_title(
                            o.chapter_number, 
                            o.summary, 
                            pattern_counts, 
                            existing_titles
                        )
                        existing_titles.discard(o.title)  # 移除旧标题
                        o.title = new_title
                        existing_titles.add(new_title)  # 添加新标题
                        break
        
        # ── 第二层：检测重复结尾词并优化 ───────────────────────────────────────
        ending_pattern = re.compile(r'[-_](.+)$')
        ending_counts: dict[str, list] = {}
        
        for o in all_outlines:
            match = ending_pattern.search(o.title)
            ending = match.group(1) if match else o.title[-2:] if len(o.title) >= 2 else o.title
            if ending not in ending_counts:
                ending_counts[ending] = []
            ending_counts[ending].append(o)
        
        # 对重复的结尾词，强制优化
        for ending, chapters in ending_counts.items():
            if len(chapters) > 1:
                for i, o in enumerate(chapters[1:], start=2):
                    new_title = generate_unique_title(
                        o.chapter_number,
                        o.summary,
                        {"ending": i},
                        existing_titles
                    )
                    existing_titles.discard(o.title)
                    o.title = new_title
                    existing_titles.add(new_title)
        
        # ── 第三层：最终去重校验 ───────────────────────────────────────────────
        final_titles: set[str] = set()
        for o in all_outlines:
            original = o.title
            counter = 0
            while o.title in final_titles:
                # 使用丰富的后缀
                suffix = RICH_STATES[counter % len(RICH_STATES)]
                o.title = f"{original}·{suffix[:2]}"
                counter += 1
                if counter > 20:
                    o.title = f"{original}[{counter}]"
                    break
            final_titles.add(o.title)

        result_data = [o.model_dump() for o in all_outlines]
        path = sm.state_dir / "chapter_outlines.json"
        path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "count": len(all_outlines), "outlines": result_data}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"章纲生成失败：{e}")


@app.get("/api/books/{book_id}/ai-generate/chapter-outlines/stream")
async def ai_generate_chapter_outlines_stream(book_id: str):
    """基于已有大纲生成全部章纲（SSE实时进度）"""
    _load_env()
    from core.setup import SetupLoader
    from core.narrative import NarrativeEngine, StoryOutlineSchema

    sm = _sm(book_id)
    outline_path = sm.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "请先生成大纲")

    try:
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    # 读取大纲 JSON 并规范化后再验证
    outline_raw = json.loads(outline_path.read_text(encoding="utf-8"))
    outline_raw = _normalize_outline(outline_raw, sm)
    outline = StoryOutlineSchema.model_validate_json(json.dumps(outline_raw, ensure_ascii=False))
    protagonist = state.characters.get(state.config.protagonist_id)
    if protagonist is None:
        for ch in state.characters.values():
            if getattr(ch, "role", None) == "protagonist":
                protagonist = ch
                break
    if protagonist is None:
        protagonist = next(iter(state.characters.values()), None)
    if protagonist is None:
        raise HTTPException(400, "未找到主角角色信息，请检查角色配置")
    engine = NarrativeEngine(llm)

    async def event_generator():
        try:
            # 在内部定义所有变量，避免闭包作用域问题
            total_sequences_local = len(outline.sequences)
            total_chapters_local = sum(seq.estimated_scenes for seq in outline.sequences)
            chapters_completed_total = 0
            all_outlines = []
            ch_start = 1
            previous_chapter_titles: list[str] = []
            
            # 获取当前事件循环（必须在主线程中获取）
            loop = asyncio.get_running_loop()
            
            # 初始化进度
            yield f"data: {json.dumps({'stage': 'init', 'message': '准备开始生成章节大纲...', 'total_sequences': total_sequences_local, 'total_chapters': total_chapters_local}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            for seq_idx, seq in enumerate(outline.sequences):
                current_sequence = seq_idx + 1
                # SequenceSchema 没有 name 属性，使用 summary 或默认名称
                seq_name = f"序列{current_sequence}"
                if hasattr(seq, 'summary') and seq.summary:
                    # 使用 summary 的前20个字符作为显示名称
                    seq_name = seq.summary[:20] + ("..." if len(seq.summary) > 20 else "")
                
                # 通知开始处理新序列
                msg = f'开始处理「{seq_name}」（{seq.estimated_scenes}章）...'
                yield f"data: {json.dumps({
                    'stage': 'sequence_start',
                    'sequence_index': current_sequence,
                    'total_sequences': total_sequences_local,
                    'sequence_name': seq_name,
                    'sequence_chapters': seq.estimated_scenes,
                    'message': msg
                }, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)

                # 进度回调队列
                progress_queue = asyncio.Queue()
                cur_chapters_before = chapters_completed_total

                # 使用类实例来保存状态，避免闭包问题
                class ProgressState:
                    def __init__(self, seq_num, chapters_before, total_seqs, total_chaps, event_loop, queue):
                        self.seq_num = seq_num
                        self.chapters_before = chapters_before
                        self.total_seqs = total_seqs
                        self.total_chaps = total_chaps
                        self.loop = event_loop
                        self.queue = queue
                
                state_obj = ProgressState(current_sequence, cur_chapters_before, total_sequences_local, total_chapters_local, loop, progress_queue)
                
                def progress_callback(data):
                    # 计算总体进度
                    data['sequence_index'] = state_obj.seq_num
                    data['total_sequences'] = state_obj.total_seqs
                    data['chapters_completed_total'] = state_obj.chapters_before + data['chapters_completed']
                    data['total_chapters'] = state_obj.total_chaps
                    # 使用预存的事件循环引用
                    asyncio.run_coroutine_threadsafe(state_obj.queue.put(data), state_obj.loop)

                # 在独立线程中执行生成
                cos = await asyncio.to_thread(
                    engine.generate_chapter_outlines,
                    seq, protagonist,
                    sm.read_truth("story_bible"),
                    ch_start,
                    state.config.target_words_per_chapter,
                    progress_callback,
                    previous_chapter_titles,
                    genre=state.config.genre,  # 传递书籍题材
                )
                
                # 从队列中读取进度更新
                while not progress_queue.empty():
                    try:
                        data = progress_queue.get_nowait()
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                all_outlines.extend(cos)
                chapters_completed_total += len(cos)
                ch_start += len(cos)
                # 收集已生成的章节标题，供后续序列防重
                previous_chapter_titles.extend(co.title for co in cos)

                # 通知序列完成
                yield f"data: {json.dumps({
                    'stage': 'sequence_complete',
                    'sequence_index': current_sequence,
                    'total_sequences': total_sequences_local,
                    'sequence_name': seq_name,
                    'chapters_completed': chapters_completed_total,
                    'total_chapters': total_chapters_local,
                    'message': f'「{seq_name}」处理完成（{len(cos)}章）'
                }, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)

            # 最终去重校验：如果仍有重复标题，用有意义的后缀替换，避免简单编号
            seen_titles: dict[str, int] = {}
            unique_suffixes = ["风波", "危机", "秘闻", "奇遇", "决战", "逆袭", "阴谋", "真相", "抉择", "转折"]
            for o in all_outlines:
                original = o.title
                while o.title in seen_titles:
                    # 使用有意义的后缀，而不是简单的数字编号
                    count = seen_titles[original]
                    suffix = unique_suffixes[count % len(unique_suffixes)]
                    o.title = f"{original[:-2] if '章-' in original else original}{suffix}"
                seen_titles[original] = seen_titles.get(original, 0) + 1
                seen_titles[o.title] = 1

            # 保存结果
            result_data = [o.model_dump() for o in all_outlines]
            path = sm.state_dir / "chapter_outlines.json"
            path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
            
            # 完成通知
            yield f"data: {json.dumps({
                'stage': 'complete',
                'count': len(all_outlines),
                'outlines': result_data,
                'message': f'成功生成 {len(all_outlines)} 章大纲！'
            }, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f'生成失败：{str(e)}'
            yield f"data: {json.dumps({'stage': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ── /api/action/*  三层审计 ───────────────────────────────────────────────────

@app.post("/api/books/{book_id}/three-layer-audit")
async def three_layer_audit(book_id: str, req: ThreeLayerAuditReq):
    """三层审计：语言层 + 结构层 + 戏剧层"""
    _load_env()
    sm = _sm(book_id)
    content = sm.read_final(req.chapter) or sm.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {req.chapter} 章不存在")

    from core.agents import AuditorAgent, ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
    from core.types.state import TruthFileKey

    blueprint = ArchitectBlueprint(
        core_conflict="", hooks_to_advance=[], hooks_to_plant=[],
        emotional_journey={}, chapter_end_hook="", pace_notes="",
        pre_write_checklist=PreWriteChecklist([], [], [], [], ""),
    )

    mode = req.mode
    results = {}

    try:
        llm_audit = _create_llm(temperature=0.0, model_env="AUDITOR_MODEL")

        # ── 语言层（复用现有 Validator + 审计员的去AI味/连续性维度）──
        if mode in ("language", "full"):
            from core.validators import PostWriteValidator
            cfg = sm.read_config()
            validator = PostWriteValidator(cfg.get("custom_forbidden_words", []))
            v_result = validator.validate(content, target_words=5000)
            lang_issues = []
            for v in v_result.issues:
                lang_issues.append({
                    "layer": "language",
                    "dimension": v.rule,
                    "severity": "critical" if v.severity == "error" else "warning",
                    "description": v.description,
                    "excerpt": v.excerpt or "",
                    "suggestion": "",
                })
            results["language"] = {"issues": lang_issues, "passed": all(i["severity"] != "critical" for i in lang_issues)}

        # ── 结构层 + 戏剧层（LLM 审计，分维度归类）──
        if mode in ("structure", "drama", "full"):
            truth_ctx = sm.read_truth_bundle([
                TruthFileKey.CURRENT_STATE, TruthFileKey.PENDING_HOOKS,
                TruthFileKey.CHARACTER_MATRIX, TruthFileKey.CAUSAL_CHAIN,
            ])
            auditor = AuditorAgent(llm_audit)
            report = await asyncio.to_thread(
                auditor.audit_chapter,
                content, req.chapter, blueprint, truth_ctx,
                PostWriteSettlement([], [], [], [], []),
            )
            # 分类到结构层和戏剧层
            structure_dims = {"大纲偏离", "节奏", "结尾钩子"}
            drama_dims = {"OOC（角色行为是否符合性格锁定，性格锁定的事绝对不能做）",
                          "情感弧线", "冲突质量", "信息边界", "因果一致性", "伏笔管理"}

            struct_issues = [i for i in report.issues if i.dimension in structure_dims]
            drama_issues = [i for i in report.issues if i.dimension in drama_dims]

            if mode in ("structure", "full"):
                results["structure"] = {
                    "issues": [_dc_to_dict(i) for i in struct_issues],
                    "passed": not any(i.severity == "critical" for i in struct_issues),
                }
            if mode in ("drama", "full"):
                results["drama"] = {
                    "issues": [_dc_to_dict(i) for i in drama_issues],
                    "passed": not any(i.severity == "critical" for i in drama_issues),
                }

        overall_passed = all(r.get("passed", True) for r in results.values())
        total_critical = sum(len([i for i in r["issues"] if i.get("severity") == "critical"]) for r in results.values())
        total_warning = sum(len([i for i in r["issues"] if i.get("severity") == "warning"]) for r in results.values())

        result_data = {
            "ok": True,
            "passed": overall_passed,
            "chapter": req.chapter,
            "layers": results,
            "summary": f"Critical: {total_critical}  Warning: {total_warning}  {'通过' if overall_passed else '未通过'}",
        }

        # 持久化审计结果
        audit_dir = sm.state_dir / "audit_results"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"ch{req.chapter:04d}.json"
        saved = {
            "chapter": req.chapter,
            "passed": overall_passed,
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "layers": results,
            "summary": result_data["summary"],
        }
        audit_file.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")

        return result_data
    except Exception as e:
        raise HTTPException(500, f"审计失败：{e}")


@app.post("/api/action/revise")
def action_revise(book_id: str, chapter: int, mode: str = "spot-fix"):
    """手动修订指定章节"""
    _load_env()
    try:
        import sys
        from subprocess import Popen, PIPE, STDOUT
        import threading
        
        cmd = [sys.executable, "-m", "cli.main", "revise", book_id, str(chapter), "--mode", mode]
        
        process = Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
            bufsize=1,
            universal_newlines=True
        )
        
        stdout_output = []
        
        def read_output():
            try:
                for line in process.stdout:
                    print(line, end="")
                    stdout_output.append(line)
            except Exception as e:
                pass
        
        read_thread = threading.Thread(target=read_output)
        read_thread.daemon = True
        read_thread.start()
        
        timeout = 600  # 10分钟
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            read_thread.join(timeout=1)
            return {"ok": False, "stdout": "", "stderr": "修订超时"}
        
        read_thread.join(timeout=5)
        
        stdout_str = "".join(stdout_output)
        stderr_str = ""
        
        return {"ok": process.returncode == 0, "stdout": stdout_str[-2000:], "stderr": stderr_str[-1000:]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "stdout": "", "stderr": f"执行出错：{str(e)}"}


# ── 质量评估 API ────────────────────────────────────────────────────────────

class QualityAssessmentReq(BaseModel):
    chapter: int
    mode: Literal["full", "dimensions", "consistency", "genre"] = "full"


@app.post("/api/books/{book_id}/quality/evaluate")
async def quality_evaluate(book_id: str, req: QualityAssessmentReq):
    """质量评估：六维评分 + 连贯性检测 + 类型适配度评估"""
    _load_env()
    sm = _sm(book_id)
    
    # 读取章节内容
    content = sm.read_final(req.chapter) or sm.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {req.chapter} 章不存在")
    
    # 读取前一章内容（用于连贯性检测）
    prev_content = ""
    if req.chapter > 1:
        prev_content = sm.read_final(req.chapter - 1) or sm.read_draft(req.chapter - 1) or ""
    
    # 读取配置
    cfg = sm.read_config()
    genre = cfg.get("genre", "general")
    
    try:
        from core.agents import QualityAgent
        from core.types.state import TruthFileKey
        
        # 创建 QualityAgent
        llm = _create_llm(temperature=0.0, model_env="AUDITOR_MODEL")
        quality_agent = QualityAgent(llm)
        
        # 读取必要的上下文
        truth_ctx = sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE, TruthFileKey.PENDING_HOOKS,
            TruthFileKey.CHARACTER_MATRIX, TruthFileKey.CAUSAL_CHAIN,
            TruthFileKey.CHAPTER_SUMMARIES,
        ])
        
        from core.agents import ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
        
        blueprint = ArchitectBlueprint(
            core_conflict="", hooks_to_advance=[], hooks_to_plant=[],
            emotional_journey={}, chapter_end_hook="", pace_notes="",
            pre_write_checklist=PreWriteChecklist([], [], [], [], ""),
        )
        
        # 执行质量评估
        report = await asyncio.to_thread(
            quality_agent.evaluate_chapter,
            chapter_content=content,
            chapter_number=req.chapter,
            genre=genre,
            blueprint=blueprint,
            truth_context=truth_ctx,
            settlement=PostWriteSettlement([], [], [], [], []),
            prev_chapter_content=prev_content[-800:] if prev_content else "",
            auto_revise=False,
        )
        
        # 如果是 tuple，取第二个元素（质量报告）
        if isinstance(report, tuple):
            revised_content, report = report
        
        # 转换为字典格式
        report_dict = _dc_to_dict(report)
        
        # 持久化评估结果
        quality_dir = sm.state_dir / "quality_results"
        quality_dir.mkdir(parents=True, exist_ok=True)
        quality_file = quality_dir / f"ch{req.chapter:04d}.json"
        saved = {
            "chapter": req.chapter,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            **report_dict,
        }
        quality_file.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {"ok": True, **report_dict}
    
    except Exception as e:
        logging.error(f"质量评估失败: {e}", exc_info=True)
        raise HTTPException(500, f"质量评估失败：{e}")


class QualityReviseReq(BaseModel):
    chapter: int


@app.post("/api/books/{book_id}/quality/revise")
async def quality_revise(book_id: str, req: QualityReviseReq):
    """基于质量评估结果进行自动修订（含状态更新）"""
    chapter = req.chapter
    _load_env()
    sm = _sm(book_id)
    
    # 读取章节内容
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        raise HTTPException(404, f"第 {chapter} 章不存在")
    
    # 读取前一章内容
    prev_content = ""
    if chapter > 1:
        prev_content = sm.read_final(chapter - 1) or sm.read_draft(chapter - 1) or ""
    
    # 读取配置
    cfg = sm.read_config()
    genre = cfg.get("genre", "general")
    
    try:
        from core.agents import QualityAgent, SummaryAgent
        from core.types.state import TruthFileKey
        from core.narrative import NarrativeEngine
        
        # 创建 QualityAgent
        llm = _create_llm(temperature=0.7, model_env="AUDITOR_MODEL")
        quality_agent = QualityAgent(llm)
        
        # 读取必要的上下文
        truth_ctx = sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE, TruthFileKey.PENDING_HOOKS,
            TruthFileKey.CHARACTER_MATRIX, TruthFileKey.CAUSAL_CHAIN,
            TruthFileKey.CHAPTER_SUMMARIES,
        ])
        
        from core.agents import ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
        
        blueprint = ArchitectBlueprint(
            core_conflict="", hooks_to_advance=[], hooks_to_plant=[],
            emotional_journey={}, chapter_end_hook="", pace_notes="",
            pre_write_checklist=PreWriteChecklist([], [], [], [], ""),
        )
        
        # 执行质量评估并修订
        result = await asyncio.to_thread(
            quality_agent.evaluate_chapter,
            chapter_content=content,
            chapter_number=chapter,
            genre=genre,
            blueprint=blueprint,
            truth_context=truth_ctx,
            settlement=PostWriteSettlement([], [], [], [], []),
            prev_chapter_content=prev_content[-800:] if prev_content else "",
            auto_revise=True,
        )
        
        # 获取修订后的内容和报告
        if isinstance(result, tuple):
            revised_content, report = result
        else:
            revised_content = content
            report = result
        
        # ── 状态更新（步骤9-15） ────────────────────────────────────────────────
        
        # 1. 重新提取因果链
        engine = NarrativeEngine(_llm())
        causal_links = await asyncio.to_thread(
            engine.extract_causal_relations, revised_content, chapter
        )
        causal_chain = sm.read_truth(TruthFileKey.CAUSAL_CHAIN) or ""
        import re
        if f"第{chapter}章因果链" in causal_chain:
            causal_chain = re.sub(
                rf"\n\n## 第{chapter}章因果链.*?(?=\n\n## 第|$)",
                f"\n\n## 第{chapter}章因果链\n{causal_links}",
                causal_chain, flags=re.DOTALL
            )
        else:
            causal_chain = f"{causal_chain}\n\n## 第{chapter}章因果链\n{causal_links}"
        sm.write_truth(TruthFileKey.CAUSAL_CHAIN, causal_chain.strip())
        
        # 2. 重新生成章节摘要
        full_summaries = sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES) or ""
        prior_sections = re.split(r'\n(?=## 第\d+章)', full_summaries)
        recent_summaries = "\n".join(prior_sections[-3:]) if len(prior_sections) > 3 else full_summaries
        
        character_matrix = sm.read_truth(TruthFileKey.CHARACTER_MATRIX) or ""
        chapter_summary = await asyncio.to_thread(
            SummaryAgent(_llm()).summarize_chapter,
            chapter_content=revised_content,
            chapter_number=chapter,
            prev_summary=recent_summaries,
            causal_chain=causal_links,
            character_matrix=character_matrix,
        )
        
        # 3. 更新章节摘要索引（替换旧摘要）
        if f"第{chapter}章" in full_summaries:
            full_summaries = re.sub(
                rf"\n\n## 第{chapter}章.*?(?=\n\n## 第|$)",
                f"\n\n## 第{chapter}章\n{chapter_summary}",
                full_summaries, flags=re.DOTALL
            )
        else:
            full_summaries = f"{full_summaries}\n\n## 第{chapter}章\n{chapter_summary}"
        sm.write_truth(TruthFileKey.CHAPTER_SUMMARIES, full_summaries.strip())
        
        # 4. 更新世界状态
        try:
            ws = sm.read_world_state()
            ws.current_chapter = chapter
            sm.write_world_state(ws)
            sm.update_current_state_md()
        except Exception:
            pass  # 世界状态更新失败不阻塞
        
        # 5. 保存修订后的内容为草稿
        sm.save_final(chapter, revised_content)
        
        report_dict = _dc_to_dict(report)
        
        return {
            "ok": True,
            "chapter": chapter,
            "revised": True,
            "quality_report": report_dict,
            "summary": f"修订完成，质量评分: {report_dict.get('overall_score', 0)}",
        }
    
    except Exception as e:
        logging.error(f"质量修订失败: {e}", exc_info=True)
        raise HTTPException(500, f"质量修订失败：{e}")


@app.get("/api/books/{book_id}/audit-results/{chapter}")
def get_audit_result(book_id: str, chapter: int):
    """获取已保存的审计结果"""
    sm = _sm(book_id)
    audit_file = sm.state_dir / "audit_results" / f"ch{chapter:04d}.json"
    if not audit_file.exists():
        raise HTTPException(404, "该章节尚未审计")
    return json.loads(audit_file.read_text(encoding="utf-8"))


@app.get("/api/books/{book_id}/audit-results")
def list_audit_results(book_id: str):
    """列出所有已审计章节的结果摘要"""
    sm = _sm(book_id)
    audit_dir = sm.state_dir / "audit_results"
    if not audit_dir.exists():
        return []
    results = []
    for f in sorted(audit_dir.glob("ch*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        results.append({
            "chapter": data.get("chapter"),
            "passed": data.get("passed"),
            "audited_at": data.get("audited_at"),
            "summary": data.get("summary", ""),
        })
    return results


@app.put("/api/books/{book_id}/chapters/{chapter}/content")
def update_chapter_content(book_id: str, chapter: int, req: dict):
    """直接更新章节正文内容"""
    sm = _sm(book_id)
    content = req.get("content", "")
    kind = req.get("kind", "draft")
    if kind == "final":
        sm.save_final(chapter, content)
    else:
        sm.save_draft(chapter, content)
    return {"ok": True, "chars": len(content)}


class SegmentRewriteReq(BaseModel):
    chapter: int
    original_text: str
    instruction: str
    context_before: str = ""
    context_after: str = ""


@app.post("/api/books/{book_id}/ai-rewrite-segment")
async def ai_rewrite_segment(book_id: str, req: SegmentRewriteReq):
    """AI 按指令重写选中段落"""
    _load_env()
    sm = _sm(book_id)
    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    from core.llm import LLMMessage

    prompt = f"""你是一位文笔出色的小说编辑。请根据用户的修改指令，重写以下段落。

## 修改指令
{req.instruction}

## 前文（供参考上下文）
{req.context_before[-800:] if req.context_before else '（无）'}

## 需要重写的段落
{req.original_text}

## 后文（供参考上下文）
{req.context_after[-800:] if req.context_after else '（无）'}

## 要求
- 只输出重写后的段落，不要输出任何说明或标注
- 保持与上下文的连贯性
- 保持人物性格一致
- 字数与原文大致相同
"""

    def _call():
        resp = llm.complete([
            LLMMessage("system", "你是一位经验丰富的小说编辑。只输出重写后的段落文本，不要任何说明。"),
            LLMMessage("user", prompt),
        ])
        return resp.content

    try:
        rewritten = await asyncio.to_thread(_call)
    except Exception as e:
        raise HTTPException(500, f"重写失败：{e}")

    return {"ok": True, "rewritten": rewritten}


# ── /api/settings  读写 .env 配置 ────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    result = {
        "llm_provider": "deepseek",
        "deepseek_base_url": "https://api.deepseek.com/v1",
        "deepseek_model": "deepseek-chat",
        "deepseek_api_key": "",
        "ollama_base_url": "http://localhost:11434/v1",
        "ollama_model": "llama3.1",
        "default_temperature": "0.7",
        "max_tokens": "8192",
        "auditor_model": "",
        "architect_model": "",
        "writer_model": "",
        "reviser_model": "",
        "llm_timeout": "300",
        "llm_max_retries": "3",
        "llm_retry_delay": "5",
        "custom_base_url": "",
        "custom_model": "",
        "custom_api_key": "",
    }
    if ENV_PATH.exists():
        from dotenv import dotenv_values
        vals = dotenv_values(ENV_PATH)
        for k in vals:
            kl = k.lower()
            if kl == "llm_provider":
                result["llm_provider"] = vals[k]
            elif kl == "deepseek_base_url":
                result["deepseek_base_url"] = vals[k]
            elif kl == "deepseek_model":
                result["deepseek_model"] = vals[k]
            elif kl == "deepseek_api_key":
                result["deepseek_api_key"] = vals[k][:6] + "***" if vals[k] and len(vals[k]) > 6 else vals[k]
            elif kl == "ollama_base_url":
                result["ollama_base_url"] = vals[k]
            elif kl == "ollama_model":
                result["ollama_model"] = vals[k]
            elif kl == "default_temperature":
                result["default_temperature"] = vals[k]
            elif kl == "max_tokens":
                result["max_tokens"] = vals[k]
            elif kl == "auditor_model":
                result["auditor_model"] = vals[k]
            elif kl == "architect_model":
                result["architect_model"] = vals[k]
            elif kl == "writer_model":
                result["writer_model"] = vals[k]
            elif kl == "reviser_model":
                result["reviser_model"] = vals[k]
            elif kl == "llm_timeout":
                result["llm_timeout"] = vals[k]
            elif kl == "llm_max_retries":
                result["llm_max_retries"] = vals[k]
            elif kl == "llm_retry_delay":
                result["llm_retry_delay"] = vals[k]
    # 读取当前提供商的配置（用于回填 custom 面板）
    current_provider = result["llm_provider"].lower()
    if current_provider not in ("deepseek", "ollama") and ENV_PATH.exists():
        from dotenv import dotenv_values
        vals = dotenv_values(ENV_PATH)
        prefix = current_provider.upper() + "_"
        result["custom_base_url"] = vals.get(f"{prefix}BASE_URL", "")
        result["custom_model"] = vals.get(f"{prefix}MODEL", "")
        result["custom_api_key"] = vals.get(f"{prefix}API_KEY", "")
        if result["custom_api_key"] and len(result["custom_api_key"]) > 6:
            result["custom_api_key"] = result["custom_api_key"][:6] + "***"
    return result


@app.get("/api/settings/status")
def get_settings_status():
    """检测 API 配置状态（是否已配置可用）"""
    configured = False
    provider = "deepseek"
    api_ready = False

    if ENV_PATH.exists():
        from dotenv import dotenv_values
        vals = dotenv_values(ENV_PATH)
        provider = vals.get("LLM_PROVIDER", "deepseek").lower()
        if provider == "ollama":
            configured = True
            api_ready = True
        else:
            # 检查对应提供商的 API Key
            if provider in ("deepseek",):
                key = vals.get("DEEPSEEK_API_KEY", "")
            else:
                prefix = provider.upper() + "_"
                key = vals.get(f"{prefix}API_KEY", "") or vals.get("DEEPSEEK_API_KEY", "")
            if key:
                configured = True
                api_ready = True

    return {
        "configured": configured,
        "provider": provider,
        "api_ready": api_ready,
    }


@app.post("/api/settings")
def save_settings(req: SaveSettingsReq):
    lines: list[str] = []
    lines.append("# Dramatica-Flow 配置（由 Web UI 写入）")
    lines.append(f"LLM_PROVIDER={req.llm_provider}")
    lines.append("")
    lines.append("# DeepSeek 配置")
    lines.append(f"DEEPSEEK_BASE_URL={req.deepseek_base_url}")
    lines.append(f"DEEPSEEK_MODEL={req.deepseek_model}")
    if req.deepseek_api_key:
        existing = ""
        if ENV_PATH.exists():
            from dotenv import dotenv_values
            vals = dotenv_values(ENV_PATH)
            existing = vals.get("DEEPSEEK_API_KEY", "")
        if req.deepseek_api_key.endswith("***") and existing:
            lines.append(f"DEEPSEEK_API_KEY={existing}")
        else:
            lines.append(f"DEEPSEEK_API_KEY={req.deepseek_api_key}")
    else:
        lines.append("DEEPSEEK_API_KEY=")
    lines.append("")
    lines.append("# Ollama 配置")
    lines.append(f"OLLAMA_BASE_URL={req.ollama_base_url}")
    lines.append(f"OLLAMA_MODEL={req.ollama_model}")
    lines.append("")
    # 自定义提供商配置（openai / zhipu / moonshot / qwen / custom）
    provider = req.llm_provider.lower()
    if provider not in ("deepseek", "ollama"):
        env_prefix = provider.upper() + "_"
        lines.append(f"# {provider.upper()} 配置")
        lines.append(f"{env_prefix}BASE_URL={req.custom_base_url}")
        lines.append(f"{env_prefix}MODEL={req.custom_model}")
        lines.append(f"{env_prefix}API_KEY={req.custom_api_key}")
        lines.append("")
    lines.append("# 写作参数")
    lines.append(f"DEFAULT_TEMPERATURE={req.default_temperature}")
    lines.append(f"MAX_TOKENS={req.max_tokens}")
    lines.append("")
    lines.append("# 各 Agent 模型配置（留空使用主模型）")
    if req.architect_model:
        lines.append(f"ARCHITECT_MODEL={req.architect_model}")
    if req.writer_model:
        lines.append(f"WRITER_MODEL={req.writer_model}")
    if req.auditor_model:
        lines.append(f"AUDITOR_MODEL={req.auditor_model}")
    if req.reviser_model:
        lines.append(f"REVISER_MODEL={req.reviser_model}")
    lines.append("")
    lines.append("# LLM 高级配置")
    lines.append(f"LLM_TIMEOUT={req.llm_timeout}")
    lines.append(f"LLM_MAX_RETRIES={req.llm_max_retries}")
    lines.append(f"LLM_RETRY_DELAY={req.llm_retry_delay}")
    lines.append("")
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    # 更新内存中的环境变量（确保后续请求立即生效）
    os.environ["LLM_PROVIDER"] = req.llm_provider
    if req.deepseek_api_key and not req.deepseek_api_key.endswith("***"):
        os.environ["DEEPSEEK_API_KEY"] = req.deepseek_api_key
    os.environ["DEEPSEEK_BASE_URL"] = req.deepseek_base_url
    os.environ["DEEPSEEK_MODEL"] = req.deepseek_model
    os.environ["OLLAMA_BASE_URL"] = req.ollama_base_url
    os.environ["OLLAMA_MODEL"] = req.ollama_model
    os.environ["DEFAULT_TEMPERATURE"] = req.default_temperature
    os.environ["MAX_TOKENS"] = req.max_tokens
    os.environ["ARCHITECT_MODEL"] = req.architect_model or ""
    os.environ["WRITER_MODEL"] = req.writer_model or ""
    os.environ["AUDITOR_MODEL"] = req.auditor_model or ""
    os.environ["REVISER_MODEL"] = req.reviser_model or ""
    os.environ["LLM_TIMEOUT"] = req.llm_timeout
    os.environ["LLM_MAX_RETRIES"] = req.llm_max_retries
    os.environ["LLM_RETRY_DELAY"] = req.llm_retry_delay
    if provider not in ("deepseek", "ollama"):
        env_prefix = provider.upper() + "_"
        if req.custom_api_key:
            os.environ[f"{env_prefix}API_KEY"] = req.custom_api_key
        if req.custom_base_url:
            os.environ[f"{env_prefix}BASE_URL"] = req.custom_base_url
        if req.custom_model:
            os.environ[f"{env_prefix}MODEL"] = req.custom_model
    return {"ok": True}


class TestLLMConnectionReq(BaseModel):
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""


@app.post("/api/test-llm-connection")
async def test_llm_connection(req: TestLLMConnectionReq):
    """测试 LLM 连接是否可用"""
    from core.llm import LLMConfig, create_provider, LLMMessage

    provider = req.llm_provider.lower()

    try:
        if provider == "ollama":
            cfg = LLMConfig(
                api_key="ollama",
                base_url=req.ollama_base_url,
                model=req.ollama_model,
                temperature=0.1,
                max_tokens=100,
            )
        elif provider == "deepseek":
            cfg = LLMConfig(
                api_key=req.deepseek_api_key,
                base_url=req.deepseek_base_url,
                model=req.deepseek_model,
                temperature=0.1,
                max_tokens=100,
            )
        else:
            # openai / zhipu / moonshot / qwen / custom
            cfg = LLMConfig(
                api_key=req.custom_api_key,
                base_url=req.custom_base_url,
                model=req.custom_model,
                temperature=0.1,
                max_tokens=100,
            )

        llm = create_provider(cfg, provider_type=provider)

        # 用极简请求测试连接
        resp = await asyncio.to_thread(
            llm.complete,
            [LLMMessage("user", "Hello")],
        )

        # 调试：打印返回结果
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"测试连接返回结果：{resp}")
        logger.info(f"返回内容类型：{type(resp)}")
        if hasattr(resp, '__dict__'):
            logger.info(f"返回对象属性：{resp.__dict__}")
        if hasattr(resp, 'content'):
            logger.info(f"返回内容：{resp.content}")
        if hasattr(resp, 'input_tokens'):
            logger.info(f"输入 token 数：{resp.input_tokens}")
        if hasattr(resp, 'output_tokens'):
            logger.info(f"输出 token 数：{resp.output_tokens}")

        # 检查返回内容是否为空
        if not resp or not hasattr(resp, 'content') or not resp.content:
            return {"ok": False, "message": "LLM 返回内容为空", "detail": "模型未返回有效内容"}

        return {
            "ok": True,
            "message": "连接成功！模型返回正常",
            "model": cfg.model,
            "input_tokens": resp.input_tokens if hasattr(resp, 'input_tokens') else 0,
            "output_tokens": resp.output_tokens if hasattr(resp, 'output_tokens') else 0,
        }
    except Exception as e:
        error_msg = str(e)
        # 提炼关键错误信息
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "auth" in error_msg.lower():
            return {"ok": False, "message": "API Key 无效或未授权", "detail": error_msg}
        if "404" in error_msg or "not found" in error_msg.lower():
            return {"ok": False, "message": f"模型 '{cfg.model}' 不存在或接口地址错误", "detail": error_msg}
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return {"ok": False, "message": "连接超时，请检查网络或接口地址", "detail": error_msg}
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return {"ok": False, "message": "无法连接服务器，请检查地址和端口", "detail": error_msg}
        return {"ok": False, "message": f"连接失败：{error_msg[:200]}", "detail": error_msg}


# ── /api/action/*  触发 CLI 命令 ─────────────────────────────────────────────

class DetailedOutlineReq(BaseModel):
    chapter_number: int
    extra_points: str = ""


class ChapterContentReq(BaseModel):
    chapter_number: int
    style_override: str = ""  # 本次写作风格覆盖（不填则用书籍默认）


@app.post("/api/books/{book_id}/ai-generate/detailed-outline")
async def ai_generate_detailed_outline(book_id: str, req: DetailedOutlineReq):
    """基于章纲生成单章细纲（更详细的节拍展开）"""
    _load_env()
    sm = _sm(book_id)

    co_path = sm.state_dir / "chapter_outlines.json"
    if not co_path.exists():
        raise HTTPException(404, "请先生成章节大纲")

    all_cos = json.loads(co_path.read_text(encoding="utf-8"))
    # 找到目标章节
    target_co = None
    for co in all_cos:
        if co.get("chapter_number") == req.chapter_number:
            target_co = co
            break
    if not target_co:
        raise HTTPException(404, f"第 {req.chapter_number} 章不在章纲中")

    try:
        llm = _create_llm(temperature=0.7)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    # ── 读取上下文（让细纲也连贯） ──────────────────────────────
    from core.types.state import TruthFileKey

    # 世界状态 + 角色矩阵
    world_ctx = sm.read_truth_bundle([
        TruthFileKey.CURRENT_STATE,
        TruthFileKey.CHARACTER_MATRIX,
    ])

    # 未闭合伏笔
    pending_hooks = sm.read_truth(TruthFileKey.PENDING_HOOKS)

    # 因果链（最近 30 条）
    causal_chain = sm.read_truth(TruthFileKey.CAUSAL_CHAIN)

    # 前情摘要（最近 3 章）
    full_summaries = sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES)
    import re as _re
    prior_sections = _re.split(r'\n(?=## 第\d+章)', full_summaries)
    recent_summaries = "\n".join(prior_sections[-3:]) if len(prior_sections) > 3 else full_summaries

    # 前后章纲（让细纲知道前一章写了什么、下一章要写什么）
    prev_co = next((c for c in all_cos if c.get("chapter_number") == req.chapter_number - 1), None)
    next_co = next((c for c in all_cos if c.get("chapter_number") == req.chapter_number + 1), None)
    adjacent_ctx = ""
    if prev_co:
        adjacent_ctx += f"\n- 前一章（第{req.chapter_number-1}章）：《{prev_co.get('title','')}》— {prev_co.get('summary','')}"
    if next_co:
        adjacent_ctx += f"\n- 下一章（第{req.chapter_number+1}章）：《{next_co.get('title','')}》— {next_co.get('summary','')}"

    # 构建细纲 prompt
    prompt = f"""你是一位专业的小说编辑，请根据以下章纲信息，为第 {req.chapter_number} 章生成详细的章节细纲。

## 基本信息
- 章节标题：{target_co.get('title', f'第{req.chapter_number}章')}
- 章节摘要：{target_co.get('summary', '无')}
- 目标字数：{target_co.get('target_words', 4000)}字

## 前后章节衔接{adjacent_ctx}

## 节拍序列（Beat）
{json.dumps(target_co.get('beats', []), ensure_ascii=False, indent=2)}

## 必须完成的叙事任务
{json.dumps(target_co.get('mandatory_tasks', []), ensure_ascii=False)}
{f'''
## 视角要求
{target_co.get('pov', '')}
''' if target_co.get('pov') else ''}{f'''
## 写作基调（本章重要指导）
{target_co.get('writing_notes', '')}
''' if target_co.get('writing_notes') else ''}

## 用户追加的剧情点（重要！必须在细纲中体现）
{req.extra_points or '无'}

## 当前世界状态（角色位置、情感、关系）
{world_ctx if world_ctx.strip() else '（尚未建立）'}

## 未闭合伏笔
{pending_hooks if pending_hooks.strip() else '（暂无）'}

## 近期因果链（最近发生的因果关系）
{causal_chain[-1500:] if causal_chain.strip() else '（暂无）'}

## 前情摘要（最近章节）
{recent_summaries if recent_summaries.strip() else '（这是早期章节）'}

## 严格要求
- 如果用户追加了剧情点，必须将所有剧情点融入场景设计中，不能遗漏任何一个
- 用户追加的剧情点优先级最高，需要围绕它们展开场景
请输出一个 JSON 对象，包含以下字段：
{{
  "chapter_number": {req.chapter_number},
  "title": "章节标题",
  "detailed_summary": "200-300字的详细剧情梗概（起承转合完整）",
  "scenes": [
    {{
      "scene_id": "s1",
      "scene_title": "场景标题",
      "location": "地点",
      "characters": ["出场角色"],
      "time_marker": "时间（如：深夜、清晨）",
      "goal": "本场目标",
      "conflict": "本场冲突",
      "beats": ["具体节拍1", "具体节拍2"],
      "emotional_shift": "情感变化",
      "dialogue_notes": "关键对话方向",
      "ending": "本场结尾状态",
      "word_budget": 500
    }}
  ],
  "hooks_to_plant": ["本章要埋下的伏笔"],
  "hooks_to_advance": ["本章要推进的伏笔"],
  "chapter_end_hook": "结尾悬念钩子"
}}
只输出 JSON，不要任何说明。"""

    def _call():
        from core.llm import LLMMessage
        resp = llm.complete([
            LLMMessage("system", "你是精通小说结构的故事编辑，只输出合法 JSON。"),
            LLMMessage("user", prompt),
        ])
        return resp.content

    try:
        raw = await asyncio.to_thread(_call)
        import re
        stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()
        result = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"细纲 JSON 解析失败：{e}\n原始输出：{raw[:500]}")
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"细纲生成失败：{e}")

    # 保存细纲
    detail_path = sm.state_dir / "detailed_outlines" / f"ch{req.chapter_number:04d}.json"
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "data": result}


@app.get("/api/books/{book_id}/detailed-outline/{chapter}")
def get_detailed_outline(book_id: str, chapter: int):
    sm = _sm(book_id)
    path = sm.state_dir / "detailed_outlines" / f"ch{chapter:04d}.json"
    if not path.exists():
        raise HTTPException(404, f"第 {chapter} 章细纲尚未生成")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/api/books/{book_id}/detailed-outline/{chapter}")
def save_detailed_outline(book_id: str, chapter: int, data: dict):
    sm = _sm(book_id)
    path = sm.state_dir / "detailed_outlines" / f"ch{chapter:04d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.post("/api/books/{book_id}/ai-generate/方法")
async def ai_generate_chapter_content(book_id: str, req: ChapterContentReq):
    """基于细纲生成单章正文（含完整上下文注入 + 写后状态更新）"""
    _load_env()
    sm = _sm(book_id)

    # 读取细纲
    detail_path = sm.state_dir / "detailed_outlines" / f"ch{req.chapter_number:04d}.json"
    if not detail_path.exists():
        raise HTTPException(404, "请先生成细纲")

    detailed = json.loads(detail_path.read_text(encoding="utf-8"))

    # 读取章纲
    co_path = sm.state_dir / "chapter_outlines.json"
    co_data = json.loads(co_path.read_text(encoding="utf-8")) if co_path.exists() else []
    target_co = next((c for c in co_data if c.get("chapter_number") == req.chapter_number), {})

    try:
        from core.setup import SetupLoader
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

    try:
        llm = _create_llm(temperature=0.8)
    except Exception as e:
        raise HTTPException(400, f"LLM 创建失败：{e}")

    # ── 读取完整上下文（与 WritingPipeline 对齐） ──────────────
    from core.types.state import TruthFileKey

    # 世界状态 + 角色矩阵
    world_ctx = sm.read_truth_bundle([
        TruthFileKey.CURRENT_STATE,
        TruthFileKey.CHARACTER_MATRIX,
    ])

    # 未闭合伏笔
    pending_hooks = sm.read_truth(TruthFileKey.PENDING_HOOKS)

    # 因果链
    causal_chain = sm.read_truth(TruthFileKey.CAUSAL_CHAIN)

    # 情感弧线
    emotional_arcs = sm.read_truth(TruthFileKey.EMOTIONAL_ARCS)

    # 前情摘要（最近 3 章，而非盲目截断）
    full_summaries = sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES)
    import re as _re
    prior_sections = _re.split(r'\n(?=## 第\d+章)', full_summaries)
    recent_summaries = "\n".join(prior_sections[-3:]) if len(prior_sections) > 3 else full_summaries

    # 前一章内容（最后 800 字，用于衔接）
    prev_content = ""
    prev_final = sm.read_final(req.chapter_number - 1) or sm.read_draft(req.chapter_number - 1)
    if prev_final:
        prev_content = prev_final[-800:]

    protagonist = state.characters.get(state.config.protagonist_id)
    pname = protagonist.name if protagonist else "主角"
    p_need = protagonist.need.external if protagonist else "未知"
    p_internal = protagonist.need.internal if protagonist else "未知"

    # 角色速查
    char_quick_ref = "\n".join(
        f"- {c.name}（{c.id}）：{c.need.external[:40]}"
        for c in state.characters.values()
    )

    from core.llm import LLMMessage

    scenes_text = json.dumps(detailed.get("scenes", []), ensure_ascii=False, indent=2)
    hooks_plant = json.dumps(detailed.get("hooks_to_plant", []), ensure_ascii=False)
    hooks_advance = json.dumps(detailed.get("hooks_to_advance", []), ensure_ascii=False)
    end_hook = detailed.get("chapter_end_hook", "")
    target_words = target_co.get("target_words", 4000)
    if target_words < 500:
        target_words = 4000

    prev_section = ""
    if prev_content.strip():
        prev_section = f"""
## 前一章结尾（衔接用）
{prev_content}
> 以上是上一章最后 800 字，本章开头必须自然衔接。
"""

    prompt = f"""你是一位文笔出色的网络小说作家。请根据以下细纲，创作第 {req.chapter_number} 章的完整正文。

## 基本信息
- 章节标题：{detailed.get('title', f'第{req.chapter_number}章')}
- 详细梗概：{detailed.get('detailed_summary', '')}
- 目标字数：{target_words}字

## 场景拆分
{scenes_text}

## 埋下伏笔
{hooks_plant}

## 推进伏笔
{hooks_advance}

## 结尾钩子
{end_hook}
{prev_section}
## 主角信息
- 姓名：{pname}
- 外部目标：{p_need}
- 内在需求：{p_internal}

## 登场角色速查
{char_quick_ref}

## 当前世界状态（角色位置、情感、关系）
{world_ctx if world_ctx.strip() else '（尚未建立）'}

## 未闭合伏笔（需要在正文中体现推进或埋设）
{pending_hooks if pending_hooks.strip() else '（暂无）'}

## 近期因果链（确保本章事件与之前因果关系一致）
{causal_chain[-1200:] if causal_chain.strip() else '（暂无）'}

## 情感弧线（角色情感走向）
{emotional_arcs[-600:] if emotional_arcs.strip() else '（暂无）'}

## 前情摘要（最近 3 章）
{recent_summaries if recent_summaries.strip() else '（这是早期章节）'}

## 写作要求
- **字数硬性要求（必须遵守）：**
  - 目标字数：{target_words} 字
  - 允许范围：{int(target_words*0.9)}–{int(target_words*1.1)} 字（±10%）
  - 硬性上限：绝对不能超过 {int(target_words*1.2)} 字
  - 硬性下限：绝对不能少于 {int(target_words*0.8)} 字
  - 警告：超过上限将直接被拒绝，少于下限将被要求重写
  - 策略：先规划好场景长度，避免写太多后被迫大幅删减。如果感觉内容过多，请提前精简描写。
- 本章开头必须与前一章结尾自然衔接，不能突兀跳转
- 场景之间要有自然过渡
- 对话要有角色个性，体现角色关系
- 伏笔推进要有机融入情节，不能生硬提及
- 角色情感要与前文保持一致
- 结尾要留下悬念（{end_hook}）
- 纯正文输出，不要任何标注或说明
- 写完后请检查字数，如果不足请继续补充细节描写和对话，直到达到字数要求
"""

    def _call():
        effective_style = (req.style_override or state.config.style_guide or "").strip()
        style_section = ""
        if effective_style:
            style_section = f"\n\n## 文风要求\n{effective_style}\n\n请严格按以上风格要求写作，这是作者指定的文风。"
        resp = llm.complete([
            LLMMessage("system", f"你是一位经验丰富的网络小说作家，擅长{state.config.genre or '玄幻'}题材，文笔流畅，善用描写和对话推进情节。直接输出小说正文。{style_section}"),
            LLMMessage("user", prompt),
        ])
        return resp.content

    try:
        content = await asyncio.to_thread(_call)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"正文生成失败：{e}")

    # ── 字数自动处理 ──
    content_length = len(content)
    max_length = int(target_words * 1.2)  # 硬性上限
    min_length = int(target_words * 0.8)  # 硬性下限
    
    if content_length > max_length:
        # 超过上限，自动截断到目标字数
        truncate_at = int(target_words * 1.1)
        if truncate_at < len(content):
            # 尝试在句子结尾截断
            for i in range(truncate_at, min(len(content), truncate_at + 50)):
                if content[i] in ('。', '！', '？', '；', ':', '\n', ' '):
                    content = content[:i+1].strip()
                    break
            else:
                content = content[:truncate_at].strip() + "..."

    # 保存草稿
    sm.save_draft(req.chapter_number, content)

    # ── 写后状态更新（让下一章有记忆） ──────────────────────────
    try:
        import re
        
        # 1. 生成章节摘要并提取伏笔回收信息
        summary_prompt = f"""请为以下小说章节生成一份简明摘要（200-300字），并分析伏笔回收情况。输出格式：

【章节摘要】
（200-300字的章节摘要）

【伏笔回收】
列出本章回收的伏笔描述（一句话描述，用顿号分隔），如果没有回收任何伏笔则写"无"。

章节正文：
{content[:4000]}"""

        summary_resp = await asyncio.to_thread(lambda: llm.complete([
            LLMMessage("system", "你是小说编辑助手，生成简洁客观的章节摘要并分析伏笔回收情况。"),
            LLMMessage("user", summary_prompt),
        ]).content)

        # 解析摘要和伏笔回收
        summary_text = ""
        resolved_hooks = []
        
        if "【章节摘要】" in summary_resp:
            if "【伏笔回收】" in summary_resp:
                parts = summary_resp.split("【伏笔回收】")
                summary_text = parts[0].replace("【章节摘要】", "").strip()
                hooks_part = parts[1].strip()
                if hooks_part and hooks_part != "无":
                    resolved_hooks = [h.strip() for h in hooks_part.split("、") if h.strip()]
            else:
                summary_text = summary_resp.replace("【章节摘要】", "").strip()

        # 检查是否已存在该章节摘要，存在则替换，否则追加
        full_summaries = sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES) or ""
        chapter_title = detailed.get('title', '')
        summary_md = f"\n## 第 {req.chapter_number} 章《{chapter_title}》\n{summary_text.strip()}\n---\n"
        
        # 使用正则表达式替换已存在的章节摘要
        chapter_pattern = rf"\n## 第 {req.chapter_number} 章.*?(?=\n## 第|$)"
        if re.search(chapter_pattern, full_summaries, re.DOTALL):
            full_summaries = re.sub(chapter_pattern, summary_md, full_summaries, flags=re.DOTALL)
        else:
            full_summaries = f"{full_summaries}{summary_md}"
        sm.write_truth(TruthFileKey.CHAPTER_SUMMARIES, full_summaries.strip())

        # 2. 回收伏笔（根据分析结果）
        resolved_count = 0
        if resolved_hooks:
            ws = sm.read_world_state()
            for h_desc in resolved_hooks:
                h_desc_stripped = str(h_desc).strip()
                if not h_desc_stripped:
                    continue
                for hook in ws.pending_hooks:
                    if hook.status == HookStatus.OPEN and (h_desc_stripped.lower() in hook.description.lower() or hook.description.lower() in h_desc_stripped.lower()):
                        hook.status = HookStatus.RESOLVED
                        hook.resolved_in_chapter = req.chapter_number
                        resolved_count += 1
            sm.write_world_state(ws)
            if resolved_count > 0:
                import logging
                logging.info(f"[chapter-content] 第 {req.chapter_number} 章回收 {resolved_count} 个伏笔")

        # 3. 提取简单因果链
        causal_prompt = f"""从以下章节正文中提取因果关系，每条格式为：
因为 [原因]，发生了 [事件]，导致 [后果]
只列出最重要的 2-5 条。

正文：
{content[:4000]}"""

        causal_resp = await asyncio.to_thread(lambda: llm.complete([
            LLMMessage("system", "你从小说正文中提取因果关系，每条一行。"),
            LLMMessage("user", causal_prompt),
        ]).content)

        # 检查是否已存在该章节因果链，存在则替换，否则追加
        if causal_resp.strip():
            causal_chain = sm.read_truth(TruthFileKey.CAUSAL_CHAIN) or ""
            causal_entry = f"\n### 第 {req.chapter_number} 章\n{causal_resp.strip()}\n"
            
            causal_pattern = rf"\n### 第 {req.chapter_number} 章.*?(?=\n### 第|$)"
            if re.search(causal_pattern, causal_chain, re.DOTALL):
                causal_chain = re.sub(causal_pattern, causal_entry, causal_chain, flags=re.DOTALL)
            else:
                causal_chain = f"{causal_chain}{causal_entry}"
            sm.write_truth(TruthFileKey.CAUSAL_CHAIN, causal_chain.strip())

        # 3. 更新世界状态中的当前章节号
        try:
            ws = sm.read_world_state()
            ws.current_chapter = req.chapter_number
            sm.write_world_state(ws)
            sm.update_current_state_md()
        except Exception:
            pass  # 世界状态更新失败不阻塞

    except Exception as e:
        import traceback; traceback.print_exc()
        # 摘要/因果链生成失败不阻塞正文返回

    return {"ok": True, "chapter_number": req.chapter_number, "content": content, "chars": len(content)}


@app.get("/api/action/write/stream")
async def action_write_stream(book_id: str, count: int = 1):
    """连续写N章（SSE流式输出）"""
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    
    async def event_generator():
        try:
            import sys
            import subprocess
            import threading
            import asyncio
            
            cmd = [sys.executable, "-m", "cli.main", "write", book_id, "--count", str(count)]
            
            # 获取书籍信息用于进度展示
            from core.state import StateManager
            from core.setup import SetupLoader
            from core.narrative import StoryOutlineSchema
            
            sm = StateManager(".", book_id)
            try:
                state = SetupLoader.restore(".", book_id)
            except:
                state = None
            
            total_outlines = 0
            try:
                outline_path = sm.state_dir / "chapter_outlines.json"
                if outline_path.exists():
                    import json
                    raw = json.loads(outline_path.read_text(encoding="utf-8"))
                    total_outlines = len(raw)
            except:
                pass
            
            # 计算总章节数
            total_chapters_for_progress = total_outlines if total_outlines > 0 else count
            
            yield f"data: {json.dumps({'stage': 'init', 'message': '准备开始写作...', 'total_outlines': total_outlines, 'total_chapters': total_chapters_for_progress}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ},
                bufsize=1,
                universal_newlines=True
            )
            
            stdout_output = []
            current_chapter = 0
            current_chapter_title = ""
            completed_chapters = 0
            
            loop = asyncio.get_running_loop()
            
            def read_output():
                nonlocal current_chapter, current_chapter_title, completed_chapters
                try:
                    for line in process.stdout:
                        print(line, end="")
                        stdout_output.append(line)
                        
                        # 解析进度信息
                        line_stripped = line.strip()
                        
                        # 检测开始新章节
                        if line_stripped.startswith("第") and "章《" in line_stripped:
                            import re
                            ch_match = re.search(r"第\s*(\d+)\s*章《(.*?)》", line_stripped)
                            if ch_match:
                                nonlocal current_chapter, current_chapter_title
                                current_chapter = int(ch_match.group(1))
                                current_chapter_title = ch_match.group(2)
                                # 发送章节开始事件
                                payload = {
                                    "stage": "chapter_start",
                                    "chapter": current_chapter,
                                    "title": current_chapter_title,
                                    "message": f"开始写作第{current_chapter}章《{current_chapter_title}》",
                                    "completed_chapters": completed_chapters,
                                    "total_chapters": total_chapters_for_progress
                                }
                                asyncio.run_coroutine_threadsafe(
                                    asyncio.sleep(0),
                                    loop
                                ).result()
                                yield_event = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                try:
                                    loop.call_soon_threadsafe(lambda e=yield_event: event_queue.put_nowait(e))
                                except:
                                    pass
                        
                        # 检测章节完成
                        elif ("审计" in line_stripped and ("通过" in line_stripped or "未通过" in line_stripped)) or ("字" in line_stripped and "因果链" in line_stripped):
                            if current_chapter > 0:
                                completed_chapters += 1
                                # 发送章节完成事件
                                payload = {
                                    "stage": "chapter_complete",
                                    "chapter": current_chapter,
                                    "title": current_chapter_title,
                                    "message": f"第{current_chapter}章《{current_chapter_title}》写作完成",
                                    "completed_chapters": completed_chapters,
                                    "total_chapters": total_chapters_for_progress
                                }
                                yield_event = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                try:
                                    loop.call_soon_threadsafe(lambda e=yield_event: event_queue.put_nowait(e))
                                except:
                                    pass
                                    
                        # 识别步骤阶段并添加标记
                        step_message = line_stripped
                        step_tag = ""
                        
                        # 识别各个步骤
                        if "建筑师" in line_stripped or "规划" in line_stripped or "蓝图" in line_stripped:
                            step_tag = "[🏛️ 架构师]"
                        elif "写手" in line_stripped or "写正文" in line_stripped or "开始写作" in line_stripped:
                            step_tag = "[✍️ 写作者]"
                        elif "审计" in line_stripped:
                            step_tag = "[🔍 审计员]"
                        elif "修订" in line_stripped or "修改" in line_stripped:
                            step_tag = "[🔧 修订员]"
                        elif "质量评估" in line_stripped:
                            step_tag = "[⭐ 质量评估]"
                        elif "因果链" in line_stripped:
                            step_tag = "[🔗 因果链]"
                        elif "摘要" in line_stripped:
                            step_tag = "[📝 摘要生成]"
                        elif "结算" in line_stripped:
                            step_tag = "[📊 结算表]"
                        elif "完成" in line_stripped and "章" in line_stripped:
                            step_tag = "[✅ 章节完成]"
                        elif "保存" in line_stripped or "备份" in line_stripped:
                            step_tag = "[💾 保存]"
                        
                        # 如果有步骤标记，添加到消息前面
                        if step_tag:
                            step_message = f"{step_tag} {line_stripped}"
                        
                        # 发送原始日志
                        log_payload = {
                            "stage": "log",
                            "message": step_message
                        }
                        yield_event = f"data: {json.dumps(log_payload, ensure_ascii=False)}\n\n"
                        try:
                            loop.call_soon_threadsafe(lambda e=yield_event: event_queue.put_nowait(e))
                        except:
                            pass
                except Exception as e:
                    print(f"读取错误: {e}")
                    pass
            
            event_queue = asyncio.Queue()
            
            read_thread = threading.Thread(target=read_output)
            read_thread.daemon = True
            read_thread.start()
            
            # 从队列读取并yield事件
            timeout = 1200  # 20分钟
            start_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    if process.poll() is not None:
                        break
                    
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        process.kill()
                        yield f"data: {json.dumps({'stage': 'error', 'message': '写作超时（20分钟）'}, ensure_ascii=False)}\n\n"
                        break
                    
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                        yield event
                    except asyncio.TimeoutError:
                        continue
                except Exception as e:
                    print(f"事件错误: {e}")
                    break
            
            # 等待读取线程结束
            try:
                read_thread.join(timeout=5)
            except:
                pass
            
            stdout_str = "".join(stdout_output)
            ok = process.returncode == 0
            
            if ok:
                complete_msg = f'成功完成{completed_chapters}章写作'
                yield f"data: {json.dumps({'stage': 'complete', 'message': complete_msg, 'completed_chapters': completed_chapters}, ensure_ascii=False)}\n\n"
            else:
                # 从日志中提取更详细的错误信息
                error_details = stdout_str[-2000:] if stdout_str else ''
                error_message = '写作失败，请检查日志'
                
                # 尝试从日志中提取更具体的错误信息
                if 'JSON 解析失败' in stdout_str:
                    error_message = 'JSON 解析失败，模型输出格式异常'
                elif '已输出 JSON，不要输出代码' in stdout_str:
                    error_message = '模型输出格式问题：收到了干扰文本'
                elif 'LLMParseError' in stdout_str:
                    error_message = 'LLM 输出解析错误'
                elif '429' in stdout_str or 'rate limit' in stdout_str.lower() or 'too many requests' in stdout_str.lower():
                    error_message = '服务限流，请稍后重试（已自动重试3次）'
                elif '503' in stdout_str or 'service unavailable' in stdout_str.lower():
                    error_message = '服务暂时不可用，请稍后重试'
                elif 'API Error' in stdout_str or 'HTTP' in stdout_str:
                    error_message = 'API 请求失败，请检查网络或密钥配置'
                elif 'timeout' in stdout_str.lower():
                    error_message = '请求超时，请检查网络连接或增加超时时间'
                
                yield f"data: {json.dumps({'stage': 'error', 'message': error_message, 'details': error_details}, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f'执行出错：{str(e)}'
            yield f"data: {json.dumps({'stage': 'error', 'message': error_msg, 'details': traceback.format_exc()[-1000:]}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/action/write")
def action_write(book_id: str, count: int = 1):
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    try:
        import sys
        from subprocess import Popen, PIPE, STDOUT
        import threading
        import queue
        
        cmd = [sys.executable, "-m", "cli.main", "write", book_id, "--count", str(count)]
        
        # 使用 Popen 实时输出到控制台，同时捕获输出
        process = Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,  # 将 stderr 合并到 stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
            bufsize=1,
            universal_newlines=True
        )
        
        stdout_output = []
        output_queue = queue.Queue()
        
        # 定义读取线程函数
        def read_output():
            try:
                for line in process.stdout:
                    print(line, end="")  # 输出到控制台
                    stdout_output.append(line)
            except Exception as e:
                pass
        
        # 启动读取线程
        read_thread = threading.Thread(target=read_output)
        read_thread.daemon = True
        read_thread.start()
        
        # 等待进程完成，带超时
        timeout = 1200  # 20分钟
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            read_thread.join(timeout=1)
            return {"ok": False, "stdout": "", "stderr": "写作超时（20分钟），请检查命令行日志"}
        
        # 等待读取线程完成
        read_thread.join(timeout=5)
        
        stdout_str = "".join(stdout_output)
        stderr_str = ""  # stderr 已合并到 stdout
        
        return {"ok": process.returncode == 0, "stdout": stdout_str[-2000:], "stderr": stderr_str[-1000:]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "stdout": "", "stderr": f"执行出错：{str(e)}"}


# ── 重写章节 API ──────────────────────────────────────────────────────────────

from pydantic import BaseModel

class RewriteChapterReq(BaseModel):
    """重写章节请求"""
    chapter: int
    reason: str = ""
    cascade: bool = False  # 是否连锁重写后续章节


@app.post("/api/books/{book_id}/rewrite-chapter")
def rewrite_chapter(book_id: str, req: RewriteChapterReq):
    """
    重写指定章节
    
    Args:
        book_id: 书籍ID
        req.chapter: 要重写的章节号
        req.reason: 重写原因（可选）
        req.cascade: 是否连锁重写后续章节
    """
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    
    sm = _sm(book_id)
    
    # 1. 检查快照是否存在
    if not sm.has_snapshot(req.chapter - 1):
        raise HTTPException(400, f"第 {req.chapter - 1} 章的快照不存在，无法重写第 {req.chapter} 章")
    
    # 2. 检查章节大纲是否存在
    outline_path = sm.state_dir / "chapter_outlines.json"
    if not outline_path.exists():
        raise HTTPException(404, "章节大纲不存在，请先生成章节大纲")
    
    try:
        import json
        outlines_raw = json.loads(outline_path.read_text(encoding="utf-8"))
        from core.narrative import ChapterOutlineSchema
        
        # 找到目标章节的大纲
        target_outline = None
        for outline_data in outlines_raw:
            if outline_data.get("chapter_number") == req.chapter:
                target_outline = ChapterOutlineSchema.model_validate(outline_data)
                break
        
        if not target_outline:
            raise HTTPException(404, f"第 {req.chapter} 章的大纲不存在")
        
        # 3. 如果是连锁重写，先回滚到目标章节之前
        if req.cascade:
            sm.rollback_to_chapter(req.chapter)
        
        # 4. 初始化写作管线
        from core.setup import SetupLoader
        from core.pipeline import WritingPipeline
        from core.agents import ArchitectAgent, WriterAgent, AuditorAgent, ReviserAgent, SummaryAgent, QualityAgent
        from core.narrative import NarrativeEngine
        from core.validators import PostWriteValidator
        
        state = SetupLoader.restore(PROJECT_ROOT, book_id)
        protagonist = state.characters.get(state.config.protagonist_id)
        if protagonist is None:
            for ch in state.characters.values():
                if getattr(ch, "role", None) == "protagonist":
                    protagonist = ch
                    break
        
        llm = _create_llm(temperature=0.7)
        engine = NarrativeEngine(llm)
        
        pipeline = WritingPipeline(
            state_manager=sm,
            architect=ArchitectAgent(llm),
            writer=WriterAgent(llm, style_guide=state.config.style_guide, genre=state.config.genre),
            auditor=AuditorAgent(_create_llm(temperature=0.0)),
            reviser=ReviserAgent(llm),
            narrative_engine=engine,
            summary_agent=SummaryAgent(llm),
            validator=PostWriteValidator(state.config.custom_forbidden_words),
            protagonist=protagonist,
            all_characters=list(state.characters.values()),
        )
        
        # 5. 执行重写
        result = pipeline.rewrite_chapter(
            chapter_outline=target_outline,
            rewrite_reason=req.reason,
            verbose=True,
        )
        
        # 6. 如果是连锁重写，继续重写后续章节
        if req.cascade:
            ws = sm.read_world_state()
            max_chapter = ws.current_chapter
            for ch in range(req.chapter + 1, max_chapter + 1):
                # 找到该章节的大纲
                ch_outline = None
                for outline_data in outlines_raw:
                    if outline_data.get("chapter_number") == ch:
                        ch_outline = ChapterOutlineSchema.model_validate(outline_data)
                        break
                
                if ch_outline:
                    pipeline.run(ch_outline, verbose=True)
        
        return {
            "ok": True,
            "chapter": req.chapter,
            "word_count": result.word_count,
            "quality_score": result.quality_score,
            "cascade": req.cascade,
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"重写失败：{str(e)}")


@app.get("/api/books/{book_id}/can-rewrite/{chapter}")
def can_rewrite_chapter(book_id: str, chapter: int):
    """检查是否可以重写指定章节"""
    sm = _sm(book_id)
    
    # 检查快照是否存在
    has_snapshot = sm.has_snapshot(chapter - 1)
    
    # 检查章节大纲是否存在
    outline_path = sm.state_dir / "chapter_outlines.json"
    has_outline = outline_path.exists()
    
    # 检查该章节是否已写
    final_path = sm.chapter_dir / f"ch{chapter:04d}_final.md"
    has_written = final_path.exists()
    
    return {
        "can_rewrite": has_snapshot and has_outline,
        "has_snapshot": has_snapshot,
        "has_outline": has_outline,
        "has_written": has_written,
        "snapshot_chapter": chapter - 1,
    }


@app.post("/api/action/audit")
def action_audit(book_id: str, chapter: int):
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    try:
        import sys
        from subprocess import Popen, PIPE, STDOUT
        import threading
        
        cmd = [sys.executable, "-m", "cli.main", "audit", book_id, str(chapter)]
        
        process = Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
            bufsize=1,
            universal_newlines=True
        )
        
        stdout_output = []
        
        def read_output():
            try:
                for line in process.stdout:
                    print(line, end="")
                    stdout_output.append(line)
            except Exception as e:
                pass
        
        read_thread = threading.Thread(target=read_output)
        read_thread.daemon = True
        read_thread.start()
        
        timeout = 600  # 10分钟
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            read_thread.join(timeout=1)
            return {"ok": False, "stdout": "", "stderr": "审计超时"}
        
        read_thread.join(timeout=5)
        
        stdout_str = "".join(stdout_output)
        stderr_str = ""
        
        return {"ok": process.returncode == 0, "stdout": stdout_str[-2000:], "stderr": stderr_str[-1000:]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "stdout": "", "stderr": f"执行出错：{str(e)}"}


class ExportRequest(BaseModel):
    book_id: str
    fmt: str = "md"  # md | txt

@app.post("/api/action/export")
def action_export(req: ExportRequest):
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    try:
        import sys
        from subprocess import Popen, PIPE, STDOUT
        import threading
        
        cmd = [sys.executable, "-m", "cli.main", "export", req.book_id]
        
        process = Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
            bufsize=1,
            universal_newlines=True
        )
        
        stdout_output = []
        
        def read_output():
            try:
                for line in process.stdout:
                    print(line, end="")
                    stdout_output.append(line)
            except Exception as e:
                pass
        
        read_thread = threading.Thread(target=read_output)
        read_thread.daemon = True
        read_thread.start()
        
        timeout = 120  # 2分钟
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            read_thread.join(timeout=1)
            return {"ok": False, "stdout": "", "stderr": "导出超时"}
        
        read_thread.join(timeout=5)
        
        stdout_str = "".join(stdout_output)
        stderr_str = ""
        
        # 如果需要 txt 格式，将 md 转换为 txt
        if req.fmt == "txt" and process.returncode == 0:
            from core.state import StateManager
            sm = StateManager(".", req.book_id)
            config = sm.read_config()
            md_path = Path(f"{config['title']}.md")
            if md_path.exists():
                txt_path = md_path.with_suffix(".txt")
                txt_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
                stdout_str = str(txt_path)
        
        return {"ok": process.returncode == 0, "stdout": stdout_str[-2000:], "stderr": stderr_str[-1000:]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "stdout": "", "stderr": f"执行出错：{str(e)}"}


# ── StoryCanvas 导入/导出 ────────────────────────────────────────────────────

import uuid
import zipfile
import tempfile
from fastapi import UploadFile, File


@app.get("/api/books/{book_id}/export-storycanvas")
def export_storycanvas(book_id: str):
    """将 Dramatica-Flow 项目导出为 .storycanvas 格式（ZIP 包）"""
    sm = _sm(book_id)
    try:
        config = sm.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")

    ws = sm.read_world_state()

    blocks = []
    connections = []

    setup_dir = sm.book_dir / "setup"

    characters_data = {}
    if (setup_dir / "characters.json").exists():
        try:
            raw = json.loads((setup_dir / "characters.json").read_text(encoding="utf-8"))
            characters_data = raw
        except Exception:
            pass

    char_list = characters_data.get("characters", []) if isinstance(characters_data, dict) else []
    char_id_map = {}

    for ch in char_list:
        if not isinstance(ch, dict):
            continue
        cid = ch.get("id", str(uuid.uuid4()))
        block_id = str(uuid.uuid4())
        char_id_map[cid] = block_id
        role = ch.get("role", "supporting")
        on_canvas = role in ("protagonist", "主角")
        need_data = ch.get("need", {})
        external = need_data.get("external", "") if isinstance(need_data, dict) else str(need_data)
        internal = need_data.get("internal", "") if isinstance(need_data, dict) else ""
        personality_list = ch.get("personality", [])
        personality_str = "、".join(personality_list) if isinstance(personality_list, list) else str(personality_list)
        appearance = ch.get("profile", "") or ch.get("backstory", "")
        blocks.append({
            "id": block_id,
            "project_id": book_id,
            "type": "CHARACTER",
            "canvas_x": 100 + len(blocks) * 20,
            "canvas_y": 100 + len(blocks) * 30,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": on_canvas,
            "is_draft": False,
            "content": {
                "name": ch.get("name", ""),
                "want": external,
                "need": internal,
                "role_archetype": role,
                "surface_personality": personality_str,
                "appearance": appearance,
                "arc": ch.get("arc", ""),
                "behavior_lock": ch.get("behavior_lock", []),
            },
            "save_status": "saved",
        })

    world_data = {}
    if (setup_dir / "world.json").exists():
        try:
            world_data = json.loads((setup_dir / "world.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    world_name = config.get("title", book_id) + "世界观"
    rules = []
    if isinstance(world_data, dict):
        for r in world_data.get("rules", []):
            if isinstance(r, dict):
                rules.append(r.get("description", r.get("rule", str(r))))
            else:
                rules.append(str(r))

    worldview_block_id = str(uuid.uuid4())
    blocks.append({
        "id": worldview_block_id,
        "project_id": book_id,
        "type": "WORLDVIEW",
        "canvas_x": 500,
        "canvas_y": 50,
        "canvas_w": 280,
        "collapsed": False,
        "color": None,
        "timeline_id": None,
        "chapter_pos": None,
        "tags": "[]",
        "notes": "",
        "on_canvas": True,
        "is_draft": False,
        "content": {
            "world_name": world_name,
            "fundamental_rules": rules,
        },
        "save_status": "saved",
    })

    factions = world_data.get("factions", []) if isinstance(world_data, dict) else []
    for fac in factions:
        if not isinstance(fac, dict):
            continue
        fac_block_id = str(uuid.uuid4())
        blocks.append({
            "id": fac_block_id,
            "project_id": book_id,
            "type": "FACTION",
            "canvas_x": 500 + len(blocks) * 15,
            "canvas_y": 400 + len(blocks) * 10,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": False,
            "is_draft": False,
            "content": {
                "name": fac.get("name", ""),
                "ideology": fac.get("description", fac.get("stance", "")),
            },
            "save_status": "saved",
        })
        connections.append({
            "id": str(uuid.uuid4()),
            "from_block": worldview_block_id,
            "to_block": fac_block_id,
            "conn_type": "contains",
            "label": "",
            "chapter_hint": None,
        })

    events_data = {}
    if (setup_dir / "events.json").exists():
        try:
            events_data = json.loads((setup_dir / "events.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    event_list = events_data.get("events", []) if isinstance(events_data, dict) else []
    for evt in event_list:
        if not isinstance(evt, dict):
            continue
        evt_block_id = str(uuid.uuid4())
        blocks.append({
            "id": evt_block_id,
            "project_id": book_id,
            "type": "EVENT",
            "canvas_x": 100 + len(blocks) * 12,
            "canvas_y": 500 + len(blocks) * 8,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": False,
            "is_draft": False,
            "content": {
                "title": evt.get("name", ""),
                "what_happens": evt.get("description", ""),
                "suggested_act": evt.get("suggested_act"),
                "suggested_function": evt.get("suggested_function", ""),
            },
            "save_status": "saved",
        })

    for hook in ws.pending_hooks:
        hook_block_id = str(uuid.uuid4())
        hook_type = "HOOK" if hook.type.value in ("promise", "conflict") else "FORESHADOW"
        blocks.append({
            "id": hook_block_id,
            "project_id": book_id,
            "type": hook_type,
            "canvas_x": 800 + len(blocks) * 10,
            "canvas_y": 100 + len(blocks) * 8,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": False,
            "is_draft": False,
            "content": {
                "title": hook.description[:50] if hook.description else "",
                "hook_type": hook.type.value,
                "description": hook.description,
                "urgency": 5,
                "status": hook.status.value,
                "plant_chapter": hook.planted_in_chapter,
                "payoff_chapter": hook.resolved_in_chapter,
            },
            "save_status": "saved",
        })

    for rel in ws.relationships:
        rel_block_id = str(uuid.uuid4())
        blocks.append({
            "id": rel_block_id,
            "project_id": book_id,
            "type": "RELATIONSHIP",
            "canvas_x": 800,
            "canvas_y": 400 + len(blocks) * 8,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": False,
            "is_draft": False,
            "content": {
                "character_a_id": rel.character_a,
                "character_b_id": rel.character_b,
                "relationship_type": rel.type.value,
                "strength": rel.strength,
            },
            "save_status": "saved",
        })

    outline_data = None
    outline_path = sm.state_dir / "outline.json"
    if outline_path.exists():
        try:
            outline_data = json.loads(outline_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if outline_data and isinstance(outline_data, dict):
        synopsis_block_id = str(uuid.uuid4())
        blocks.append({
            "id": synopsis_block_id,
            "project_id": book_id,
            "type": "STORY_SYNOPSIS",
            "canvas_x": 100,
            "canvas_y": -100,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": True,
            "is_draft": False,
            "content": {
                "logline": outline_data.get("logline", ""),
                "genre": outline_data.get("genre", ""),
                "emotional_roadmap": outline_data.get("emotional_roadmap", ""),
            },
            "save_status": "saved",
        })

        story_outline_block_id = str(uuid.uuid4())
        sequences = outline_data.get("sequences", [])
        act1 = "\n".join(s.get("summary", "") for s in sequences if s.get("act") == 1)
        act2 = "\n".join(s.get("summary", "") for s in sequences if s.get("act") == 2)
        act3 = "\n".join(s.get("summary", "") for s in sequences if s.get("act") == 3)
        key_turning_points = []
        for s in sequences:
            for evt in s.get("key_events", []):
                key_turning_points.append(evt)
            hook = s.get("end_hook", "")
            if hook:
                key_turning_points.append(hook)
        blocks.append({
            "id": story_outline_block_id,
            "project_id": book_id,
            "type": "STORY_OUTLINE",
            "canvas_x": 100,
            "canvas_y": 0,
            "canvas_w": 280,
            "collapsed": False,
            "color": None,
            "timeline_id": None,
            "chapter_pos": None,
            "tags": "[]",
            "notes": "",
            "on_canvas": True,
            "is_draft": False,
            "content": {
                "title": outline_data.get("title", config.get("title", book_id)),
                "logline": outline_data.get("logline", ""),
                "genre": outline_data.get("genre", ""),
                "act1_summary": act1,
                "act2_summary": act2,
                "act3_summary": act3,
                "key_turning_points": "；".join(key_turning_points[:10]) if key_turning_points else "",
                "central_conflict": "",
                "climax_design": "",
                "ending_type": "",
                "emotional_roadmap": outline_data.get("emotional_roadmap", ""),
            },
            "save_status": "saved",
        })

    chapter_outlines_data = None
    co_path = sm.state_dir / "chapter_outlines.json"
    if co_path.exists():
        try:
            chapter_outlines_data = json.loads(co_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    chapters_json_list = []
    if chapter_outlines_data and isinstance(chapter_outlines_data, list):
        for co in chapter_outlines_data:
            if not isinstance(co, dict):
                continue
            ch_num = co.get("chapter_number", 0)
            co_block_id = str(uuid.uuid4())
            beats = co.get("beats", [])
            beat_fields = {}
            for bi, beat in enumerate(beats[:6], 1):
                beat_fields[f"beat{bi}_desc"] = beat.get("description", "") if isinstance(beat, dict) else str(beat)
            blocks.append({
                "id": co_block_id,
                "project_id": book_id,
                "type": "CHAPTER_OUTLINE",
                "canvas_x": 500 + len(blocks) * 10,
                "canvas_y": 200 + len(blocks) * 15,
                "canvas_w": 280,
                "collapsed": False,
                "color": None,
                "timeline_id": None,
                "chapter_pos": None,
                "tags": "[]",
                "notes": "",
                "on_canvas": True,
                "is_draft": False,
                "content": {
                    "chapter_number": ch_num,
                    "title": co.get("title", ""),
                    "summary": co.get("summary", ""),
                    "narrative_goal": co.get("mandatory_tasks", [""])[0] if co.get("mandatory_tasks") else "",
                    "dramatic_function": co.get("beats", [{}])[0].get("dramatic_function", "") if beats else "",
                    "pov_character": "",
                    "target_words": co.get("target_words", 4000),
                    "emotional_arc": str(co.get("emotional_arc", "")),
                    "status": "draft",
                    **beat_fields,
                },
                "save_status": "saved",
            })
            chapters_json_list.append({
                "chapter_num": ch_num,
                "title": co.get("title", ""),
                "timeline_id": None,
                "outline": co.get("summary", ""),
                "status": "planned",
                "word_count": 0,
                "block_refs": [co_block_id],
                "special_links": [],
                "audit_result": None,
            })

    metadata = {
        "storycanvas_version": "1.0",
        "project_id": book_id,
        "title": config.get("title", book_id),
        "created_at": config.get("created_at", ""),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_blocks": len(blocks),
            "total_chapters": ws.current_chapter,
            "total_words": 0,
        },
        "app_info": {
            "platform": "Dramatica-Flow",
            "version": "0.4.0",
        },
    }

    canvas = {
        "viewport": {"x": 0, "y": 0, "zoom": 1.0},
        "timeline_layout": {},
        "blocks": blocks,
        "connections": connections,
    }

    style_sig = {}
    if config.get("style_guide"):
        style_sig = {
            "style_guide": config["style_guide"],
            "forbidden_words": config.get("custom_forbidden_words", []),
        }

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".storycanvas", prefix=config.get("title", book_id))
    tmp_path = tmp.name
    tmp.close()

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        zf.writestr("canvas.json", json.dumps(canvas, ensure_ascii=False, indent=2))
        if style_sig:
            zf.writestr("style_signature.json", json.dumps(style_sig, ensure_ascii=False, indent=2))

        for f in sm.chapter_dir.glob("*_final.md"):
            ch_num_match = re.match(r"ch(\d+)_final\.md", f.name)
            if ch_num_match:
                ch_num = int(ch_num_match.group(1))
                zf.writestr(f"chapters/chapter_{ch_num:03d}.md", f.read_text(encoding="utf-8"))
                for ci, cj in enumerate(chapters_json_list):
                    if cj.get("chapter_num") == ch_num:
                        chapters_json_list[ci]["status"] = "generated"
                        word_count = len(f.read_text(encoding="utf-8"))
                        chapters_json_list[ci]["word_count"] = word_count
                        break

        if chapters_json_list:
            zf.writestr("chapters.json", json.dumps(chapters_json_list, ensure_ascii=False, indent=2))

        det_dir = sm.state_dir / "detailed_outlines"
        if det_dir.exists():
            for det_file in det_dir.glob("ch*.json"):
                zf.writestr(f"detailed_outlines/{det_file.name}", det_file.read_text(encoding="utf-8"))

    from fastapi.responses import Response
    from urllib.parse import quote
    filename = f"{config.get('title', book_id)}.storycanvas"
    encoded_filename = quote(filename)
    ascii_fallback = f"export_{book_id}.storycanvas"
    try:
        ascii_fallback.encode('latin-1')
    except UnicodeEncodeError:
        ascii_fallback = "export.storycanvas"

    with open(tmp_path, "rb") as f:
        file_bytes = f.read()

    return Response(
        content=file_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}"},
    )


@app.post("/api/import-storycanvas")
async def import_storycanvas(file: UploadFile = File(...)):
    """从 .storycanvas 文件导入项目到 Dramatica-Flow"""
    if not file.filename:
        raise HTTPException(400, "请上传文件")

    content = await file.read()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".storycanvas")
    tmp.write(content)
    tmp.close()

    try:
        with zipfile.ZipFile(tmp.name, "r") as zf:
            names = zf.namelist()

            canvas_data = {}
            if "canvas.json" in names:
                canvas_data = json.loads(zf.read("canvas.json"))
            if not isinstance(canvas_data, dict):
                canvas_data = {}

            metadata = {}
            if "metadata.json" in names:
                metadata = json.loads(zf.read("metadata.json"))
            if not isinstance(metadata, dict):
                metadata = {}

            style_sig = {}
            if "style_signature.json" in names:
                style_sig = json.loads(zf.read("style_signature.json"))
            if not isinstance(style_sig, dict):
                style_sig = {}

            title = metadata.get("title", "导入项目")
            book_id = title.replace(" ", "_").replace("/", "_").replace("\\", "_")[:20]

            existing = BOOKS_DIR / book_id
            if existing.exists():
                suffix = 1
                while (BOOKS_DIR / f"{book_id}_{suffix}").exists():
                    suffix += 1
                book_id = f"{book_id}_{suffix}"

            from core.state import StateManager
            from core.types.state import BookConfig

            style_guide = style_sig.get("style_guide", "")
            forbidden_words = style_sig.get("forbidden_words", [])

            config = BookConfig(
                id=book_id,
                title=title,
                genre="玄幻",
                target_words_per_chapter=4000,
                target_chapters=90,
                protagonist_id="",
                status="planning",
                created_at=datetime.now(timezone.utc).isoformat(),
                custom_forbidden_words=forbidden_words if isinstance(forbidden_words, list) else [],
                style_guide=style_guide,
            )
            sm = StateManager(PROJECT_ROOT, book_id)
            sm.init(config)

            blocks = canvas_data.get("blocks", [])
            connections = canvas_data.get("connections", [])

            characters = []
            locations = []
            factions = []
            events = []
            world_rules = []
            protagonist_id = ""
            story_synopsis_data = {}
            story_outline_data = {}
            chapter_outline_blocks = []

            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                content = block.get("content", {})
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        content = {}
                if not isinstance(content, dict):
                    content = {}
                on_canvas = block.get("on_canvas", False)

                if btype == "CHARACTER":
                    cid = block.get("id", str(uuid.uuid4()))[:12]
                    need_data = content.get("want", "")
                    internal = content.get("need", "")
                    personality = content.get("surface_personality", "")
                    personality_list = [p.strip() for p in personality.split("、") if p.strip()] if personality else []
                    role = content.get("role_archetype", "supporting")
                    if role in ("protagonist", "主角") and not protagonist_id:
                        protagonist_id = cid

                    characters.append({
                        "id": cid,
                        "name": content.get("name", "未命名角色"),
                        "role": role,
                        "need": {
                            "external": need_data,
                            "internal": internal,
                        },
                        "personality": personality_list,
                        "behavior_lock": content.get("behavior_lock", []),
                        "arc": content.get("arc", ""),
                        "backstory": content.get("appearance", ""),
                    })

                elif btype == "WORLDVIEW":
                    wname = content.get("world_name", "")
                    rules = content.get("fundamental_rules", [])
                    world_rules.extend(rules if isinstance(rules, list) else [str(rules)])

                elif btype == "FACTION":
                    factions.append({
                        "id": block.get("id", str(uuid.uuid4()))[:12],
                        "name": content.get("name", "未命名势力"),
                        "description": content.get("ideology", ""),
                        "stance": "中立",
                    })

                elif btype == "EVENT":
                    events.append({
                        "id": block.get("id", str(uuid.uuid4()))[:12],
                        "name": content.get("title", "未命名事件"),
                        "description": content.get("what_happens", ""),
                        "suggested_act": content.get("suggested_act", 1),
                        "suggested_function": content.get("suggested_function", "setup"),
                        "characters_involved": [],
                        "dramatic_question": "",
                    })

                elif btype in ("HOOK", "FORESHADOW"):
                    events.append({
                        "id": block.get("id", str(uuid.uuid4()))[:12],
                        "name": content.get("title", "伏笔"),
                        "description": content.get("description", ""),
                        "suggested_act": 1,
                        "suggested_function": "setup",
                        "characters_involved": [],
                        "dramatic_question": "",
                    })

                elif btype == "STORY_SYNOPSIS":
                    story_synopsis_data = content

                elif btype == "STORY_OUTLINE":
                    story_outline_data = content

                elif btype == "CHAPTER_OUTLINE":
                    chapter_outline_blocks.append(content)

            setup_dir = sm.book_dir / "setup"
            setup_dir.mkdir(parents=True, exist_ok=True)

            (setup_dir / "characters.json").write_text(
                json.dumps({"characters": characters}, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            world_json = {
                "locations": locations,
                "factions": factions,
                "rules": world_rules,
            }
            (setup_dir / "world.json").write_text(
                json.dumps(world_json, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            (setup_dir / "events.json").write_text(
                json.dumps({"events": events}, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # 创建 setup_state.json 以便前端识别"世界观已配置"
            setup_state = {
                "seed_event_id": events[0]["id"] if events else "",
                "characters": {},
                "locations": {},
                "factions": {},
                "world_rules": world_rules,
                "events": {},
            }
            for ch in characters:
                cid = ch["id"]
                setup_state["characters"][cid] = {
                    "id": cid,
                    "name": ch["name"],
                    "need": ch["need"],
                    "obstacles": [],
                    "worldview": {"power": "seeks", "trust": "suspicious", "coping": "fight"},
                    "arc": ch.get("arc", "positive"),
                    "profile": ch.get("backstory", ""),
                    "behavior_lock": ch.get("behavior_lock", []),
                    "role": ch.get("role", "supporting"),
                    "personality": ch.get("personality", []),
                    "backstory": ch.get("backstory", ""),
                    "current_goal": "",
                    "hidden_agenda": "",
                }
            for fac in factions:
                fid = fac["id"]
                setup_state["factions"][fid] = {
                    "id": fid,
                    "name": fac["name"],
                    "description": fac.get("description", ""),
                    "stance": fac.get("stance", "中立"),
                }
            for evt in events:
                eid = evt["id"]
                setup_state["events"][eid] = {
                    "id": eid,
                    "name": evt["name"],
                    "description": evt.get("description", ""),
                    "suggested_act": evt.get("suggested_act", 1),
                    "suggested_function": evt.get("suggested_function", "setup"),
                    "characters_involved": evt.get("characters_involved", []),
                    "dramatic_question": evt.get("dramatic_question", ""),
                }
            sm.state_dir.mkdir(parents=True, exist_ok=True)
            (sm.state_dir / "setup_state.json").write_text(
                json.dumps(setup_state, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if protagonist_id:
                cfg_data = sm.read_config()
                cfg_data["protagonist_id"] = protagonist_id
                sm._write_json("config.json", cfg_data)

            chapter_files = sorted([n for n in names if n.startswith("chapters/") and n.endswith(".md")])
            imported_chapters = 0
            for ch_file in chapter_files:
                ch_match = re.search(r"chapter[_\-]?(\d+)", ch_file, re.IGNORECASE)
                if ch_match:
                    ch_num = int(ch_match.group(1))
                    ch_content = zf.read(ch_file).decode("utf-8")
                    final_path = sm.chapter_dir / f"ch{ch_num:04d}_final.md"
                    final_path.write_text(ch_content, encoding="utf-8")
                    imported_chapters += 1

            # 导入故事大纲 (outline.json)
            imported_outline = 0
            if story_outline_data or story_synopsis_data:
                outline_obj = {
                    "id": f"outline_{book_id}",
                    "title": story_outline_data.get("title", title) if story_outline_data else title,
                    "logline": story_outline_data.get("logline", "") or story_synopsis_data.get("logline", ""),
                    "genre": story_outline_data.get("genre", "") or story_synopsis_data.get("genre", ""),
                    "sequences": [],
                    "emotional_roadmap": story_outline_data.get("emotional_roadmap", "") or story_synopsis_data.get("emotional_roadmap", ""),
                }
                act_summaries = {
                    1: story_outline_data.get("act1_summary", ""),
                    2: story_outline_data.get("act2_summary", ""),
                    3: story_outline_data.get("act3_summary", ""),
                }
                for act_num in (1, 2, 3):
                    summary = act_summaries.get(act_num, "")
                    if summary:
                        outline_obj["sequences"].append({
                            "id": f"seq_act{act_num}",
                            "number": act_num,
                            "act": act_num,
                            "summary": summary,
                            "narrative_goal": "",
                            "dramatic_function": "setup" if act_num == 1 else ("turning" if act_num == 2 else "climax"),
                            "key_events": [],
                            "estimated_scenes": 0,
                            "end_hook": "",
                        })
                (sm.state_dir / "outline.json").write_text(
                    json.dumps(outline_obj, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                imported_outline = 1

            # 导入章节大纲 (chapter_outlines.json)
            imported_chapter_outlines = 0
            if chapter_outline_blocks:
                co_list = []
                for co in sorted(chapter_outline_blocks, key=lambda x: x.get("chapter_number", 0)):
                    ch_num = co.get("chapter_number", 0)
                    beats = []
                    for bi in range(1, 7):
                        desc = co.get(f"beat{bi}_desc", "")
                        if desc:
                            beats.append({
                                "id": f"beat_{ch_num}_{bi}",
                                "description": desc,
                                "dramatic_function": co.get("dramatic_function", "setup") if bi == 1 else "",
                            })
                    co_list.append({
                        "chapter_number": ch_num,
                        "title": co.get("title", ""),
                        "summary": co.get("summary", ""),
                        "sequence_id": "",
                        "beats": beats,
                        "emotional_arc": {"start": "", "end": co.get("emotional_arc", "")},
                        "mandatory_tasks": [co.get("narrative_goal", "")] if co.get("narrative_goal") else [],
                        "target_words": co.get("target_words", 4000),
                    })
                (sm.state_dir / "chapter_outlines.json").write_text(
                    json.dumps(co_list, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                imported_chapter_outlines = len(co_list)

            # 导入章节细纲 (detailed_outlines/*.json)
            imported_detailed_outlines = 0
            det_files = [n for n in names if n.startswith("detailed_outlines/") and n.endswith(".json")]
            for det_file in det_files:
                det_match = re.search(r"ch(\d+)", det_file, re.IGNORECASE)
                if det_match:
                    try:
                        det_data = json.loads(zf.read(det_file).decode("utf-8"))
                        det_dir = sm.state_dir / "detailed_outlines"
                        det_dir.mkdir(parents=True, exist_ok=True)
                        det_name = os.path.basename(det_file)
                        (det_dir / det_name).write_text(
                            json.dumps(det_data, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        imported_detailed_outlines += 1
                    except Exception:
                        pass

            return {
                "ok": True,
                "book_id": book_id,
                "title": title,
                "imported": {
                    "characters": len(characters),
                    "factions": len(factions),
                    "events": len(events),
                    "chapters": imported_chapters,
                    "world_rules": len(world_rules),
                    "story_outline": imported_outline,
                    "chapter_outlines": imported_chapter_outlines,
                    "detailed_outlines": imported_detailed_outlines,
                },
            }

    except zipfile.BadZipFile:
        raise HTTPException(400, "无效的 .storycanvas 文件（不是有效的 ZIP）")
    except Exception as e:
        raise HTTPException(500, f"导入失败：{str(e)}")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
