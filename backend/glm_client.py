"""AI 调用层：全项目唯一的 GLM 出入口。

所有模块要调用 GLM 都必须经过这里，统一负责：
- 组装请求、读取配置
- 把 AI 返回的文本解析为 JSON（带容错：AI 有时会把 JSON 包在 markdown 代码块里）
- 失败重试 1 次（网络抖动或格式错误时给第二次机会）
"""
import json
import re
import time

from backend import config


def chat(messages: list[dict], model: str, temperature: float = 0.7) -> str:
    """调用 GLM 对话接口，返回纯文本结果。

    messages: 对话消息列表，格式 [{"role": "system", "content": "..."}, ...]
    temperature: 随机性。越低输出越稳定（分析任务用低值），越高越灵动（对话用高值）
    """
    # 延迟导入：演示模式下不需要 SDK，避免无 Key 环境报错
    from zai import ZhipuAiClient

    client = ZhipuAiClient(api_key=config.ZAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        # 关闭深度思考模式：开着时一次分析要约 70 秒，关掉后大幅提速，
        # 对情绪分析这类任务质量影响很小（验证实测）
        thinking={"type": "disabled"},
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> dict:
    """从 AI 返回的文本中提取 JSON 对象（容错处理 markdown 代码块包裹的情况）。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"AI 返回的内容不含 JSON：{text[:200]}")
    return json.loads(match.group())


def chat_json(messages: list[dict], model: str, temperature: float = 0.3) -> dict:
    """调用 GLM 并把返回内容解析为 JSON 字典；失败时重试 1 次。

    开启强制 JSON 模式（response_format）：对话场景下模型容易"聊嗨了"
    直接输出散文，此参数保证返回合法 JSON（验证时抓获的真实问题）。
    免费模型输出长 JSON 时偶尔格式出错，重试一次能解决大部分偶发失败。
    """
    # 延迟导入：演示模式下不需要 SDK
    from zai import ZhipuAiClient

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            client = ZhipuAiClient(api_key=config.ZAI_API_KEY)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                thinking={"type": "disabled"},
                response_format={"type": "json_object"},
            )
            return _extract_json(response.choices[0].message.content)
        except Exception as exc:  # 解析失败或调用失败都重试一次
            last_error = exc
            if attempt == 0:
                time.sleep(1)  # 稍等再试，避开瞬时抖动
    raise ValueError(f"GLM 调用或 JSON 解析失败（已重试 1 次）：{last_error}")
