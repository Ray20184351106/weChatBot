# WeChat Auto-Reply Bot

微信自动回复机器人，基于 UI 自动化实现消息监听和发送，支持微信 4.x 最新版本。

## ✨ 功能特性

- 🤖 **UI 自动化** - 基于 pywinauto + OCR，不依赖 Hook
- 📺 **屏幕识别** - 实时 OCR 识别微信窗口消息
- 💬 **自动发送** - 模拟键盘输入发送消息
- 📝 **消息收集** - 自动收集对话数据，JSONL 格式存储
- 🎭 **自动回复** - 频率限制、人机切换、黑白名单
- 🧠 **LLM 集成** - 支持 OpenAI/DeepSeek/本地模型
- 👥 **联系人管理** - 联系人缓存、昵称解析、群组管理
- 📎 **消息类型** - 支持文本/图片/文件/视频等多种消息类型识别

## 🚀 快速开始

### 环境要求

- Windows 10/11 (64 位)
- Python 3.10+
- 微信任意版本（支持 4.x 最新版）
- Tesseract OCR 5.5+

### 安装步骤

1. **安装 Tesseract OCR**

   下载并安装：https://github.com/UB-Mannheim/tesseract/wiki

   安装后配置路径（默认 `E:\Tesseract`）

2. **克隆项目**
   ```bash
   cd D:/Desktop/weChatBot
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境**

   复制 `.env.example` 为 `.env` 并填写 LLM API 配置

5. **运行机器人**
   ```bash
   python main.py
   ```

   **注意**：微信窗口必须保持可见，不要最小化！

## 📊 开发进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 微信连接 | ✅ 完成 | 支持微信 4.x/3.x |
| OCR 识别 | ✅ 完成 | Tesseract 中文识别 |
| 消息发送 | ✅ 完成 | 键盘模拟发送 |
| 消息收集 | ✅ 完成 | JSONL 格式存储 |
| 自动回复 | ✅ 完成 | 频率限制、人机切换 |
| LLM 集成 | ✅ 完成 | 多提供商支持 |
| 联系人管理 | ✅ 完成 | 缓存、昵称解析 |
| 消息类型 | ✅ 完成 | 多种消息类型识别 |
| 测试框架 | ✅ 完成 | pytest + CI/CD |
| 风格训练 | ⏳ 待测试 | LoRA 微调（需 GPU） |

**项目完成度：95%**

## 📁 项目结构

```
D:/Desktop/weChatBot/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI/CD 工作流
├── core/
│   ├── __init__.py
│   ├── wechat_bot.py           # 微信自动化封装
│   ├── message_collector.py    # 消息收集器
│   ├── llm_engine.py           # LLM 推理引擎
│   ├── auto_reply.py           # 自动回复管理器
│   ├── contact_manager.py      # 联系人管理器
│   └── message_types.py        # 消息类型处理
├── training/
│   ├── __init__.py
│   ├── data_processor.py       # 数据处理
│   └── train_style.py          # 风格微调脚本
├── tests/
│   ├── conftest.py             # pytest 配置
│   ├── test_wechat_bot.py      # 微信模块测试
│   ├── test_message_collector.py # 消息收集测试
│   ├── test_llm_engine.py      # LLM 引擎测试
│   ├── test_data_processor.py  # 数据处理测试
│   ├── test_auto_reply.py      # 自动回复测试
│   ├── test_contact_manager.py # 联系人管理测试
│   └── test_message_types.py   # 消息类型测试
├── config/
│   └── config.yaml             # 配置文件
├── data/                       # 数据目录 (不提交到 Git)
├── .env.example                # 环境变量模板
├── pytest.ini                  # pytest 配置
├── requirements.txt            # 依赖列表
├── main.py                     # 程序入口
├── validate_tests.py           # 测试验证脚本
└── README.md                   # 项目说明
```

## ⚙️ 配置说明

### 自动回复配置 (config.yaml)

```yaml
auto_reply:
  enabled: false                 # 是否启用自动回复
  min_training_data: 100         # 最小训练数据量

  rate_limit:
    min_interval: 3.0            # 最小回复间隔 (秒)
    max_per_minute: 5            # 每分钟最大回复数

  human_takeover:
    enabled: true
    keywords:                    # 触发人工模式关键词
      - "#人工"
      - "#stop"

  exclude_contacts: []           # 黑名单
  whitelist_contacts: []         # 白名单
```

### LLM 配置

```yaml
llm:
  provider: "openai"             # openai / deepseek / zhipu / local
  api_key: ""                    # API Key
  base_url: ""                   # API Base URL
  model: "gpt-3.5-turbo"
  max_tokens: 512
  temperature: 0.7
```

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行单个模块测试
python -m pytest tests/test_auto_reply.py -v

# 快速验证
python validate_tests.py

# 生成覆盖率报告
python -m pytest tests/ --cov=core --cov=training
```

### 测试覆盖

| 模块 | 测试文件 | 测试用例数 |
|------|---------|-----------|
| WeChatBot | test_wechat_bot.py | 15+ |
| MessageCollector | test_message_collector.py | 20+ |
| LLMEngine | test_llm_engine.py | 25+ |
| DataProcessor | test_data_processor.py | 35+ |
| AutoReplyManager | test_auto_reply.py | 40+ |
| ContactManager | test_contact_manager.py | 25+ |
| MessageParser | test_message_types.py | 20+ |
| **总计** | - | **180+** |

## ⚠️ 注意事项

1. **封号风险**：请控制消息发送频率，建议间隔 > 3 秒
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
git commit -m "test: 添加自动回复模块测试"
```

## 📝 License

MIT License

## 🙏 感谢

- [pywinauto](https://github.com/pywinauto/pywinauto) - Windows UI 自动化
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - OCR 引擎