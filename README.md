# WeChat Auto-Reply Bot

基于 WeChatHook + WeClone 实现的微信自动回复机器人，能够学习你的聊天风格并自动回复消息。

## ✨ 功能特性

- 🤖 **自动回复** - 基于 AI 的智能回复
- 🎭 **风格模仿** - 学习并模拟你的聊天风格
- 📚 **持续学习** - 边使用边收集数据，不断优化
- 🔒 **本地部署** - 数据存储在本地，保护隐私

## 🚀 快速开始

### 环境要求

- Windows 10/11 (64 位)
- Python 3.10+
- 微信 3.9.5.81 ~ 4.1.1 (支持最新版本)

### 安装步骤

1. **克隆项目**
   ```bash
   cd D:/Desktop/weChatBot
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   # 复制环境变量模板
   cp .env.example .env
   ```
   
   编辑 `.env` 文件，填入你的配置：
   ```
   LLM_PROVIDER=openai
   LLM_API_KEY=your_api_key
   ```

4. **运行机器人**
   ```bash
   python main.py
   ```

## 📖 使用说明

### 第一步：启动机器人

```bash
python main.py
```

### 第二步：收集聊天数据

机器人会自动收集你的聊天数据。正常聊天即可，无需额外操作。

### 第三步：训练模型 (可选)

当收集足够的数据后（建议至少 100 条对话），可以训练模型：

```bash
python training/train_style.py
```

### 第四步：启用自动回复

修改配置文件启用自动回复模式。

## 📁 项目结构

```
D:/Desktop/weChatBot/
├── core/
│   ├── wechat_bot.py         # WeChatHook 封装
│   ├── message_collector.py  # 消息收集器
│   └── llm_engine.py         # LLM 推理引擎
├── training/
│   ├── data_processor.py     # 数据处理
│   └── train_style.py        # 风格微调脚本
├── config/
│   └── config.yaml           # 配置文件
├── data/                     # 数据目录 (不提交到 Git)
├── tests/                    # 测试文件
├── main.py                   # 程序入口
└── requirements.txt          # 依赖列表
```

## ⚠️ 注意事项

1. **封号风险**：请控制消息发送频率，避免被微信判定为机器人
2. **微信版本**：支持微信 3.9.5.81 ~ 4.1.1，建议使用最新版
3. **数据隐私**：聊天记录存储在本地，请勿上传到公开仓库

## 🛠️ 开发

### 代码规范

- 遵循 PEP 8 规范
- 提交前运行测试：`pytest tests/ -v`
- 遵循 Conventional Commits 提交规范

### 提交示例

```bash
git commit -m "feat(core): 实现消息自动回复功能"
git commit -m "fix(training): 修复数据处理 bug"
```

## 📝 License

MIT License

## 🙏 感谢

- [WeChatHook](https://github.com/lyx102/WeChatHook) - 微信 Hook 框架 (支持最新版)
- [WeClone](https://github.com/xming521/WeClone) - 聊天风格模仿
