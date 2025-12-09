"""
异步数据库操作模块
提供事务化、重试机制和异步处理的数据库操作
"""

import os
import time
import logging
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


# ==================== 日志配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 数据库初始化 ====================

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("✅ Neo4j 数据库连接成功 (异步模块)")
except Exception as e:
    logger.error(f"❌ Neo4j 连接失败: {e}")
    driver = None


# ==================== 配置常量 ====================

# 最大重试次数
MAX_RETRIES = 3

# 重试等待时间基数（秒）
RETRY_BASE_WAIT_TIME = 2


# ==================== 数据库操作函数 ====================

def update_user_activity_transactional(username: str, max_retries: int = MAX_RETRIES) -> bool:
    """更新用户活动时间和请求计数（带事务和重试机制）
    
    使用事务确保数据一致性，失败时自动重试
    
    Args:
        username: 用户名
        max_retries: 最大重试次数，默认为3
        
    Returns:
        bool: 操作是否成功
    """
    if not driver:
        logger.error("❌ 数据库驱动未初始化")
        return False
    
    for attempt in range(max_retries):
        try:
            with driver.session() as session:
                with session.begin_transaction() as tx:
                    # 更新最后活动时间
                    tx.run(
                        """
                        MATCH (u:User {username: $username})
                        SET u.last_activity = timestamp()
                        """,
                        username=username
                    )
                    
                    # 增加请求计数
                    tx.run(
                        """
                        MATCH (u:User {username: $username})
                        SET u.request_count = COALESCE(u.request_count, 0) + 1
                        """,
                        username=username
                    )
                    
                    # 事务自动提交
                    
                logger.info(f"✅ 用户活动更新成功: {username} (尝试 {attempt + 1}/{max_retries})")
                return True
                
        except Exception as e:
            logger.error(f"❌ 事务执行失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            
            # 如果是最后一次重试，记录最终失败
            if attempt == max_retries - 1:
                logger.error(f"❌ 更新用户活动最终失败: {username}")
                return False
            
            # 指数退避策略：等待时间随重试次数增加
            wait_time = RETRY_BASE_WAIT_TIME ** attempt
            logger.warning(f"⚠️ {wait_time}秒后重试...")
            time.sleep(wait_time)
    
    return False


def close_driver():
    """关闭数据库连接"""
    if driver:
        driver.close()
        logger.info("🛑 数据库驱动已关闭")


# ==================== 异步数据库管理器 ====================

class AsyncDatabaseManager:
    """异步数据库管理器
    
    使用线程池异步处理数据库操作，避免阻塞主线程
    适用于需要高并发处理数据库更新的场景
    """
    
    def __init__(self, max_workers: int = 5):
        """初始化异步数据库管理器
        
        Args:
            max_workers: 线程池最大工作线程数，建议设置为CPU核心数的2-3倍
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._loop = None
        self._active_tasks = 0
        logger.info(f"🔄 异步数据库管理器初始化完成，最大工作线程: {max_workers}")
    
    @property
    def loop(self):
        """获取事件循环（懒加载）
        
        Returns:
            asyncio.AbstractEventLoop: 当前事件循环
        """
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果没有事件循环，创建新的
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    async def submit_async_update(self, username: str) -> bool:
        """异步提交数据库更新任务
        
        在线程池中执行数据库操作，不阻塞主线程
        
        Args:
            username: 用户名
            
        Returns:
            bool: 更新是否成功
        """
        self._active_tasks += 1
        
        try:
            # 在线程池中执行数据库操作
            result = await self.loop.run_in_executor(
                self.executor,
                partial(update_user_activity_transactional, username)
            )
            
            if result:
                logger.debug(f"📊 异步更新成功: {username}")
            else:
                logger.error(f"📊 异步更新失败: {username}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 异步更新异常: {username}, 错误: {e}")
            return False
            
        finally:
            self._active_tasks -= 1
    
    def get_stats(self) -> dict:
        """获取管理器统计信息

        Returns:
            dict: 包含工作线程数、活动任务数等统计信息
        """
        pending_tasks = 0
        if hasattr(self.executor, '_work_queue'):
            pending_tasks = self.executor._work_queue.qsize()

        return {
            "max_workers": self.max_workers,
            "active_tasks": self._active_tasks,
            "executor_stats": {
                "threads": self.executor._max_workers,
                "pending": pending_tasks
            }
        }

    async def submit_avatar_save(
        self,
        username: str,
        filename: str,
        content: bytes,
        avatar_dir: str,
        old_avatar: str = None
    ) -> bool:
        """异步提交头像保存任务

        在线程池中执行文件保存和数据库更新，不阻塞主线程

        Args:
            username: 用户名
            filename: 新头像文件名
            content: 文件内容
            avatar_dir: 头像存储目录
            old_avatar: 旧头像文件名（可选）

        Returns:
            bool: 保存是否成功
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(save_avatar_sync, username, filename, content, avatar_dir, old_avatar)
            )

            if result:
                logger.debug(f"📊 异步头像保存成功: {username}")
            else:
                logger.error(f"📊 异步头像保存失败: {username}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步头像保存异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def submit_profile_update(self, username: str, profile_data: dict) -> tuple:
        """异步提交用户资料更新任务

        在线程池中执行数据库操作，不阻塞主线程

        Args:
            username: 当前用户名
            profile_data: 资料数据字典

        Returns:
            tuple: (成功标志, 错误信息或新用户名)
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(update_user_profile_sync, username, profile_data)
            )

            if result[0]:
                logger.debug(f"📊 异步资料更新成功: {username}")
            else:
                logger.error(f"📊 异步资料更新失败: {username}, 原因: {result[1]}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步资料更新异常: {username}, 错误: {e}")
            return False, str(e)

        finally:
            self._active_tasks -= 1

    async def submit_2fa_image_save(self, username: str, filename: str, content: bytes, twofa_dir: str) -> bool:
        """异步提交2FA图片保存任务

        Args:
            username: 用户名
            filename: 2FA图片文件名
            content: 文件内容
            twofa_dir: 2FA图片存储目录

        Returns:
            bool: 保存是否成功
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(save_2fa_image_sync, username, filename, content, twofa_dir)
            )

            if result:
                logger.debug(f"📊 异步2FA图片保存成功: {username}")
            else:
                logger.error(f"📊 异步2FA图片保存失败: {username}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步2FA图片保存异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def submit_2fa_disable(self, username: str, twofa_dir: str) -> bool:
        """异步提交禁用2FA任务

        Args:
            username: 用户名
            twofa_dir: 2FA图片存储目录

        Returns:
            bool: 禁用是否成功
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(disable_2fa_sync, username, twofa_dir)
            )

            if result:
                logger.debug(f"📊 异步禁用2FA成功: {username}")
            else:
                logger.error(f"📊 异步禁用2FA失败: {username}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步禁用2FA异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def submit_2fa_verify(self, username: str, content: bytes, twofa_dir: str) -> bool:
        """异步提交2FA图片验证任务

        Args:
            username: 用户名
            content: 上传的图片内容
            twofa_dir: 2FA图片存储目录

        Returns:
            bool: 验证是否成功
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(verify_2fa_image_sync, username, content, twofa_dir)
            )

            return result

        except Exception as e:
            logger.error(f"❌ 异步2FA验证异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def submit_password_update(self, username: str, new_password_hash: str, password_strength: int = 2) -> bool:
        """异步提交密码更新任务

        Args:
            username: 用户名
            new_password_hash: 新密码哈希
            password_strength: 密码强度等级 (1-4)

        Returns:
            bool: 更新是否成功
        """
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(update_password_sync, username, new_password_hash, password_strength)
            )

            if result:
                logger.debug(f"📊 异步密码更新成功: {username}")
            else:
                logger.error(f"📊 异步密码更新失败: {username}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步密码更新异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def submit_login_record(
        self,
        username: str,
        ip: str,
        location: str,
        user_agent: str,
        login_time: int
    ) -> bool:
        """异步提交登录历史写入任务，使用线程池避免阻塞请求线程"""
        self._active_tasks += 1

        try:
            result = await self.loop.run_in_executor(
                self.executor,
                partial(create_login_record_sync, username, ip, location, user_agent, login_time)
            )

            if result:
                logger.debug(f"📊 异步登录记录写入成功: {username} @ {ip}")
            else:
                logger.error(f"📊 异步登录记录写入失败: {username}")

            return result

        except Exception as e:
            logger.error(f"❌ 异步登录记录异常: {username}, 错误: {e}")
            return False

        finally:
            self._active_tasks -= 1

    async def warmup_qr_login_cache(self):
        """预热二维码登录状态缓存
        
        在应用启动时，将所有用户的二维码登录状态写入Redis缓存
        使用Redis Pipeline批量写入，提高性能
        """
        try:
            # 导入必要的模块
            from database import get_all_users_qr_login_status
            from redis_utils import batch_set_qr_login_status_cache
            
            logger.info("🔥 开始预热二维码登录状态缓存...")
            
            # 在线程池中执行数据库查询
            users = await self.loop.run_in_executor(
                self.executor,
                get_all_users_qr_login_status
            )
            
            if not users:
                logger.warning("⚠️ 未找到任何用户，跳过缓存预热")
                return
            
            # 使用Redis Pipeline批量写入缓存（单次网络往返）
            success_count = await self.loop.run_in_executor(
                self.executor,
                batch_set_qr_login_status_cache,
                users
            )
            
            logger.info(f"✅ 二维码登录状态缓存预热完成，共 {success_count}/{len(users)} 个用户")
            
        except Exception as e:
            logger.error(f"❌ 预热二维码登录状态缓存失败: {e}")

    def shutdown(self, wait: bool = True):
        """关闭线程池
        
        Args:
            wait: 是否等待所有任务完成，默认为True
        """
        logger.info("🛑 正在关闭异步数据库管理器...")
        self.executor.shutdown(wait=wait)
        logger.info("🛑 异步数据库管理器已关闭")


