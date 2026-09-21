"""配置层：集中管理所有配置，从环境变量或 .env 文件读取。

.env 文件存放 API Key 等私密信息，已被 .gitignore 排除，永远不会提交。
"""
import os

from dotenv import load_dotenv

# 启动时自动读取项目根目录下的 .env 文件
load_dotenv()

# 智谱 GLM 的 API Key（没有配置时会自动进入演示模式）
ZAI_API_KEY: str = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL: str = os.getenv("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# 各模块使用的模型（glm-4.7-flash 免费，适合开发期；上架前需切换付费模型）
MODEL_ANALYZE: str = os.getenv("MODEL_ANALYZE", "glm-4.7-flash")
MODEL_POLISH: str = os.getenv("MODEL_POLISH", "glm-4.7-flash")
MODEL_CHAT: str = os.getenv("MODEL_CHAT", "glm-4.7-flash")

# 演示模式：auto=没有 Key 时自动启用；on=强制演示；off=强制关闭
DEMO_MODE: str = os.getenv("DEMO_MODE", "auto")

# SQLite 数据库文件路径
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "meimei.db")

# 单次输入长度上限（决策：5000 字，防费用失控和超时）
MAX_INPUT_LENGTH: int = 5000

# 对话上下文压缩阈值（超过约 20 轮自动压缩早期对话，控制费用）
CHAT_COMPRESS_THRESHOLD: int = 20


# .env 模板里的占位符（未填入真实 Key 时视为未配置）
KEY_PLACEHOLDER = "在这里填入你的APIKey"


def is_demo_mode() -> bool:
    """判断当前是否处于演示模式（不真正调用 GLM，返回内置示例数据）。"""
    if DEMO_MODE == "on":
        return True
    if DEMO_MODE == "off":
        return False
    # auto：未配置 Key、Key 还是占位符、或格式明显不对（真实 Key 格式为 id.secret）时进入演示模式
    if not ZAI_API_KEY or ZAI_API_KEY == KEY_PLACEHOLDER:
        return True
    return "." not in ZAI_API_KEY
