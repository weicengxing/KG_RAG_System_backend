from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError

# 你的密钥
SECRET_KEY = "MY_SUPER_SECRET_KEY_FOR_THESIS"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 短期：15分钟
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 长期：7天

# 显式指定 bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """创建刷新令牌，有效期为 7 天"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    """解码和验证 JWT token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return payload
    except JWTError:
        return None


def decode_token_with_exp(token: str):
    """
    解码token并区分是否过期
    返回: (payload, is_expired, error_message)
    - payload: 解码后的payload或None
    - is_expired: True表示token过期，False表示其他错误
    - error_message: 错误信息
    """
    try:
        # 先尝试完整验证（包括exp）
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload, False, None
    except jwt.ExpiredSignatureError:
        # Token已过期，但我们仍然需要payload来获取用户信息
        try:
            # 使用 options={"verify_signature": False} 来获取payload（不验证签名）
            # 但这样不安全，所以我们直接解码不验证
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            return payload, True, "Token已过期"
        except JWTError as e:
            return None, False, f"Token解码失败: {str(e)}"
    except JWTError as e:
        return None, False, f"Token无效: {str(e)}"