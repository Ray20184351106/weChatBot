# 推送代码到 GitHub 指南

## 第一步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名称：`wechat-auto-reply`
3. 描述：`基于 WeChatFerry + WeClone 的微信自动回复机器人`
4. 选择 **Public** (公开)
5. **不要** 勾选 "Add a README file"
6. 点击 **Create repository**

## 第二步：推送代码

仓库创建后，在终端执行以下命令：

```bash
cd D:/Desktop/weChatBot

# 添加远程仓库 (将 <your-username> 替换为你的 GitHub 用户名)
git remote add origin https://github.com/<your-username>/wechat-auto-reply.git

# 推送代码
git branch -M main
git push -u origin main
```

## 第三步：验证推送

访问你的仓库页面，刷新后应该能看到所有代码文件。

## 后续提交规范

每次修改并测试无误后，执行标准提交流程：

```bash
# 1. 查看变更
git status
git diff

# 2. 暂存变更
git add <files>

# 3. 提交 (遵循 Conventional Commits)
git commit -m "type(scope): description"

# 4. 推送
git push origin main
```

### 提交类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(core): 实现自动回复功能` |
| `fix` | Bug 修复 | `fix(training): 修复数据处理 bug` |
| `docs` | 文档更新 | `docs: 更新 README 安装说明` |
| `style` | 代码格式 | `style: 格式化代码` |
| `refactor` | 重构 | `refactor(llm): 优化引擎架构` |
| `test` | 测试相关 | `test: 添加单元测试` |
| `chore` | 构建/配置 | `chore: 更新依赖版本` |
