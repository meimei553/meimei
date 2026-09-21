# meimei
a rope for little but unwavering start

项目方案（决策记录）：[PLAN.md](PLAN.md) ｜ 总设计图（施工图）：[BLUEPRINT.md](BLUEPRINT.md)

合规文件：[隐私政策](PRIVACY.md) ｜ [用户协议与免责声明](USER_AGREEMENT.md) ｜ [开源协议 MIT](LICENSE)

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key：复制 .env.example 改名为 .env，填入你的智谱 GLM Key
#    （没有 Key 也能跑：自动进入演示模式，返回内置示例数据）
cp .env.example .env

# 3. 启动后端
uvicorn backend.main:app --reload

# 4. 浏览器打开接口测试页面
#    http://127.0.0.1:8000/docs
```

## 小程序联调（最小骨架）

1. 先启动后端（见上）
2. 微信开发者工具导入 `miniprogram/` 目录（AppID 填在 `project.config.json`）
3. 开发者工具勾选：详情 → 本地设置 → 不校验合法域名（仅开发期）
4. 真机预览：把 `miniprogram/app.js` 里的 `apiBase` 改成电脑局域网 IP

## 目录结构

```
backend/        Python 后端（FastAPI）：主干五层 + 四个功能分枝
miniprogram/    微信小程序前端（6 页最小骨架，UI 二期美化）
tests/          温柔回归测试集
```
