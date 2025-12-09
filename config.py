"""
配置文件
从环境变量读取配置，提供默认值
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 数据库配置（替换成cpolar的公网地址+端口）
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://20.tcp.vip.cpolar.cn:11740")  # 对应7687的公网地址
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")  # 保持你的本地密码

# Redis配置（替换成cpolar的公网地址+端口）
REDIS_HOST = os.getenv("REDIS_HOST", "20.tcp.vip.cpolar.cn")  # 对应6379的公网地址
REDIS_PORT = int(os.getenv("REDIS_PORT", 10023))  # 替换成cpolar显示的Redis端口
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)  # 本地Redis无密码则保持None

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