# ==================== 向后兼容函数 ====================

def update_last_activity_and_count(username: str) -> bool:
    """向后兼容的同步更新函数

    Args:
        username: 用户名

    Returns:
        bool: 操作是否成功
    """
    return update_user_activity_transactional(username)


def update_user_profile_sync(username: str, profile_data: dict) -> tuple:
    """同步更新用户资料，返回完整用户数据"""
    if not driver:
        logger.error("❌ 数据库驱动未初始化")
        return False, "数据库连接失败"

    try:
        with driver.session() as session:
            new_username = profile_data.get("username", username)
            new_email = profile_data.get("email")

            # 如果要修改用户名，检查新用户名是否已存在
            if new_username != username:
                check_query = "MATCH (u:User {username: $new_username}) RETURN u"
                if session.run(check_query, new_username=new_username).single():
                    return False, "用户名已被占用"

            # 如果要修改邮箱，检查新邮箱是否已存在
            if new_email:
                check_email_query = """
                MATCH (u:User {email: $email})
                WHERE u.username <> $username
                RETURN u
                """
                if session.run(check_email_query, email=new_email, username=username).single():
                    return False, "邮箱已被占用"

            # 构建更新语句并返回所有需要的字段
            update_query = """
            MATCH (u:User {username: $username})
            SET u.username = $new_username,
                u.email = COALESCE($email, u.email),
                u.job_title = $job_title,
                u.website = $website,
                u.bio = $bio
            RETURN u.username as username,
                   u.email as email,
                   u.job_title as job_title,
                   u.website as website,
                   u.bio as bio,
                   u.avatar as avatar
            """

            result = session.run(
                update_query,
                username=username,
                new_username=new_username,
                email=new_email,
                job_title=profile_data.get("job_title", ""),
                website=profile_data.get("website", ""),
                bio=profile_data.get("bio", "")
            ).single()

            if result:
                updated_user = {
                    "username": result.get("username", ""),
                    "email": result.get("email", ""),
                    "job_title": result.get("job_title", ""),
                    "website": result.get("website", ""),
                    "bio": result.get("bio", ""),
                    "avatar": result.get("avatar", "")
                }
                logger.info(f"✅ 用户资料更新成功: {username} -> {updated_user['username']}")
                return True, updated_user
            return False, "用户不存在"

    except Exception as e:
        logger.error(f"❌ 更新用户资料失败: {username}, 错误: {e}")
        return False, str(e)


