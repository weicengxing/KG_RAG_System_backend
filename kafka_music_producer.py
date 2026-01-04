"""
Kafka 音乐播放事件生产者
用于发送音乐播放事件到 Kafka 队列
"""

import json
import logging
import time
import uuid
from typing import Optional
from confluent_kafka import Producer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Kafka 配置
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
MUSIC_PLAY_EVENTS_TOPIC = 'music-play-events'

# 全局生产者实例
_producer = None


def get_kafka_producer() -> Optional[Producer]:
    """获取 Kafka 生产者实例（单例模式）

    Returns:
        Optional[Producer]: Kafka 生产者实例，连接失败返回 None
    """
    global _producer

    if _producer is not None:
        return _producer

    try:
        # 创建生产者配置
        config = {
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
            'client.id': 'music-play-producer',
            # 性能优化配置
            'compression.type': 'snappy',  # 启用压缩
            'linger.ms': 1,  # 优化：降低延迟，减少事件丢失风险（从10ms降到1ms）
            'batch.size': 32768,  # 优化：增加批量大小（从16KB到32KB），吞吐量更高
            # 可靠性配置
            'acks': 1,  # 等待 leader 确认即可（平衡性能和可靠性）
            'retries': 3,  # 重试次数
            'retry.backoff.ms': 100,  # 重试间隔
            # 连接配置
            'message.max.bytes': 10485760  # 最大消息大小：10MB
        }

        _producer = Producer(config)
        logger.info(f"✅ Kafka 生产者初始化成功: {KAFKA_BOOTSTRAP_SERVERS}")

        # 确保 topic 存在
        create_topic_if_not_exists()

        return _producer

    except Exception as e:
        logger.error(f"❌ Kafka 生产者初始化失败: {e}")
        _producer = None
        return None


def create_topic_if_not_exists():
    """创建 topic（如果不存在）"""
    try:
        admin_client = AdminClient({
            'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS
        })

        # 检查 topic 是否存在
        metadata = admin_client.list_topics(timeout=5)

        if MUSIC_PLAY_EVENTS_TOPIC not in metadata.topics:
            # 创建 topic
            new_topic = NewTopic(
                MUSIC_PLAY_EVENTS_TOPIC,
                num_partitions=3,  # 3 个分区，支持并发消费
                replication_factor=1  # 单机环境，复制因子为 1
            )

            fs = admin_client.create_topics([new_topic])

            # 等待创建完成
            for topic, f in fs.items():
                try:
                    f.result()  # 阻塞等待
                    logger.info(f"✅ Topic 创建成功: {topic}")
                except Exception as e:
                    logger.error(f"❌ Topic 创建失败: {topic}, 错误: {e}")
        else:
            logger.info(f"✅ Topic 已存在: {MUSIC_PLAY_EVENTS_TOPIC}")

    except Exception as e:
        logger.warning(f"⚠️ 检查/创建 Topic 失败: {e}")


def delivery_callback(err, msg):
    """消息发送回调函数

    Args:
        err: 错误信息
        msg: 消息对象
    """
    if err:
        logger.error(f"❌ 消息发送失败: {err}, topic: {msg.topic()}")
    else:
        logger.debug(f"✅ 消息发送成功: topic={msg.topic()}, partition={msg.partition()}, offset={msg.offset()}")


def send_play_event(song_id: int, user_id: str, event_type: str = "play") -> bool:
    """发送播放事件到 Kafka

    Args:
        song_id: 歌曲ID
        user_id: 用户ID
        event_type: 事件类型，默认 "play"

    Returns:
        bool: 是否发送成功
    """
    producer = get_kafka_producer()

    if producer is None:
        logger.warning("⚠️ Kafka 未连接，跳过事件发送")
        return False

    try:
        # 构建事件数据
        event = {
            "event_id": str(uuid.uuid4()),
            "song_id": song_id,
            "user_id": user_id,
            "timestamp": int(time.time() * 1000),  # 毫秒时间戳
            "event_type": event_type
        }

        # 序列化为 JSON
        event_json = json.dumps(event, ensure_ascii=False)

        # 异步发送消息
        producer.produce(
            topic=MUSIC_PLAY_EVENTS_TOPIC,
            value=event_json.encode('utf-8'),
            key=str(song_id).encode('utf-8'),  # 使用 song_id 作为 key，保证同一歌曲的事件进入同一分区
            callback=delivery_callback
        )

        # 触发消息发送（非阻塞）
        producer.poll(0)

        logger.info(f"📤 播放事件已发送: song_id={song_id}, user={user_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 发送播放事件失败: song_id={song_id}, 错误: {e}")
        return False


def flush_producer():
    """刷新生产者缓冲区，确保所有消息发送完成

    建议在应用关闭时调用
    """
    global _producer

    if _producer:
        try:
            logger.info("🔄 刷新 Kafka 生产者缓冲区...")
            _producer.flush(timeout=5)  # 最多等待 5 秒
            logger.info("✅ Kafka 生产者缓冲区刷新完成")
        except Exception as e:
            logger.error(f"❌ 刷新 Kafka 生产者缓冲区失败: {e}")


def close_producer():
    """关闭 Kafka 生产者

    建议在应用关闭时调用
    """
    global _producer

    if _producer:
        try:
            flush_producer()
            logger.info("🔒 Kafka 生产者已关闭")
            _producer = None
        except Exception as e:
            logger.error(f"❌ 关闭 Kafka 生产者失败: {e}")


# 优雅关闭处理
import atexit
atexit.register(close_producer)


# ==================== 测试函数 ====================

def test_kafka_connection():
    """测试 Kafka 连接

    Returns:
        bool: 连接是否成功
    """
    try:
        producer = get_kafka_producer()
        if producer is None:
            logger.error("❌ Kafka 连接测试失败：生产者初始化失败")
            return False

        # 发送测试消息
        test_event = {
            "event_id": str(uuid.uuid4()),
            "song_id": 999999,
            "user_id": "test_user",
            "timestamp": int(time.time() * 1000),
            "event_type": "test"
        }

        producer.produce(
            topic=MUSIC_PLAY_EVENTS_TOPIC,
            value=json.dumps(test_event).encode('utf-8'),
            callback=lambda err, msg: logger.info("✅ Kafka 连接测试成功") if not err else logger.error(f"❌ Kafka 连接测试失败: {err}")
        )

        producer.flush(timeout=5)
        return True

    except Exception as e:
        logger.error(f"❌ Kafka 连接测试失败: {e}")
        return False


if __name__ == "__main__":
    # 测试连接
    logger.info("开始测试 Kafka 连接...")

    if test_kafka_connection():
        logger.info("✅ Kafka 连接正常")
    else:
        logger.error("❌ Kafka 连接失败，请检查 Kafka 服务是否启动")
