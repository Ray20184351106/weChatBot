# WeChat Auto Reply Bot - 开发准则

## 项目概述

基于 WeChatFerry + WeClone 实现的微信自动回复机器人，能够学习用户聊天风格并自动回复消息。

**项目位置**: `D:/Desktop/weChatBot`  
**GitHub 仓库**: [待创建]

---

## 开发规范

### 代码风格

- **语言**: Python 3.10+
- **格式化**: 遵循 PEP 8 规范
- **类型提示**: 所有公共函数必须包含类型注解
- **文档字符串**: 所有模块、类、公共函数必须包含 docstring

### 项目结构

```
D:/Desktop/weChatBot/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI/CD 工作流
├── config/
│   └── config.yaml             # 配置文件
├── core/
│   ├── __init__.py
│   ├── wechat_bot.py           # WeChatFerry 封装
│   ├── message_collector.py    # 消息收集器
│   └── llm_engine.py           # LLM 推理引擎
├── training/
│   ├── __init__.py
│   ├── data_processor.py       # 数据处理
│   └── train_style.py          # 风格微调脚本
├── data/                       # 数据目录 (不提交到 Git)
│   ├── chat_history/           # 聊天记录
│   └── models/                 # 训练模型
├── tests/                      # 测试文件
├── .gitignore
├── .env.example                # 环境变量模板
├── requirements.txt            # Python 依赖
├── main.py                     # 程序入口
├── CLAUDE.md                   # 本文件
└── README.md                   # 项目说明
```

### Git 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Type 类型**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具/配置

**示例**:
```bash
feat(core): 实现微信消息接收功能
fix(training): 修复数据预处理中的编码问题
docs: 更新 README 安装说明
refactor(llm): 优化 LLM 引擎架构
```

### 测试要求

- 所有核心功能必须包含单元测试
- 提交前确保测试通过
- 新功能必须附带测试用例

---

## 开发流程

### 本地开发

1. **环境准备**
   ```bash
   cd D:/Desktop/weChatBot
   python -m venv .venv
   source .venv/Scripts/activate  # Windows PowerShell
   pip install -r requirements.txt
   ```

2. **运行测试**
   ```bash
   pytest tests/ -v
   ```

### 提交规范

每次代码修改并测试无误后，执行标准提交流程：

```bash
# 1. 查看变更
git status
git diff

# 2. 暂存变更 (只添加相关文件)
git add <files>

# 3. 提交 (遵循 Conventional Commits)
git commit -m "type(scope): description"

# 4. 推送到 GitHub
git push origin main
```

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 微信自动化 | WeChatFerry | Hook 微信客户端 |
| LLM 框架 | PyTorch + LoRA | 风格微调 |
| 基础模型 | Qwen/GLM | 中文对话优化 |
| 数据存储 | SQLite/JSON | 本地存储 |

---

## 注意事项

### ⚠️ 封号风险

- 控制消息发送频率 (建议间隔 > 1 秒)
- 避免短时间内发送大量相同内容
- 实现人机切换机制

### ⚠️ 微信版本

- 必须使用微信 **3.9.12.51** 版本
- 不要更新微信客户端
- 版本不匹配会导致 Hook 失败

### ⚠️ 数据隐私

- 聊天记录存储于本地 `data/` 目录
- `.gitignore` 已配置排除敏感数据
- 不要将 `data/` 目录提交到 Git

---

## 快速开始

1. 安装微信 3.9.12.51
2. 复制 `.env.example` 为 `.env` 并填写配置
3. 运行 `python main.py` 启动机器人

---

*最后更新：2026-04-02*