def save_avatar_sync(username: str, filename: str, content: bytes, avatar_dir: str, old_avatar: str = None) -> bool:
    """同步保存头像文件并更新数据库

    Args:
        username: 用户名
        filename: 新头像文件名
        content: 文件内容
        avatar_dir: 头像存储目录
        old_avatar: 旧头像文件名（可选，用于删除）

    Returns:
        bool: 操作是否成功
    """
    try:
        # 删除旧头像
        if old_avatar:
            old_file_path = os.path.join(avatar_dir, old_avatar)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
                logger.info(f"🗑️ 已删除旧头像: {old_avatar}")

        # 保存新头像
        file_path = os.path.join(avatar_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"💾 头像文件已保存: {filename}")

        # 更新数据库
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            session.run(
                """
                MATCH (u:User {username: $username})
                SET u.avatar = $avatar
                """,
                username=username,
                avatar=filename
            )
        logger.info(f"✅ 头像数据库更新成功: {username}")
        return True

    except Exception as e:
        logger.error(f"❌ 保存头像失败: {username}, 错误: {e}")
        return False


# ==================== 2FA 图片验证相关函数 ====================

def save_2fa_image_sync(username: str, filename: str, content: bytes, twofa_dir: str) -> bool:
    """同步保存2FA验证图片并更新数据库

    Args:
        username: 用户名
        filename: 2FA图片文件名
        content: 文件内容
        twofa_dir: 2FA图片存储目录

    Returns:
        bool: 操作是否成功
    """
    import hashlib

    try:
        # 确保目录存在
        os.makedirs(twofa_dir, exist_ok=True)

        # 计算图片哈希
        content_hash = hashlib.sha256(content).hexdigest()

        # 删除旧的2FA图片
        if driver:
            with driver.session() as session:
                result = session.run(
                    "MATCH (u:User {username: $username}) RETURN u.twofa_image as twofa_image",
                    username=username
                ).single()
                if result and result["twofa_image"]:
                    old_file = os.path.join(twofa_dir, result["twofa_image"])
                    if os.path.exists(old_file):
                        os.remove(old_file)
                        logger.info(f"🗑️ 已删除旧2FA图片: {result['twofa_image']}")

        # 保存新图片
        file_path = os.path.join(twofa_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"💾 2FA图片已保存: {filename}")

        # 更新数据库 - 启用2FA并保存图片名和哈希
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            session.run(
                """
                MATCH (u:User {username: $username})
                SET u.twofa_enabled = true,
                    u.twofa_image = $filename,
                    u.twofa_hash = $hash
                """,
                username=username,
                filename=filename,
                hash=content_hash
            )
        logger.info(f"✅ 2FA已启用: {username}, 哈希: {content_hash[:16]}...")
        return True

    except Exception as e:
        logger.error(f"❌ 保存2FA图片失败: {username}, 错误: {e}")
        return False


