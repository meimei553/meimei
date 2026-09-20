# meimei

a rope for little but unwavering start

一个私密的对话记录情绪分析工具：把聊天记录或"气话"交给 AI，
它先温柔地帮你分析情绪（情绪雷达图 + 当时为什么这样说），
再把话润色成高情商版本，陪你反思、记录，换一种说法。

## 技术栈

- 后端：Python + FastAPI（自带接口测试页面）
- AI：智谱 GLM（`zai-sdk`，开发期使用免费的 glm-4.7-flash）
- 存储：SQLite（零配置）
- 前端（二期）：微信小程序

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（可选：没有 Key 会自动进入演示模式，返回示例数据）
cp .env.example .env
# 编辑 .env，填入你在 https://open.bigmodel.cn 创建的 API Key

# 3. 启动后端
uvicorn backend.main:app --reload

# 4. 打开接口测试页面
# 浏览器访问 http://127.0.0.1:8000/docs
```

## 目录结构

```
backend/        Python 后端（FastAPI）
miniprogram/    微信小程序前端（当前为最小骨架，UI 设计二期再讨论）
```

## 小程序联调（最小骨架）

1. 先启动后端：`uvicorn backend.main:app --reload`
2. 用微信开发者工具导入 `miniprogram/` 目录（AppID 在 project.config.json 里填）
3. 开发者工具里勾选：详情 → 本地设置 → 不校验合法域名（仅开发期）
4. 如果后端跑在电脑上、用手机预览，把 `miniprogram/app.js` 里的
   `apiBase` 从 `127.0.0.1` 改成电脑的局域网 IP（如 `192.168.x.x`）

## 隐私说明

- `.env`（API Key）和 `*.db`（聊天记录数据库）均已被 .gitignore 排除，不会提交到 GitHub
- 聊天记录属于高度敏感数据，请妥善保管数据库文件
