## 教学方式

- 学习者的目标岗位是 AI 应用开发工程师和 Agent 开发工程师。
- 讲解时结合本项目中的真实代码，不只讲抽象概念。
- 按步骤教学，一次只发送当前步骤；学习者回复 `ok` 后再进入下一步。
- 企业行政 Agent 的 10 步架构调整阶段已获用户明确授权自动连续推进：每步仍须独立验证和更新进度，但通过后不等待 `ok`；遇到需求冲突、真实数据风险或必须由用户决定的问题时暂停。
- 每一步标题都使用 `（当前步骤/总步骤数）` 标记进度。
- 创建方法和类时，每个字段都需要说明作用，给出代码时添加适量注释，重点说明设计原因、数据流转和容易出错的地方，不必逐行注释。
- 每个实践步骤结束时，说明需要修改哪些文件、如何验证，以及预期结果。
- 遇到错误时先根据报错和代码核实原因，不假定学习者或助手的判断一定正确。
- 如果需求、环境或代码状态存在矛盾或缺失，逐项询问或检查后再继续。

## 进度维护

- 完成一个步骤或一周的学习后，更新 `LEARNING_PLAN.md` 中的“当前进度”和对应检查项。
- 不要因为开始了某一步就将其标记为完成；必须在代码运行并通过该步验证后更新。
- 修改范围默认限定在当前项目，不修改原始参考项目 `py-doc-qa-deepseek-server`。

# AI 应用开发与 Agent 开发学习计划

## 学习目标

通过 12 周学习，掌握 Python、FastAPI、RAG、LangChain、LangGraph、Tool Calling 和基础工程化，最终完成一个可以写入简历并进行演示的企业知识库与业务 Agent 项目。

总体实践方法：

```text
跑通开源项目
→ 理解核心流程
→ 修改现有项目
→ 独立仿写
→ 加入业务 Agent
→ 工程化、部署和求职整理
```

## 当前进度

- 第 1–7 周：已完成
- 第 8 周：进行中
- 当前步骤：企业行政 Agent 架构调整第 5/10 步，重构 Agent State、Prompt、Graph 与 SQLite Checkpointer
- 第 9–12 周：未开始

> 进度只能在完成代码实践和验证后更新。

## 第一阶段：基础准备（第 1–2 周）

### 第 1 周：Python 与项目环境

学习内容：

- Python 常用语法、函数、类和异常处理
- 文件读写与 JSON
- `pip`、Conda 虚拟环境
- 环境变量和 `.env`
- Git 与 GitHub 基础操作

验收目标：能看懂普通 Python 项目，并独立创建环境、安装依赖和启动项目。

### 第 2 周：FastAPI 与 LLM API

学习内容：

- FastAPI 路由
- 请求参数和响应模型
- Pydantic 参数校验
- 异常处理
- 调用云端 DeepSeek API
- 普通响应与流式响应
- Swagger 接口测试

验收目标：独立完成一个调用 DeepSeek 的聊天接口。

## 第二阶段：小型 RAG 项目（第 3–5 周）

### 第 3 周：RAG 基础流程

学习内容：

- `Document` 对象和文档加载器
- 文本切分与 Chunk
- Embedding 和语义相似度
- Chroma 向量数据库
- Retriever 检索器
- Prompt 与上下文拼接

需要掌握的数据流：

```text
上传文档 → 解析文档 → 切分文本 → Embedding
→ 写入向量库 → 检索相关文本 → 交给大模型回答
```

### 第 4 周：精读 GitHub RAG 项目

参考项目：`YuiGod/py-doc-qa-deepseek-server`

重点理解：

- 项目目录结构
- 文档上传和数据库记录
- 文档加载与切分
- BGE Embedding 模型
- Chroma 持久化
- DeepSeek 问答
- 会话和聊天记录

### 第 5 周：改造 RAG 项目

已完成的主要改造：

- [x] Ollama 改为云端 DeepSeek
- [x] Embedding 模型改为本地加载
- [x] 配置集中到 `.env`
- [x] 路径改为项目相对路径
- [x] 文档和向量库整理到 `data/`
- [x] 全量向量化改为增量同步
- [x] 增加文档来源元数据和回答引用
- [x] 改善聊天记录保存和参数校验
- [x] 增加测试并更新 README

## 第三阶段：企业级 RAG 与 mini RAG（第 6–7 周）

### 第 6 周：分析企业级 RAG 项目

可选择 Dify、MaxKB、RAGFlow、FastGPT 或 QAnything。无需通读全部源码，重点分析：

- 文档上传、解析和 Chunk 策略
- Embedding、混合检索和 Rerank
- 引用溯源和知识库管理
- 用户权限、多租户和对话历史
- 任务队列与异步处理

### 第 7 周：完善自己的 mini RAG

目标功能：

- 文档上传、删除和列表
- 增量向量同步
- 文档删除后清理对应向量
- 相似度分数与检索阈值
- 引用文档名称和文本片段
- 会话管理、统一异常处理和日志记录
- 测试与 README

