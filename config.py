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

# --- 1. 三元组提取模型配置 (用于实体关系抽取) ---
EXTRACTION_API_KEY = os.getenv("EXTRACTION_API_KEY", "sk-VGr1R5YhrRdApUezU81xzmGnXJW1C6k2wbOrLvXuKgBaBON9")
EXTRACTION_BASE_URL = os.getenv("EXTRACTION_BASE_URL", "https://zhouliuai.online/v1")
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "gpt-5.2-chat-latest")

# --- 2. AI问答模型配置列表 (用户可在前端选择) ---
QA_MODELS = [



    # 最强梯队
    {
        "name": "Gemini-3-pro",
        "description": "谷歌Gemini 3 Pro高性能版，顶级推理能力，适合复杂问题深度分析，当今最强模型",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-3kiSiKDoyFxOkVxqzNGj0kosqaxUjmK0ckFBEz9OSl0XWNnO"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.qidianai.xyz/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "gemini-3-pro-high")
    },
    {
        "name": "Gemini-3-flash-preview-thinking",
        "description": "谷歌Gemini 3 Flash思考增强版，顶级推理能力，适合复杂问题深度分析，当今最强模型梯队",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "gemini-3-flash-preview-thinking")
    },
    {
        "name": "Claude-opus-4.5",
        "description": "Anthropic Claude Opus 4.5模型，擅长极度复杂推理和长文本处理，当今最强模型梯队",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-sV8Gkji5NKNb0h9mIsmFrlmoSvD2YAkAjee84j6ichQBmhct"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://yansd666.com/pg"),
        "model": os.getenv("QA_MODEL_4_MODEL", "claude-opus-4-5-20251101"),
        "use_yansd_api": True,
        "session_cookie": os.getenv("YANSD_SESSION", "session=MTc2NzI2ODI5NXxEWDhFQVFMX2dBQUJFQUVRQUFEXzFmLUFBQVlHYzNSeWFXNW5EQVFBQW1sa0EybHVkQVFGQVAwRmQxd0djM1J5YVc1bkRBb0FDSFZ6WlhKdVlXMWxCbk4wY21sdVp3d0lBQVozWldrd01ETUdjM1J5YVc1bkRBWUFCSEp2YkdVRGFXNTBCQUlBQWdaemRISnBibWNNQ0FBR2MzUmhkSFZ6QTJsdWRBUUNBQUlHYzNSeWFXNW5EQWNBQldkeWIzVndCbk4wY21sdVp3d0pBQWRrWldaaGRXeDBCbk4wY21sdVp3d1BBQTF6WlhOemFXOXVYM1J2YTJWdUJuTjBjbWx1Wnd3aUFDQTVaRFpqTTJSbVpHRmhNREkwT1dReU9HTTVPRFZoTWpaaE5EQTBNRFJtT1E9PXwRsA1H_WiJkEJI41A2-g4oXa9kUcXDqnQEcdlmg5cjQA=="),
        "new_api_user": os.getenv("YANSD_USER", "179118")
    },
  
        {
            "name": "Chatgpt-5.2",
            "description": "OpenAI GPT-5.2模型，最新一代大模型，具备卓越的语言理解和生成能力,当今最强模型梯队",
            "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-3kiSiKDoyFxOkVxqzNGj0kosqaxUjmK0ckFBEz9OSl0XWNnO"),
            "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://qidianai.xyz/v1"),
            "model": os.getenv("QA_MODEL_4_MODEL", "gpt-5.2")
        },
        {
            "name": "Chatgpt-5.2-codex",
            "description": "OpenAI GPT-5.2-Codex模型，专为代码生成和理解优化，顶级编程能力，当今最强代码模型",
            "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-3kiSiKDoyFxOkVxqzNGj0kosqaxUjmK0ckFBEz9OSl0XWNnO"),
            "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://qidianai.xyz/v1"),
            "model": os.getenv("QA_MODEL_4_MODEL", "gpt-5.2-codex"),
            # qidian API 特殊配置
            "use_qidian_api": True,
            "satoken": os.getenv("QIDIAN_SATOKEN", "8d200f5a-6861-4d1a-9578-d8658bf0132f"),
            "model_id": 32,  # qidian API 的 modelId
            "session_id": os.getenv("QIDIAN_SESSION_ID", "f21d3a83-6b7f-4dad-b7f4-1ee749e6d81a")  # 固定的 sessionId
        },
    {
            "name": "Grok-4.1-thinking",
            "description": "XAi Grok 4.1思考增强版，顶级推理能力，适合复杂问题深度分析，当今最强模型梯队",
            "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-3kiSiKDoyFxOkVxqzNGj0kosqaxUjmK0ckFBEz9OSl0XWNnO"),
            "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.qidianai.xyz/v1"),
            "model": os.getenv("QA_MODEL_4_MODEL", "grok-4.1-thinking")
        },
    {
        "name": "Gemini-3-flash-preview-nothinking",
        "description": "谷歌Gemini 3 Flash无思考版，快速响应，性能强大，适合大多数问答场景",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "gemini-3-flash-preview-nothinking")
    },
    {
        "name": "Claude-sonnet-4.5",
        "description": "Anthropic Claude Sonnet 4.5模型，擅长复杂推理和长文本处理，当今最强模型梯队",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "claude-sonnet-4.5")
    },


    {
        "name": "MiMo-V2-Flash",
        "description": "小米MiMo V2 Flash模型，国内顶级模型，超快响应速度，适合日常对话和快速问答",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "XiaomiMiMo/MiMo-V2-Flash")
    },
    {
        "name": "GLM-4.7",
        "description": "智谱GLM-4.7模型，强大的中文理解能力，擅长复杂推理和长文本处理",
        "api_key": os.getenv("QA_MODEL_10_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_10_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_10_MODEL", "ZhipuAI/GLM-4.7")
    },
    {
        "name": "Qwen3-235B-A22B-Thinking-2507",
        "description": "通义千问235B思考增强版，顶级推理能力，适合复杂问题深度分析",
        "api_key": os.getenv("QA_MODEL_5_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_5_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_5_MODEL", "Qwen/Qwen3-235B-A22B-Thinking-2507")
    },
    {
        "name": "Qwen3-235B-A22B",
        "description": "通义千问235B标准版，超大参数量，综合能力顶尖",
        "api_key": os.getenv("QA_MODEL_6_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_6_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_6_MODEL", "Qwen/Qwen3-235B-A22B")
    },
    {
        "name": "kimi-k2-thinking",
        "description": "月之暗面K2思考增强模型，擅长复杂推理和多轮对话",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "kimi-k2-thinking")
    },
    {
        "name": "kimi-k2-instruct-0905",
        "description": "月之暗面K2指令调优模型，擅长理解复杂指令和生成高质量文本",
        "api_key": os.getenv("QA_MODEL_4_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_4_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_4_MODEL", "kimi-k2-instruct-0905")
    },
     {
        "name": "DeepSeek-R1-0528",
        "description": "DeepSeek R1推理模型，专注于逻辑推理和代码生成",
        "api_key": os.getenv("QA_MODEL_3_API_KEY", "sk-WGOCGHbfZAjX0G2nT0rYckllyOcby1RBcwTnNwJhONUEiJfE"),
        "base_url": os.getenv("QA_MODEL_3_BASE_URL", "https://api.lhyb.dpdns.org/v1"),
        "model": os.getenv("QA_MODEL_3_MODEL", "deepseek-r1-0528")
    },
    # 次强梯队
    {
        "name": "Qwen3-30B-A3B",
        "description": "通义千问30B轻量版，平衡性能与速度",
        "api_key": os.getenv("QA_MODEL_7_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_7_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_7_MODEL", "Qwen/Qwen3-30B-A3B")
    },
    {
        "name": "Qwen3-32B",
        "description": "通义千问32B标准版，适合专业领域知识问答",
        "api_key": os.getenv("QA_MODEL_8_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_8_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_8_MODEL", "Qwen/Qwen3-32B")
    },
    {
        "name": "Qwen3-14B",
        "description": "通义千问14B，高性价比选择，适合一般任务",
        "api_key": os.getenv("QA_MODEL_9_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_9_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_9_MODEL", "Qwen/Qwen3-14B")
    },

    # 原有模型（按强弱顺延）
    {
        "name": "Qwen3-0.6B",
        "description": "通义千问0.6B轻量版，极速响应，适合简单问答",
        "api_key": os.getenv("QA_MODEL_1_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_1_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_1_MODEL", "Qwen/Qwen3-0.6B")
    },
    {
        "name": "Qwen3-4B",
        "description": "通义千问4B，小巧高效，适合资源受限环境",
        "api_key": os.getenv("QA_MODEL_2_API_KEY", "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"),
        "base_url": os.getenv("QA_MODEL_2_BASE_URL", "https://api-inference.modelscope.cn/v1"),
        "model": os.getenv("QA_MODEL_2_MODEL", "Qwen/Qwen3-4B")
    }


]

