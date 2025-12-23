"""
配置文件
从环境变量读取配置，提供默认值
"""

import os
from dotenv import load_dotenv

load_dotenv()
# Neo4j配置（优先读环境变量，没有则用默认值）
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

# Redis配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# JWT配置
SECRET_KEY = os.getenv("SECRET_KEY", "MY_SUPER_SECRET_KEY_FOR_THESIS")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 短期：15分钟
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 长期：7天

# 应用配置
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:8080"]

# 邮件配置
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "2997657261@qq.com")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "mlajppzvoexhdddf")
MAIL_FROM = os.getenv("MAIL_FROM", "2997657261@qq.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 465))
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.qq.com")
MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "False").lower() == "true"
MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "True").lower() == "true"
USE_CREDENTIALS = os.getenv("USE_CREDENTIALS", "True").lower() == "true"
VALIDATE_CERTS = os.getenv("VALIDATE_CERTS", "True").lower() == "true"

# 验证码配置
VERIFICATION_CODE_EXPIRE_MINUTES = 5  # 验证码5分钟过期

# 用户活动窗口配置
USER_ACTIVITY_WINDOW_HOURS = 24  # 24小时活动窗口

# ==================== Redis 配置 ====================

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)  # 如果没有密码，设置为 None

# ==================== 限流配置 ====================

# IP级别限流：每个IP的令牌桶容量和填充速率
# 容量：100个令牌
# 填充速率：100个令牌/秒（即每秒最多10个请求）
RATE_LIMIT_IP_CAPACITY = int(os.getenv("RATE_LIMIT_IP_CAPACITY", 1000))
RATE_LIMIT_IP_REFILL_RATE = float(os.getenv("RATE_LIMIT_IP_REFILL_RATE", 1000.0))

# 接口级别限流：每个接口的令牌桶容量和填充速率
# 容量：200个令牌
# 填充速率：200个令牌/秒
RATE_LIMIT_ENDPOINT_CAPACITY = int(os.getenv("RATE_LIMIT_ENDPOINT_CAPACITY", 2000))
RATE_LIMIT_ENDPOINT_REFILL_RATE = float(os.getenv("RATE_LIMIT_ENDPOINT_REFILL_RATE", 2000.0))

# 全局限流：全局令牌桶容量和填充速率
# 容量：1000个令牌
# 填充速率：1000个令牌/秒
RATE_LIMIT_GLOBAL_CAPACITY = int(os.getenv("RATE_LIMIT_GLOBAL_CAPACITY", 10000))
RATE_LIMIT_GLOBAL_REFILL_RATE = float(os.getenv("RATE_LIMIT_GLOBAL_REFILL_RATE", 10000.0))

# ==================== MongoDB 配置 ====================
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "chat_app_db"

# ==================== 知识图谱RAG配置 ====================

# --- 1. LLM 问答模型配置 (例如使用 DeepRouter 或 OpenAI) ---
LLM_API_KEY = "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"
LLM_BASE_URL = "https://api-inference.modelscope.cn/v1"
LLM_MODEL = "XiaomiMiMo/MiMo-V2-Flash"  # 或者 deepseek-chat
# 如果使用OpenAI，修改为：
# OPENAI_API_BASE = "https://api.openai.com/v1"
# LLM_MODEL = "gpt-3.5-turbo"

# --- 2. Embedding 向量模型配置 (使用 ModelScope) ---
EMBED_API_KEY = "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"
EMBED_BASE_URL = "https://api-inference.modelscope.cn/v1"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B" # 魔搭上的模型名称

# 文本分块配置
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 200))  # 每个文本块的大小
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 80))  # 文本块之间的重叠

# 向量检索配置
VECTOR_SEARCH_TOP_K = int(os.getenv("VECTOR_SEARCH_TOP_K", 5))  # 向量检索返回的top-k结果

# 图检索配置
GRAPH_SEARCH_HOPS = int(os.getenv("GRAPH_SEARCH_HOPS", 2))  # 图检索的跳数（N跳邻居）

# 文档上传配置
MAX_DOCUMENT_SIZE = int(os.getenv("MAX_DOCUMENT_SIZE", 20 * 1024 * 1024))  # 最大文档大小 20MB