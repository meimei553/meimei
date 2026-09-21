"""安全边界层：四道防线的代码部分。

防线 0：危机识别（关键词表 + 后续节点接入 AI 判断，双保险）
防线 1：输入前置校验（空、超长、乱码——不花 AI 费用就拦下）
防线 2：读不懂的内容（由 AI 在 prompt 层判断，见 analyze 模块）
防线 3：恶意内容（上线前接入微信 msgSecCheck，此处预留接口）

所有边界回应都要温柔，不冷冰冰地报错（决策：全程保持人设）。
"""
import re

from backend import config

# 危机关键词表（防线 0 的第一重保险；AI 判断在分析模块里做第二重）
# 注意：词表要覆盖隐晦表达，但宁可误报给温柔回应，也不可漏报
CRISIS_KEYWORDS: list[str] = [
    "自杀", "不想活", "活不下去", "轻生", "自残", "自伤", "割腕",
    "结束生命", "想死", "死了算了", "活着没意思", "离开这个世界",
    "永远不醒", "不想醒来",
]


def check_input(text: str) -> str | None:
    """输入前置校验（防线 1）。

    返回 None 表示通过；否则返回一段温柔的提示文案（不调用 AI，直接返回）。
    """
    stripped = text.strip()
    if not stripped:
        return "好像还没有写内容？把聊天记录或心里那句话放进来吧。"
    if len(stripped) > config.MAX_INPUT_LENGTH:
        return (
            f"这段话有点长（超过 {config.MAX_INPUT_LENGTH} 字了）。"
            "可以先截取最关键的部分给我，我们一段一段来。"
        )
    # 乱码检测：如果可读字符（中文、常见标点、字母数字）占比过低，视为乱码
    # 注意：中文引号用实际字符“”‘’，避免与 Python 字符串定界符冲突
    readable = re.findall(r'[一-鿿\w\s，。！？、；：‘’“”（）……—~·,.!?;:()\[\]\-]', stripped)
    if len(stripped) > 10 and len(readable) / len(stripped) < 0.5:
        return "这段话我有点没看懂。能和我说说发生了什么吗？想到哪说到哪就好。"
    return None


def check_crisis(text: str) -> bool:
    """危机关键词检测（防线 0 的第一重保险）。

    命中即返回 True——调用方应中断常规分析，改走危机回应流程。
    """
    return any(keyword in text for keyword in CRISIS_KEYWORDS)


def check_content_security(text: str) -> bool:
    """内容安全检测（防线 3，上架前接入微信 msgSecCheck）。

    MVP 单机阶段不启用，预留接口；返回 True 表示通过。
    """
    return True
