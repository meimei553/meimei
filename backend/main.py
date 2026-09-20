"""FastAPI 应用入口。

本地运行方式（在项目根目录执行）：
    uvicorn backend.main:app --reload
然后打开浏览器访问 http://127.0.0.1:8000/docs 可以看到自动生成的接口测试页面。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.analyze import router as analyze_router
from backend.polish import router as polish_router

app = FastAPI(
    title="meimei 情绪分析 API",
    description="私密的对话记录情绪分析工具：先分析情绪，再温柔润色。",
    version="0.1.0",
)

# 开发期允许所有来源跨域访问（小程序开发者工具调试需要）；
# 正式上线前应收紧为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各功能模块的路由
app.include_router(analyze_router)
app.include_router(polish_router)


@app.get("/api/health")
def health() -> dict:
    """健康检查接口：确认服务已启动，并报告当前运行模式。"""
    return {
        "status": "ok",
        "demo_mode": config.is_demo_mode(),
        "model_analyze": config.MODEL_ANALYZE,
        "model_polish": config.MODEL_POLISH,
    }
