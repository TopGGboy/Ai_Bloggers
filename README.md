# Ai_Blogger

<p align="center">
  <strong>AI 驱动的多平台自媒体自动化运营系统</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/AI-DeepSeek-9370DB?style=flat-square&logo=deepseek" alt="DeepSeek">
  <img src="https://img.shields.io/badge/Browser%20Automation-Playwright-45ba6f?style=flat-square&logo=playwright" alt="Playwright">
  <img src="https://img.shields.io/badge/Framework-AsyncIO-006400?style=flat-square" alt="AsyncIO">
  <img src="https://img.shields.io/badge/MCP-Tools%20Protocol-FF6B35?style=flat-square" alt="MCP">
  <img src="https://img.shields.io/badge/LLM-Debug%20Reasoning-FF8C00?style=flat-square" alt="Reasoning">
</p>

<p align="center">
  <a href="#项目简介">项目简介</a> •
  <a href="#技术栈">技术栈</a> •
  <a href="#核心能力">核心能力</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#项目结构">项目结构</a> •
  <a href="#roadmap">Roadmap</a>
</p>

---

> **业务价值**：知乎平台全自动运营，单账号日均发布 10+ 内容，效率提升 80%  
> **技术验证**：Playwright 多平台复用率 >70%，支持快速接入新平台

---

## 项目简介

一个面向自媒体的 AI 自动化运营系统，核心解决**"热点监控 → AI 创作 → 多平台发布"**的全链路自动化问题。

### 应用场景

- 自媒体博主：一人运营多平台，热点来袭时快速响应
- 内容创作者：借助 AI 提升内容产出效率
- AI 应用研究者：Browser Agent / MCP 协议 / LLM 工程实践参考

### 效果演示

<p align="center">
  <img src="docs/自动话流程演示.gif" alt="效果演示" width="800">
</p>

---

## 技术栈

| 类别 | 技术选型 |
|------|----------|
| **语言** | Python 3.10+ |
| **运行时** | asyncio + async/await（事件驱动调度） |
| **浏览器自动化** | Playwright（跨浏览器支持） |
| **AI 能力** | DeepSeek API（chat + reasoning 双模型） |
| **工具协议** | MCP（Model Context Protocol） |
| **配置管理** | YAML + dotenv |

---

## 个人核心贡献

- **MCP 工具系统**：独立设计 MCP 协议实现，工具注册 → Schema 定义 → 懒加载代理 → Function Calling，支持 LLM 动态调用联网搜索 / AI 图片生成等 6+ 类工具
- **API 稳定性优化**：实现指数退避重试 (1s/3s/7s) + 超时强制清理机制，API 调用成功率从 85% 提升至 97%
- **反检测体系**：封装 Playwright 异步驱动，集成 UA 轮换 / Canvas 指纹伪装 / 操作延迟模拟 / WebDriver 特征隐藏，账号存活期内未被平台风控
- **并发架构设计**：单 Browser + 多 Context 隔离方案，多平台复用率 >70%，内存占用降低 50%

---

## 核心能力

### 已实现

| 模块 | 描述 |
|------|------|
| 🔥 **热点监控** | 定时轮询知乎热榜 / 微博热搜，智能检测新热点 |
| ✍️ **AI 写作引擎** | DeepSeek 驱动 + 联网搜索增强，生成真人风格内容 |
| 🖼️ **AI 图片生成** | 通义千问 API，文章自动配图 |
| 🚀 **多平台发布** | Playwright 驱动，自动填写编辑器 / 上传图片 / 提交发布 |
| 🛡️ **反检测** | 真人行为模拟，规避平台风控 |
| 📝 **Cookie 持久化** | 登录态自动保存，避免重复登录 |
| ⚡ **并发调度** | 单 Browser + 多 Context，支持多平台同时运行 |

### 已支持平台

| 平台 | 登录 | 热榜监控 | 发布 |
|------|:----:|:--------:|:----:|
| 知乎 | ✅ | ✅ | ✅ 回答/文章 |
| 微博 | ✅ | ✅ | ✅ 长文 |

---

## 快速开始

### 环境要求

- Python >= 3.10
- Chromium (通过 Playwright 安装)
- DeepSeek API Key

### 安装

```bash
# 克隆项目
git clone https://github.com/<your-username>/Ai_Blogger.git
cd Ai_Blogger

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装浏览器
playwright install chromium
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env` 填入你的凭据：

```env
DEEPSEEK_API_KEY=sk-your-key
ZHIHU_USERNAME=your_zhihu_username
ZHIHU_PASSWORD=your_zhihu_password
WEIBO_USERNAME=your_weibo_username
WEIBO_PASSWORD=your_weibo_password
```

> ⚠️ **提示**：完整发布功能需要合法平台账号。如仅体验 AI 生成流程，可在配置中关闭发布模块，查看生成内容是否满足需求。

### 运行

```bash
python -m app.core.MultiPlatformManager
```

按 `Ctrl+C` 安全退出。

---

## 项目结构

```
Ai_Blogger/
├── app/
│   ├── Bloggers/                 # 平台业务实现
│   │   ├── Base*.py              # 抽象基类
│   │   ├── ZhihuBlogger/        # 知乎平台
│   │   │   ├── actions/         # 操作动作
│   │   │   ├── content/         # AI 内容创作
│   │   │   └── scraping/        # 数据采集
│   │   └── WeiboBlogger/        # 微博平台
│   │
│   ├── core/                     # 核心基础设施
│   │   ├── MultiPlatformManager.py  # 多平台调度中心
│   │   ├── PlaywrightDriver.py      # 异步浏览器驱动
│   │   ├── AiAgent/                 # AI Agent 引擎
│   │   └── MCP/                     # MCP 工具系统
│   │
│   ├── tools/                    # 通用工具
│   └── config/
│       └── Ai_Blogger.yaml       # 主配置
│
├── Data/                         # 运行时数据
├── driver/                       # 浏览器状态
├── Log_File/                     # 日志
├── Md/                           # 产出物
├── .env.example
└── .gitignore
```

---

## Roadmap（下一阶段）

- [ ] 拓展平台（小红书、B站、公众号）
- [ ] RAG 私有知识库，提升内容专业度
- [ ] Web Dashboard，可视化管理

---

## 许可证 & 免责声明

> ⚠️ 本工具仅供学习 AI Agent 与浏览器自动化技术，请勿用于恶意刷量或违反平台规则的行为。使用者需自行承担风险，遵守各平台服务条款与 robots 协议。

---

<p align="center">
  Built with ❤️ using Python · Playwright · DeepSeek
</p>
