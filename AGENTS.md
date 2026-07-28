# 项目协作说明

开始处理本项目之前，请先阅读根目录的 `LEARNING_PLAN.md`，并以其中记录的学习路线和当前进度为准。

# Mini RAG 项目协作规则

## 项目定位

本项目是个人学习为主、可供朋友小范围使用的企业知识库与行政 Agent 后端，使用 FastAPI、SQLModel、SQLite、LangChain、LangGraph、本地 BGE、Milvus 和 DeepSeek。Swagger 是当前唯一操作界面，不以公开多用户网站为部署目标。

现有可验收能力包括 RAG 后端、Alembic 迁移基线、员工与请假领域层，以及尚未接入正式 Graph 的制度、余额和申请只读工具。企业行政 Agent Graph、人工确认、API 和完整登录认证仍在实施中，在相应步骤通过测试前不得写成现有能力。当前不包含前端、OCR、表格专用解析、混合检索、Rerank、多 Agent、Redis 任务队列和生产级分布式部署。

## 企业行政 Agent 计划

目标是完成可通过 Swagger 演示、可写入简历的单 Agent 业务闭环，而不是追求 Tool 或 Agent 数量。

已确认工具：

```text
search_company_policy      查询当前会话绑定知识库中的公司制度
query_my_leave_balance     查询当前用户自己的假期余额
list_my_leave_requests     列出当前用户自己的请假申请
get_my_leave_request       查看当前用户自己的申请详情
create_leave_request       经人工确认后幂等创建请假申请
```

目标链路：

```text
用户消息 → DeepSeek 判断意图或追问缺失参数
→ 只读工具直接执行 / 写工具生成草稿
→ create_leave_request 使用 LangGraph interrupt 暂停
→ 用户批准或拒绝 → 恢复 Graph
→ 批准后幂等写入 SQLite → 返回结果、引用和调用记录
```

十个实施步骤：

1. 文档与架构基线。
2. Alembic 迁移基线并保留现有数据。
3. 员工、余额、请假申请模型和领域规则。
4. 制度、余额和申请查询等只读工具。
5. Agent State、Prompt、Graph 与 SQLite Checkpointer。
6. 请假草稿、人工确认、恢复和幂等写入。
7. 独立 Agent API、会话权限和历史查询。
8. 错误分类、重试、权限和脱敏工具日志。
9. 单元、Graph、API、迁移测试和真实模型评测。
10. README、架构图、演示脚本和验收报告。

详细需求、数据与接口分别以 `docs/requirements.md`、`database-design.md` 和 `api-design.md` 为准；实时进度以 `LEARNING_PLAN.md` 为准。现有 Agent 原型和中断半成品不算完成证据。

## 文档驱动顺序

```text
需求澄清 → requirements → architecture → database/api design
→ implementation plan → 单个可验证任务 → 测试 → acceptance report/README
```

- 需求、文档和代码冲突时，不自行猜测；列出冲突并向用户确认。
- 无法从代码或已确认需求证明的内容标记为 `[TODO]`。
- 需要用户决定的产品意图标记为 `[ASK USER]`。
- 功能需求使用稳定编号 `FR-xxx`，实现计划和验收报告引用该编号。

## 当前分层

```text
Router → Application Service → Agent / Domain Service
→ SQLModel、文件系统、Milvus、DeepSeek
```

- `app/routers/`：HTTP 输入输出、状态码和依赖注入。
- `app/dependencies/`：Session、当前用户和资源所有权。
- `app/services/`：应用流程、领域规则、事务、解析、切分、Embedding、检索和外部客户端。
- `app/agents/`：LangGraph 状态、Prompt、工具、编排、暂停恢复和调用观测；不得直接保存数据库 Session。
- `app/models/`：SQLite 模型；`app/schemas/`：HTTP 契约。
- `app/core/`：配置、日志和异常。

当前没有 Repository 层。未经架构确认，不要只为模仿 Spring Boot 增加空转层。

## 数据与安全规则

- SQLite 保存业务实体和状态；Milvus 保存 Chunk、引用元数据和向量；文件系统保存原文件。
- LangGraph Checkpoint 使用独立 SQLite 文件，只保存可序列化的执行状态、消息和中断，不代替业务表。
- `document_id` 必须贯穿 SQLite、文件路径和 Milvus。
- 受保护接口必须先验证真实存在的 `X-User-ID` 和资源归属。
- Milvus 检索必须包含 `user_id + kb_id`；文档删除必须再包含 `document_id`。
- 不接受客户端覆盖资源的 `owner_id` 或 `user_id`。
- Agent 工具的 `user_id`、`kb_id` 和员工身份必须由已验证上下文注入，不能由模型生成。
- 创建请假等写操作必须先暂停并取得当前用户明确确认；恢复后的写入必须幂等。
- Agent Graph State 只能保存可序列化数据，不得保存数据库 Session、Engine、模型客户端或向量库客户端。
- Tool 保持薄层；工作日计算、余额校验、重复申请和事务由领域 Service 负责。
- 只对超时和连接失败重试；参数、权限、余额不足、拒答和用户拒绝不重试。
- 工具日志只保存脱敏摘要，不保存完整制度正文、Token、密码或模型隐藏推理。
- 未知异常只在服务端日志记录细节，不把 `str(exc)` 返回客户端。
- 登录功能实施后只能保存密码哈希，不得保存、记录或返回明文密码。
- JWT 实施后，受保护接口必须从已验证 Token 获取用户身份，不再信任客户端直接提交的 `X-User-ID`。
- Access Token 和 Refresh Token 必须使用不同用途声明和有效期，刷新接口不得接受 Access Token 代替 Refresh Token。
- SQLite 只保存 Refresh Token 的单向哈希和会话状态，不得保存 Token 明文；退出登录必须撤销对应会话。
- 为保持学习项目简单，Refresh Token 在有效且未撤销期间可以重复使用；刷新时只签发新的 Access Token，不轮换 Refresh Token。
- 不读取、打印或提交 `.env`、密钥、数据库、上传文件和运行日志。

## 编码与注释

- 遵循 `pyguide_zh-CN.md` 中适用于本项目的规则。
- 模块、公开类和公开函数写职责明确的文档字符串。
- 关键代码段注释“为什么”，不做逐行翻译式注释。
- API Schema、数据库 Model、内部 dataclass 分开定义。
- 已知业务错误使用 `AppError`；数据库提交失败后先 `rollback()`。
- 不修改无关文件，不覆盖用户已有未提交改动。

## 命令

当前验证环境为 Python 3.11：

```powershell
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python run.py
python -m pytest -q
python -m compileall -q app tests
```

本机也可使用 `C:\D\venvs\mrh\Scripts\python.exe`。项目目前没有 Ruff、Black、Mypy 或覆盖率阈值配置；未实际运行时不得声称这些检查通过。

`python run.py` 启动时也会执行 Alembic upgrade。基线迁移只检查旧表结构，不读取或打印业务数据；发现字段不兼容时必须停止，不得直接 `stamp` 掩盖冲突。

## 完成标准

- 改动对应明确需求编号和可验证结果。
- 新行为覆盖正常、边界、异常和越权测试。
- 运行相关测试、完整测试和 `compileall`。
- API、SQLite、Milvus、README 与 `docs/` 保持一致。
- 明确列出未实现、部分实现和当前环境无法验证的内容。
- 提交前排除 `.env`、`data/`、`logs/`、IDE 临时文件和真实密钥。