def disable_2fa_sync(username: str, twofa_dir: str) -> bool:
    """同步禁用2FA并删除验证图片

    Args:
        username: 用户名
        twofa_dir: 2FA图片存储目录

    Returns:
        bool: 操作是否成功
    """
    try:
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            # 获取并删除旧图片
            result = session.run(
                "MATCH (u:User {username: $username}) RETURN u.twofa_image as twofa_image",
                username=username
            ).single()

            if result and result["twofa_image"]:
                old_file = os.path.join(twofa_dir, result["twofa_image"])
                if os.path.exists(old_file):
                    os.remove(old_file)
                    logger.info(f"🗑️ 已删除2FA图片: {result['twofa_image']}")

            # 更新数据库 - 禁用2FA
            session.run(
                """
                MATCH (u:User {username: $username})
                SET u.twofa_enabled = false,
                    u.twofa_image = null
                """,
                username=username
            )
        logger.info(f"✅ 2FA已禁用: {username}")
        return True

    except Exception as e:
        logger.error(f"❌ 禁用2FA失败: {username}, 错误: {e}")
        return False


def verify_2fa_image_sync(username: str, content: bytes, twofa_dir: str) -> bool:
    """同步验证2FA图片是否匹配

    使用文件哈希进行比较，避免字节级别差异导致验证失败

    Args:
        username: 用户名
        content: 上传的图片内容
        twofa_dir: 2FA图片存储目录

    Returns:
        bool: 图片是否匹配
    """
    import hashlib

    try:
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            result = session.run(
                "MATCH (u:User {username: $username}) RETURN u.twofa_image as twofa_image, u.twofa_hash as twofa_hash",
                username=username
            ).single()

            if not result or not result["twofa_image"]:
                logger.error(f"❌ 用户没有设置2FA图片: {username}")
                return False

            # 计算上传图片的哈希
            uploaded_hash = hashlib.sha256(content).hexdigest()

            # 如果数据库中有存储的哈希，直接比较哈希
            if result.get("twofa_hash"):
                if uploaded_hash == result["twofa_hash"]:
                    logger.info(f"✅ 2FA验证成功 (哈希匹配): {username}")
                    return True
                else:
                    logger.warning(f"⚠️ 2FA验证失败，哈希不匹配: {username}")
                    logger.debug(f"   存储哈希: {result['twofa_hash'][:16]}...")
                    logger.debug(f"   上传哈希: {uploaded_hash[:16]}...")
                    return False

            # 兼容旧数据：如果没有哈希，则读取文件比较
            stored_file = os.path.join(twofa_dir, result["twofa_image"])
            if not os.path.exists(stored_file):
                logger.error(f"❌ 2FA图片文件不存在: {stored_file}")
                return False

            with open(stored_file, "rb") as f:
                stored_content = f.read()

            stored_hash = hashlib.sha256(stored_content).hexdigest()

            # 比较哈希值
            if uploaded_hash == stored_hash:
                logger.info(f"✅ 2FA验证成功: {username}")
                return True
            else:
                logger.warning(f"⚠️ 2FA验证失败，图片不匹配: {username}")
                logger.debug(f"   存储文件大小: {len(stored_content)}, 上传文件大小: {len(content)}")
                return False

    except Exception as e:
        logger.error(f"❌ 2FA验证异常: {username}, 错误: {e}")
        return False


