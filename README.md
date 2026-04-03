# WeChat Auto-Reply Bot

微信自动回复机器人，基于 UI 自动化实现消息监听和发送，支持微信 4.x 最新版本。

## ✨ 功能特性

- 🤖 **UI 自动化** - 基于 pywinauto + OCR，不依赖 Hook
- 📺 **屏幕识别** - 实时 OCR 识别微信窗口消息
- 💬 **自动发送** - 模拟键盘输入发送消息
- 🎭 **风格学习** - 收集聊天记录，学习聊天风格（开发中）

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

4. **运行机器人**
   ```bash
   python main.py
   ```

   **注意**：微信窗口必须保持可见，不要最小化！

## 📊 开发进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 微信连接 | ✅ 完成 | 支持微信 4.x/3.x |
| 窗口查找 | 🔄 调试中 | 微信 4.x 窗口定位优化中 |
| OCR 识别 | ✅ 完成 | Tesseract 中文识别 |
| 消息发送 | ⏳ 待测试 | 键盘模拟/Ctrl+Enter |
| 消息收集 | ✅ 完成 | JSONL 格式存储 |
| 风格训练 | ⏳ 计划中 | LoRA 微调 |
| 自动回复 | ⏳ 计划中 | 集成 LLM |

### 当前阶段

**2026-04-03**: 已完成 UI 自动化框架搭建

- [x] pywinauto 连接微信进程
- [x] Tesseract OCR 集成（中文语言包）
- [x] 消息收集模块
- [ ] 窗口定位优化（微信 4.x）
- [ ] 完整消息监听流程测试
- [ ] 自动回复功能

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
