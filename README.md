# MemOS 本地实现 - 项目交换区

这是何老师（AI 助手）与开哥（用户）协作开发 MemOS 本地实现的项目交换区。

## 🎯 项目目标

学习 MemOS 的设计理念，实现本地化的记忆管理系统，作为云端 MemOS 的备份和补充。

## 📋 项目阶段

### 阶段 1：记忆检索引擎 ✅ 已完成
- [x] 关键词搜索
- [x] 相关性评分
- [x] 日期/类型过滤
- [x] 标签搜索
- [x] JSON 输出

### 阶段 2：OpenClaw 插件 ⏸️ 暂停
- [ ] 对话前自动注入记忆
- [ ] 对话后自动保存
- [ ] 集成检索引擎

### 阶段 3：记忆提取优化 ⏸️ 暂停
- [ ] AI 提取关键信息
- [ ] 自动分类和标签
- [ ] 记忆去重

## 📁 目录结构

```
memos-exchange/
├── README.md              # 项目说明
├── docs/                  # 设计文档
│   ├── memos-architecture.md    # MemOS 架构分析
│   ├── local-design.md          # 本地设计方案
│   └── api-reference.md         # API 参考
├── src/                   # 源代码
│   ├── search-engine/     # 检索引擎
│   └── plugin/            # OpenClaw 插件
├── test/                  # 测试文件
└── logs/                  # 开发日志
```

## 🔧 技术栈

- **Python 3.7+**: 检索引擎
- **Node.js**: OpenClaw 插件
- **SQLite** (可选): 记忆索引
- **Flask** (可选): Web 界面

## 👥 协作方式

### 何老师（AI 助手）负责
- 架构设计
- 核心逻辑实现
- 系统集成
- 测试验证

### Claude Code（协作 AI）负责
- 样板代码生成
- 单元测试编写
- 文档编写
- 代码审查

### 开哥（用户）负责
- 需求确认
- 代码审查
- 最终决策

## 📝 开发日志

### 2026-03-26
- ✅ 完成 MemOS 架构分析
- ✅ 完成检索引擎开发（阶段 1）
- ⏸️ 插件开发暂停（等待进一步指示）

## 🚀 快速开始

### 使用检索引擎

```bash
# 搜索记忆
python3 src/search-engine/search.py search "关键词" --limit 6

# JSON 输出
python3 src/search-engine/search.py search "Python" --json

# 查看统计
python3 src/search-engine/search.py stats
```

## 📚 参考资料

- [MemOS 官方文档](https://memos-docs.openmem.net/)
- [MemOS GitHub](https://github.com/MemTensor/MemOS)
- [MemOS 论文](https://arxiv.org/abs/2507.03724)

## 📄 License

MIT License

---

*最后更新：2026-03-26*