## 第四阶段：Agent（第 8–9 周）

### 第 8 周：Tool Calling 与 LangGraph

实践项目：企业行政 Agent。

最终业务工具：

```text
search_company_policy      查询当前会话的制度知识库
query_my_leave_balance     查询当前用户的假期余额
list_my_leave_requests     列出当前用户的请假申请
get_my_leave_request       查看当前用户的申请详情
create_leave_request       经人工确认后创建请假申请
```

已完成的 Tool Calling 基础练习：

- [x] 理解 Tool Calling 边界并定义第一个 `@tool`
- [x] 使用 Pydantic 校验模型生成的业务参数
- [x] 让 DeepSeek 判断是否调用工具并生成参数
- [x] 使用 LangGraph 实现基础状态、节点、边和条件路由
- [x] 练习参数错误、工具异常、失败重试和调用日志

这些练习证明了单点知识，不代表企业行政 Agent 已完成。现有 Agent 文件仍是原型或中断后的半成品。

简历级企业行政 Agent 十个步骤：

- [x] 1/10 建立需求、架构、数据库、API 与实施计划基线
- [x] 2/10 引入 Alembic，保留现有 SQLite 数据并建立迁移基线
- [x] 3/10 实现员工、余额、请假申请模型与领域规则
- [x] 4/10 实现制度、余额和申请查询等只读工具
- [ ] 5/10 重构 Agent State、Prompt、Graph 与 SQLite Checkpointer
- [ ] 6/10 实现请假草稿、人工确认、恢复和幂等写入
- [ ] 7/10 增加独立 Agent API、会话权限和历史查询
- [ ] 8/10 完善错误分类、重试、权限和脱敏工具日志
- [ ] 9/10 完成单元、Graph、API、迁移测试和真实模型评测
- [ ] 10/10 更新 README、架构图、演示脚本和验收报告

目标流程：

```text
用户输入
→ DeepSeek 判断意图或追问缺失参数
→ 制度检索 / 查询余额 / 查询申请直接执行只读工具
→ 创建请假先校验参数并生成草稿
→ LangGraph interrupt 暂停并等待用户批准或拒绝
→ 拒绝时不写业务表；批准时幂等写入 SQLite
→ 记录脱敏工具日志
→ 返回最终回答、制度引用或申请结果
```

验收目标：能够解释模型、LangGraph、Tool、领域 Service、业务 SQLite、Checkpoint SQLite 和 Milvus 的职责边界，并让五个业务工具在单 Agent 状态图中可靠运行。最终必须通过 Swagger 演示制度问答、余额查询、多轮补参、申请草稿、拒绝零写入、批准单次写入、申请查询和脱敏调用日志。

### 第 9 周：完成可演示业务 Agent

功能目标：

- RAG 查询公司制度
- 查询员工假期余额
- 创建请假申请
- 多轮对话状态
- 工具调用权限控制
- 调用日志与异常重试
- 高风险操作执行前人工确认
- 真实模型评测与失败分析

重点是实现一个可控、可观察、有明确业务流程的 Agent，而不是追求多 Agent 数量。

## 第五阶段：工程化（第 10 周）

### 第 10 周：系统整合与部署

建议职责划分：

```text
Spring Boot：用户、认证、权限、会话、操作日志
FastAPI：RAG、Embedding、向量检索、DeepSeek、LangGraph Agent
```

学习内容：

- Dockerfile 和 Docker Compose
- 配置分环境管理与 API Key 安全
- 数据持久化
- 健康检查
- 日志和异常追踪
- Java 与 Python 服务联调

验收目标：一条命令启动完整项目，并能说明每个服务的职责和调用链。

## 第六阶段：求职准备（第 11–12 周）

### 第 11 周：整理项目

需要完成：

- 项目 README
- 系统架构图、RAG 数据流程图和 Agent 状态图
- API 文档和 Docker 启动说明
- 演示数据、截图或演示视频
- GitHub 提交记录整理

最终演示链路：

```text
上传制度文档 → 建立向量索引 → 提问并返回引用
→ Agent 查询业务数据 → Agent 创建业务申请 → 查看调用日志
```

### 第 12 周：简历与面试

重点准备：

- Python、FastAPI、LangChain 和 LangGraph
- RAG 流程、Chunk、Embedding 和向量数据库
- Top-K、相似度阈值与 Rerank
- Prompt 与上下文管理
- Tool Calling 与 Agent 状态管理
- 异常重试、权限控制和防止工具误调用
- 项目遇到的问题、判断过程和解决方案

简历描述参考：

> 基于 FastAPI、LangChain、LangGraph、Chroma 和 DeepSeek 实现企业知识库与业务 Agent，支持文档增量向量化、语义检索、引用溯源、会话管理、工具调用、参数校验、异常重试及调用链日志。

## 跨对话继续学习

在新的对话中，可以直接说明：

```text
请先阅读项目根目录的 AGENTS.md 和 LEARNING_PLAN.md，
根据其中的当前进度继续带我学习。一次只进行一个步骤，
我回复 ok 后再进入下一步。
```