def create_login_record_sync(username: str, ip: str, location: str, user_agent: str, login_time: int) -> bool:
    """同步写入登录历史记录"""
    try:
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {username: $username})
                CREATE (l:LoginHistory {
                    ip: $ip,
                    location: $location,
                    user_agent: $user_agent,
                    login_time: $login_time
                })
                CREATE (u)-[:HAS_LOGIN]->(l)
                RETURN l
                """,
                username=username,
                ip=ip,
                location=location,
                user_agent=user_agent,
                login_time=login_time
            ).single()

            if result:
                logger.info(f"✅ 登录历史记录已写入: {username} @ {ip}")
                return True
            else:
                logger.error(f"❌ 登录历史写入失败: {username}")
                return False

    except Exception as e:
        logger.error(f"❌ 写入登录历史异常: {username}, 错误: {e}")
        return False


def update_password_sync(username: str, new_password_hash: str, password_strength: int = 2) -> bool:
    """同步更新用户密码

    Args:
        username: 用户名
        new_password_hash: 新密码哈希
        password_strength: 密码强度等级 (1-4)

    Returns:
        bool: 操作是否成功
    """
    try:
        if not driver:
            logger.error("❌ 数据库驱动未初始化")
            return False

        with driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {username: $username})
                SET u.password = $password,
                    u.password_strength = $strength
                RETURN u.username as username
                """,
                username=username,
                password=new_password_hash,
                strength=password_strength
            ).single()

            if result:
                logger.info(f"✅ 密码更新成功: {username}, 强度等级: {password_strength}")
                return True
            else:
                logger.error(f"❌ 用户不存在: {username}")
                return False

    except Exception as e:
        logger.error(f"❌ 更新密码失败: {username}, 错误: {e}")
        return False