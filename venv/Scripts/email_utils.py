from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
import random

# --- 配置区域 (请替换为你自己的) ---
conf = ConnectionConfig(
    MAIL_USERNAME = "2997657261@qq.com",
    MAIL_PASSWORD = "mlajppzvoexhdddf", # 去邮箱设置里开通 POP3/SMTP 获取
    MAIL_FROM = "2997657261@qq.com",
    MAIL_PORT = 465,
    MAIL_SERVER = "smtp.qq.com",
    MAIL_STARTTLS = False,
    MAIL_SSL_TLS = True,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# 生成 6 位验证码
def generate_code():
    return str(random.randint(100000, 999999))

# 发送邮件函数
async def send_verification_email(email: EmailStr, code: str):
    html = f"""
    <div style="padding: 20px; background-color: #f4f4f4;">
        <div style="background-color: #fff; padding: 20px; border-radius: 10px;">
            <h2>KG-RAG 系统注册验证</h2>
            <p>您的验证码是：<strong style="font-size: 24px; color: #409EFF;">{code}</strong></p>
            <p>验证码 5 分钟内有效，请勿泄露给他人。</p>
        </div>
    </div>
    """
    message = MessageSchema(
        subject="【KG-RAG毕设】注册验证码",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)

# 发送忘记密码验证码邮件函数
async def send_forgot_password_email(email: EmailStr, code: str):
    html = f"""
    <div style="padding: 20px; background-color: #f4f4f4;">
        <div style="background-color: #fff; padding: 20px; border-radius: 10px;">
            <h2>KG-RAG 系统密码重置验证</h2>
            <p>您正在重置密码，验证码是：<strong style="font-size: 24px; color: #409EFF;">{code}</strong></p>
            <p>验证码 5 分钟内有效，请勿泄露给他人。</p>
            <p style="color: #f56c6c; margin-top: 15px;">如果不是您本人操作，请忽略此邮件。</p>
        </div>
    </div>
    """
    message = MessageSchema(
        subject="【KG-RAG毕设】密码重置验证码",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)