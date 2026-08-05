FROM python:3.11-slim

# 固定容器内工作目录，让项目相对路径始终从 /app 解析。
WORKDIR /app

# 先安装依赖，业务代码变化时可以复用这一层的构建缓存。
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# 使用白名单复制运行文件，避免把 .env、数据库、日志和 IDE 文件打入镜像。
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Checkpoint SQLite、上传文件和日志通过 Compose 挂载持久化目录；
# PostgreSQL 数据由独立数据库容器持久化。
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# 容器必须监听所有网络接口，宿主机端口映射才能访问 FastAPI。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
