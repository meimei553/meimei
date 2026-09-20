"""封装智谱 GLM 的调用。

演示模式：没有配置 API Key 时，不真正调用 GLM，
由调用方返回内置示例数据（方便先跑通整个流程）。
"""
import json
import re

from backend import config


def chat(messages: list[dict], model: str, temperature: float = 0.7) -> str:
    """调用 GLM 对话接口，返回纯文本结果。

    messages: 对话消息列表，格式 [{"role": "system", "content": "..."}, ...]
    temperature: 随机性，越低输出越稳定（分析任务用低值，润色用高值）
    """
    from zai import ZhipuAiClient  # 延迟导入，演示模式下不依赖 SDK

    client = ZhipuAiClient(api_key=config.ZAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def chat_json(messages: list[dict], model: str, temperature: float = 0.3) -> dict:
    """调用 GLM 并把返回内容解析为 JSON 字典。

    AI 有时会把 JSON 包在 ```json ... ``` 代码块里，这里做了容错处理。
    """
    text = chat(messages, model, temperature)
    # 去掉可能存在的 markdown 代码块包裹
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"AI 返回的内容不是 JSON：{text[:200]}")
    return json.loads(match.group())
