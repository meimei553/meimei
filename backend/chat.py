"""反思对话分枝：POST /api/chat（施工图节点 2）。

分析后的对话：AI 携带完整上下文（原文 + 分析结果 + 对话历史），
引用原话解释依据、平等讨论改分（留痕）、永不主动收尾。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import config, glm_client, prompts, safety, storage

router = APIRouter(prefix="/api", tags=["反思对话"])


class ChatRequest(BaseModel):
    """对话接口的请求参数。"""

    record_id: int = Field(..., description="分析接口返回的记录 id")
    message: str = Field(..., description="用户想说的话")


class ChatResponse(BaseModel):
    """对话接口的返回结果。"""

    reply: str = Field(..., description="AI 的回应")
    score_revision: dict | None = Field(default=None, description="改分信息（讨论后 AI 判断要改分时给出，原分数保留）")
    rumination_detected: bool = Field(default=False, description="反刍检测：发现用户原地打转")
    crisis: bool = Field(default=False, description="是否命中危机信号")
    crisis_response: str | None = None
    round: int = Field(..., description="当前是第几轮对话")
    demo: bool = Field(..., description="是否演示数据")


def _build_context(record: dict) -> str:
    """把记录的原文和分析结果组装成上下文，让 AI 始终"记得"自己的分析。"""
    parts = [f"【用户当时粘贴的内容】\n{record['original_text']}"]
    if record.get("background"):
        parts.append(f"【背景】\n{record['background']}")
    analysis = record.get("analysis")
    if analysis:
        emotions = "、".join(
            f"{e['name']}占{e['percent']}%" for e in analysis.get("emotions", [])
        )
        parts.append(
            f"【你之前的分析结果】\n情绪：{emotions}\n"
            f"解读：{analysis.get('my_analysis', '')}\n"
            f"对方推测：{analysis.get('other_analysis', '')}\n"
            f"总结：{analysis.get('summary', '')}"
        )
    # 称呼系统：用户设置过称呼时，对话里用这个称呼（决策 13）
    nickname = storage.get_setting("user_nickname")
    if nickname:
        parts.append(f"【用户称呼】\n回应时请称呼用户为“{nickname}”")
    return "\n\n".join(parts)


def _compress_history(history: list[dict]) -> list[dict]:
    """对话超过阈值时，把早期对话压缩为摘要（控制费用，用户无感知）。

    保留最近 10 条原文，更早的压缩成一段摘要放在开头。
    """
    if len(history) <= config.CHAT_COMPRESS_THRESHOLD * 2:
        return history
    early = history[:-10]
    early_text = "\n".join(f"{'用户' if m['role'] == 'user' else '我'}：{m['content']}" for m in early)
    try:
        summary = glm_client.chat(
            messages=[{"role": "system", "content": prompts.CHAT_COMPRESS_PROMPT},
                      {"role": "user", "content": early_text}],
            model=config.MODEL_CHAT, temperature=0.3,
        )
    except Exception:
        # 压缩失败时退化为简单截断，保证对话不中断
        summary = early_text[:500] + "……（早期对话略）"
    return [{"role": "system", "content": f"【早期对话摘要】\n{summary}"}] + history[-10:]


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """和用户进行反思对话。"""
    record = storage.get_record(req.record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在，请先分析再对话")

    # 防线：输入校验 + 危机关键词（对话中同样守护）
    input_error = safety.check_input(req.message)
    if input_error:
        raise HTTPException(status_code=400, detail=input_error)
    if safety.check_crisis(req.message):
        return ChatResponse(reply=prompts.CRISIS_RESPONSE, crisis=True,
                            crisis_response=prompts.CRISIS_RESPONSE,
                            round=_next_round(record), demo=config.is_demo_mode())

    history = record.get("chat_history") or []

    if config.is_demo_mode():
        # 演示模式：温柔示例回应（引用原话的形式）
        reply = (
            f"我注意到你当时说「{record['original_text'][:20]}」——这句话里藏着的东西，"
            "比我们看到的更多。你愿意多说一点当时的感受吗？我听着。"
        )
        _append_and_save(req.record_id, history, req.message, reply)
        return ChatResponse(reply=reply, round=len(history) // 2 + 1, demo=True)

    # 真实模式：组装 人设+上下文+历史+新消息
    messages = [
        {"role": "system", "content": prompts.CHAT_PROMPT},
        {"role": "system", "content": _build_context(record)},
        *_compress_history(history),
        {"role": "user", "content": req.message},
    ]
    try:
        result = glm_client.chat_json(messages, model=config.MODEL_CHAT, temperature=0.7)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"我刚刚走神了，我们再试一次好吗？（{exc}）") from exc

    reply = result.get("reply", "")
    score_revision = result.get("score_revision")

    # 改分留痕：追加到修改轨迹，原分数永不覆盖（决策 36）
    if score_revision:
        revisions = record.get("score_revisions") or []
        revisions.append(score_revision)
        storage.update_record_json(req.record_id, "score_revisions_json", revisions)

    _append_and_save(req.record_id, history, req.message, reply)

    # 对话中的隐晦危机信号（AI 第二重保险）
    crisis = bool(result.get("crisis_detected", False))
    return ChatResponse(
        reply=prompts.CRISIS_RESPONSE if crisis else reply,
        score_revision=score_revision,
        rumination_detected=bool(result.get("rumination_detected", False)),
        crisis=crisis,
        crisis_response=prompts.CRISIS_RESPONSE if crisis else None,
        round=len(history) // 2 + 1,
        demo=False,
    )


def _next_round(record: dict) -> int:
    """计算下一轮对话的轮次。"""
    return len(record.get("chat_history") or []) // 2 + 1


def _append_and_save(record_id: int, history: list[dict], user_msg: str, reply: str) -> None:
    """把这一轮对话追加到历史并存入记录（决策：对话内容自动存入记录）。"""
    history = history + [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": reply},
    ]
    storage.update_record_json(record_id, "chat_history_json", history)
