FROM python:3.11-slim

# 配置阿里云pip源（解决国外源下载失败）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip install --upgrade pip

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装（--no-cache-dir减少镜像体积）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 启动FastAPI服务（端口和云托管配置的8000一致）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]