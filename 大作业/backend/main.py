# 小航阅读小伙伴 · FastAPI 后端
#
# 把 xiaohang_agent_v2.py 的状态机逻辑包装成无状态的 API
# 前端每次请求带上 session_id，后端维护每个 session 的状态
#
# 危机转介在入口/出口各拦截一次
import os
import json
import uuid
import pathlib
from typing import Optional
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ---- 配置（全部从环境变量读）----
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
DATA_DIR = pathlib.Path(os.getenv("DATA_DIR", str(pathlib.Path(__file__).parent.parent)))

# 当前文件所在目录
HERE = pathlib.Path(__file__).parent

# ---- 危机检测（确定性拦截）----
CRISIS_PATTERNS = [
    "自杀", "想死", "不想活", "活着没意思", "活不下去", "撑不下去", "撑不住了",
    "好笨", "我太笨了", "我很笨", "我读不好", "别人都能我不会",
    "解脱", "伤害自己", "自残", "不敢回家", "有人伤害我",
]

CRISIS_REPLY = (
    "我们先不读了，没关系的。\n\n"
    "如果你有需要，一定要告诉爸爸妈妈、老师或学校心理老师。\n"
    "也可以拨打心理援助热线：**400-161-9995**（24小时）。"
)

def is_crisis(text: str) -> bool:
    return any(p in text for p in CRISIS_PATTERNS)


# ---- 优雅降级 ----
FALLBACK_REPLY = (
    "哎呀，我今天有点忙不过来，可能网络不太稳定。"
    "你可以深呼吸三次，稍等一下再和我说说，或者找老师帮忙好吗？"
)


# ---- 调模型 ----
def call_model(messages: list) -> Optional[str]:
    if not DEEPSEEK_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[错误] 调用模型失败: {e}")
        return None


# ---- 导入核心逻辑 ----
import sys
sys.path.insert(0, str(HERE))  # xiaohang_agent_v2.py 在同一目录
from xiaohang_agent_v2 import (
    ReadingBuddyV2,
    load_char_table,
    load_freq_table,
    load_prop_table,
    load_text_library,
)

# 预加载数据
try:
    CHAR_MAP = load_char_table()
    FREQ_MAP = load_freq_table()
    PROP_MAP = load_prop_table()
    TEXT_LIBRARY = load_text_library()
    DATA_LOADED = True
    print("[系统] 数据文件加载成功")
except Exception as e:
    print(f"[警告] 数据文件加载失败: {e}")
    CHAR_MAP = {}
    FREQ_MAP = {}
    PROP_MAP = {}
    TEXT_LIBRARY = {}
    DATA_LOADED = False


# ---- 会话管理（内存存储，生产环境建议用 Redis）----
sessions: dict[str, ReadingBuddyV2] = {}


def get_or_create_session(session_id: Optional[str]) -> tuple[str, ReadingBuddyV2]:
    """获取或创建会话"""
    if session_id and session_id in sessions:
        return session_id, sessions[session_id]
    new_id = session_id or str(uuid.uuid4())[:8]
    sessions[new_id] = ReadingBuddyV2(load_history_on_start=False)
    return new_id, sessions[new_id]


# ---- FastAPI 应用 ----
app = FastAPI(
    title="小航阅读小伙伴 · 后端",
    description="识读率测验 + 智能推荐的阅读伙伴 API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 请求/响应模型 ----
class ChatIn(BaseModel):
    session_id: Optional[str] = None  # 前端传 None 表示新会话
    message: str  # 当前用户输入


class ChatOut(BaseModel):
    session_id: str
    reply: str
    state: str  # 当前状态（用于前端调试/流程控制）
    meta: dict


# ---- 接口 ----
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model": DEEPSEEK_MODEL,
        "has_key": bool(DEEPSEEK_API_KEY),
        "data_loaded": DATA_LOADED,
        "active_sessions": len(sessions),
    }


@app.post("/api/chat", response_model=ChatOut)
def chat(body: ChatIn):
    # 1) 入口危机检测
    if is_crisis(body.message):
        return ChatOut(
            session_id=body.session_id or "new",
            reply=CRISIS_REPLY,
            state="CRISIS",
            meta={"crisis": True, "source": "deterministic"}
        )

    # 2) 获取或创建会话
    session_id, buddy = get_or_create_session(body.session_id)

    # 3) 检查数据
    if not DATA_LOADED:
        return ChatOut(
            session_id=session_id,
            reply=FALLBACK_REPLY,
            state=buddy.state,
            meta={"crisis": False, "error": "data_not_loaded"}
        )

    # 4) 调用 agent 处理
    reply, is_system = buddy.reply(body.message)

    # 5) 出口危机检测
    if is_crisis(reply):
        return ChatOut(
            session_id=session_id,
            reply=CRISIS_REPLY,
            state="CRISIS",
            meta={"crisis": True, "source": "output_review"}
        )

    return ChatOut(
        session_id=session_id,
        reply=reply,
        state=buddy.state,
        meta={"crisis": False, "is_system": is_system}
    )


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    """删除会话（可选）"""
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "ok", "message": "会话已删除"}
    return {"status": "not_found", "message": "会话不存在"}


# ---- 启动提示 ----
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("小航阅读小伙伴 · FastAPI 后端")
    print("=" * 50)
    print(f"API Key: {'已配置' if DEEPSEEK_API_KEY else '❌ 未配置'}")
    print(f"数据文件: {'已加载' if DATA_LOADED else '❌ 未加载'}")
    print(f"CORS: {CORS_ORIGINS}")
    print(f"会话数: {len(sessions)}")
    print("=" * 50)
    print("启动命令: uvicorn main:app --reload --port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# MIT License | 郑先隽，北师大心理学部教授，人本 AI 设计与创新