# 默认AI问答模型名称
DEFAULT_QA_MODEL = os.getenv("DEFAULT_QA_MODEL", "MiMo-V2-Flash")

# --- 3. Embedding 向量模型配置 (使用 ModelScope) ---
EMBED_API_KEY = "ms-7ae9b437-2d5d-47c9-b613-86e012766c2c"
EMBED_BASE_URL = "https://api-inference.modelscope.cn/v1"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B" # 魔搭上的模型名称

# --- 4. 保留旧的配置变量名以保持向后兼容（可选）---
LLM_API_KEY = EXTRACTION_API_KEY  # 向后兼容
LLM_BASE_URL = EXTRACTION_BASE_URL
LLM_MODEL = EXTRACTION_MODEL

# 文本分块配置
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 200))  # 每个文本块的大小
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 80))  # 文本块之间的重叠

# 向量检索配置
VECTOR_SEARCH_TOP_K = int(os.getenv("VECTOR_SEARCH_TOP_K", 5))  # 向量检索返回的top-k结果
VECTOR_SIMILARITY_THRESHOLD = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", 0.6))  # 相似度阈值（距离小于此值才使用文档）

# 图检索配置
GRAPH_SEARCH_HOPS = int(os.getenv("GRAPH_SEARCH_HOPS", 2))  # 图检索的跳数（N跳邻居）

# 文档上传配置
MAX_DOCUMENT_SIZE = int(os.getenv("MAX_DOCUMENT_SIZE", 20 * 1024 * 1024))  # 最大文档大小 20MB