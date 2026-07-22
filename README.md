# mini-rag-milvus-handwrite

这是从零手写的练习项目。完整参考实现位于相邻目录
`mini-rag-milvus/`，当前阶段未完成前不要复制其中的代码。

## 当前阶段

阶段一：项目骨架与连接验证。

本阶段需要亲手完成：

- `requirements.txt`
- `requirements-dev.txt`
- `.env.example`
- `.gitignore`
- `run.py`
- `app/__init__.py`
- `app/main.py`
- `app/db.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/core/errors.py`
- `app/routers/__init__.py`
- `app/routers/health.py`
- `app/services/__init__.py`
- `app/services/model_service.py`
- `app/services/vector_service.py`

## 学习规则

1. 一次只编写一个小模块。
2. 先写代码，再对照参考项目。
3. 出错时先阅读错误信息并解释原因。
4. 阶段验收通过后再进入下一阶段。
5. 不提前编写用户、知识库、上传、检索和聊天功能。

## 阶段一验收

- Swagger 可以打开。
- SQLite 表可以创建。
- 能连接现有 Milvus 并列出 Collection。
- 本地 BGE 可以生成 512 维归一化向量。
- Milvus 或 BGE 不可用时，`GET /health` 返回明确的组件错误。
