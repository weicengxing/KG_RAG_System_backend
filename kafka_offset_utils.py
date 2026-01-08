"""
Kafka Offset 工具
用于查询指定时间范围的 Kafka offset，优化 Spark 批处理读取性能
"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional, Tuple
from confluent_kafka import Consumer, KafkaError, TopicPartition

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Kafka 配置
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
MUSIC_PLAY_EVENTS_TOPIC = 'music-play-events'


def get_kafka_consumer() -> Consumer:
    """创建 Kafka 消费者（仅用于查询 offset）

    Returns:
        Consumer: Kafka 消费者实例
    """
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'spark-offset-query',  # 临时 group id，不会实际消费
        'enable.auto.commit': False,  # 不自动提交
        'auto.offset.reset': 'earliest',  # 从最早开始
        'session.timeout.ms': 10000,  # 10秒超时
    }
    
    consumer = Consumer(conf)
    return consumer


def get_partitions_for_topic(topic: str, consumer: Consumer) -> list[int]:
    """获取 topic 的所有分区

    Args:
        topic: topic 名称
        consumer: Kafka 消费者

    Returns:
        list[int]: 分区列表
    """
    cluster_metadata = consumer.list_topics(topic)
    topic_metadata = cluster_metadata.topics.get(topic)
    
    if not topic_metadata:
        raise ValueError(f"Topic {topic} 不存在")
    
    partitions = list(topic_metadata.partitions.keys())
    logger.info(f"✅ Topic {topic} 有 {len(partitions)} 个分区: {partitions}")
    
    return partitions


def get_offsets_by_timestamp(
    consumer: Consumer,
    topic: str,
    start_timestamp_ms: int,
    end_timestamp_ms: int
) -> Dict[str, Dict]:
    """查询指定时间范围的 offset

    Args:
        consumer: Kafka 消费者
        topic: topic 名称
        start_timestamp_ms: 开始时间戳（毫秒）
        end_timestamp_ms: 结束时间戳（毫秒）

    Returns:
        Dict[str, Dict]: Spark 可用的 offset 格式
            {
                "startingOffsets": {
                    "topic": {"partition": offset, ...}
                },
                "endingOffsets": {
                    "topic": {"partition": offset, ...}
                }
            }
    """
    logger.info(f"🔍 查询 offset 范围: topic={topic}")
    logger.info(f"   - 开始时间: {datetime.fromtimestamp(start_timestamp_ms / 1000)}")
    logger.info(f"   - 结束时间: {datetime.fromtimestamp(end_timestamp_ms / 1000)}")
    
    # 获取所有分区
    partitions = get_partitions_for_topic(topic, consumer)
    
    # 查询起始 offset
    start_offsets = {}
    for partition in partitions:
        tp = TopicPartition(topic, partition)
        
        # 查找大于等于 start_timestamp 的第一个 offset
        offsets = consumer.offsets_for_times({tp: start_timestamp_ms})
        
        if offsets and offsets[tp]:
            start_offset = offsets[tp].offset
            logger.info(f"   - 分区 {partition}: 起始 offset={start_offset}")
        else:
            # 没有找到该时间点之后的 offset，说明该分区没有数据
            # 使用 earliest offset
            try:
                earliest = consumer.get_watermark_offsets(tp)[0]
                start_offset = earliest
                logger.warning(f"   - 分区 {partition}: 未找到时间点对应的 offset，使用 earliest={start_offset}")
            except KafkaError as e:
                logger.error(f"   - 分区 {partition}: 获取 earliest offset 失败: {e}")
                start_offset = 0
        
        start_offsets[str(partition)] = start_offset
    
    # 查询结束 offset
    end_offsets = {}
    for partition in partitions:
        tp = TopicPartition(topic, partition)
        
        # 查找大于等于 end_timestamp 的第一个 offset
        offsets = consumer.offsets_for_times({tp: end_timestamp_ms})
        
        if offsets and offsets[tp]:
            end_offset = offsets[tp].offset
            logger.info(f"   - 分区 {partition}: 结束 offset={end_offset}")
        else:
            # 没有找到该时间点之后的 offset，说明该分区数据早于该时间点
            # 使用 latest offset（最新）
            try:
                latest = consumer.get_watermark_offsets(tp)[1]
                end_offset = latest
                logger.warning(f"   - 分区 {partition}: 未找到时间点对应的 offset，使用 latest={end_offset}")
            except KafkaError as e:
                logger.error(f"   - 分区 {partition}: 获取 latest offset 失败: {e}")
                end_offset = -1  # -1 表示 latest
        
        end_offsets[str(partition)] = end_offset
    
    # 构建 Spark offset 格式
    spark_start_offsets = {topic: start_offsets}
    spark_end_offsets = {topic: end_offsets}
    
    logger.info(f"✅ Offset 查询完成")
    logger.info(f"   - startingOffsets: {json.dumps(spark_start_offsets)}")
    logger.info(f"   - endingOffsets: {json.dumps(spark_end_offsets)}")
    
    return {
        'startingOffsets': json.dumps(spark_start_offsets),
        'endingOffsets': json.dumps(spark_end_offsets)
    }


def get_offset_range_summary(
    consumer: Consumer,
    topic: str,
    start_timestamp_ms: int,
    end_timestamp_ms: int
) -> Tuple[int, int]:
    """估算时间范围内的消息数量

    Args:
        consumer: Kafka 消费者
        topic: topic 名称
        start_timestamp_ms: 开始时间戳（毫秒）
        end_timestamp_ms: 结束时间戳（毫秒）

    Returns:
        Tuple[int, int]: (消息数量, 分区数量)
    """
    try:
        partitions = get_partitions_for_topic(topic, consumer)
        offset_info = get_offsets_by_timestamp(consumer, topic, start_timestamp_ms, end_timestamp_ms)
        
        start_offsets = json.loads(offset_info['startingOffsets'])[topic]
        end_offsets = json.loads(offset_info['endingOffsets'])[topic]
        
        total_messages = 0
        for partition in partitions:
            start = start_offsets[str(partition)]
            end = end_offsets[str(partition)]
            
            if end == -1:  # latest offset，无法计算确切数量
                total_messages = -1  # -1 表示无法估算
                break
            
            messages = end - start
            total_messages += messages
        
        if total_messages == -1:
            logger.warning(f"⚠️ 无法准确估算消息数量（某个分区使用了 latest offset）")
        else:
            logger.info(f"✅ 估算消息数量: {total_messages} 条")
        
        return total_messages, len(partitions)
        
    except Exception as e:
        logger.error(f"❌ 估算消息数量失败: {e}")
        return -1, 0


def main():
    """测试函数"""
    import sys
    from datetime import timedelta
    
    if len(sys.argv) < 2:
        print("Usage: python kafka_offset_utils.py <hours_ago>")
        print("Example: python kafka_offset_utils.py 24")
        sys.exit(1)
    
    hours_ago = int(sys.argv[1])
    
    # 计算时间范围
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_ago)
    
    start_timestamp_ms = int(start_time.timestamp() * 1000)
    end_timestamp_ms = int(end_time.timestamp() * 1000)
    
    print(f"\n🚀 开始查询 offset 范围...")
    print(f"   - 时间范围: {start_time} 到 {end_time} ({hours_ago} 小时)")
    
    try:
        consumer = get_kafka_consumer()
        
        # 查询 offset
        offset_info = get_offsets_by_timestamp(
            consumer,
            MUSIC_PLAY_EVENTS_TOPIC,
            start_timestamp_ms,
            end_timestamp_ms
        )
        
        # 估算消息数量
        total_messages, partition_count = get_offset_range_summary(
            consumer,
            MUSIC_PLAY_EVENTS_TOPIC,
            start_timestamp_ms,
            end_timestamp_ms
        )
        
        print(f"\n✅ 查询完成:")
        print(f"   - 分区数: {partition_count}")
        print(f"   - 估算消息数: {total_messages if total_messages > 0 else '无法估算'}")
        print(f"   - startingOffsets: {offset_info['startingOffsets']}")
        print(f"   - endingOffsets: {offset_info['endingOffsets']}")
        
        consumer.close()
        
    except Exception as e:
        logger.error(f"❌ 查询失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
