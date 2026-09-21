"""FastAPI 应用入口。

本地运行方式（在项目根目录执行）：
    uvicorn backend.main:app --reload
然后浏览器访问 http://127.0.0.1:8000/docs 可以看到自动生成的接口测试页面。

分枝路由在后续节点注册到这里：
节点 1 分析 analyze / 节点 2 反思对话 chat / 节点 3 润色 polish / 节点 4 记录与设置
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config, storage
from backend.analyze import router as analyze_router

app = FastAPI(
    title="meimei 情绪分析 API",
    description="私密的对话记录情绪分析工具：先理解情绪，再温柔润色。",
    version="0.1.0",
)

# 注册分枝路由（后续节点在此追加）
app.include_router(analyze_router)

# 开发期允许所有来源跨域访问（小程序开发者工具调试需要）；正式上线前收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    """服务启动时初始化数据库表（不存在则创建）。"""
    storage.init_db()


@app.get("/api/health")
def health() -> dict:
    """健康检查接口：确认服务已启动，并报告当前运行模式。"""
    return {
        "status": "ok",
        "demo_mode": config.is_demo_mode(),
        "model_analyze": config.MODEL_ANALYZE,
        "model_polish": config.MODEL_POLISH,
        "model_chat": config.MODEL_CHAT,
    }
