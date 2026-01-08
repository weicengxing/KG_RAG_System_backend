"""
Flink 音乐播放流处理作业（生产级优化版本）
从 Kafka 消费播放事件，使用滑动窗口计算热度，输出到 Redis

优化改进：
1. ✅ 添加 Watermark 策略，解决窗口无法触发问题
2. ✅ 使用 AggregateFunction 增量计算，避免 OOM
3. ✅ 优化 Redis 写入，添加 Top N 限制
4. ✅ 改进数据类型，使用 Row 替代 PICKLED_BYTE_ARRAY
"""

import json
import logging
import time
from typing import Dict, List

import redis
from pyflink.common import Types, Row
from pyflink.common.time import Duration
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer, KafkaOffsetsInitializer
from pyflink.datastream.functions import (
    AggregateFunction,
    ProcessWindowFunction,
    RuntimeContext,
    MapFunction
)
from pyflink.datastream.window import SlidingEventTimeWindows

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 配置参数 ====================

KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
MUSIC_PLAY_EVENTS_TOPIC = 'music-play-events'
CONSUMER_GROUP_ID = 'flink-music-trending-consumer'

# 窗口配置
WINDOW_SIZE_SECONDS = 3600  # 1小时窗口
WINDOW_SLIDE_SECONDS = 300  # 5分钟滑动

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None

# Top N 配置
TOP_N_COUNT = 1000  # 只保留前1000首热门歌曲

# Watermark 配置
WATERMARK_DELAY_SECONDS = 10  # 允许10秒的乱序

# ==================== Redis 连接 ====================

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=False  # 保持 bytes 格式
    )
    redis_client.ping()
    logger.info(f"✅ Flink Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Flink Redis 连接失败: {e}")
    redis_client = None


# ==================== 数据结构定义 ====================

class PlayEvent:
    """播放事件数据结构"""
    
    def __init__(self, event_id: str, song_id: int, user_id: str, timestamp: int, event_type: str):
        self.event_id = event_id
        self.song_id = song_id
        self.user_id = user_id
        self.timestamp = timestamp  # 毫秒时间戳
        self.event_type = event_type
        self.timestamp_sec = timestamp / 1000.0  # 转换为秒
    
    def to_dict(self):
        """转换为字典"""
        return {
            'event_id': self.event_id,
            'song_id': self.song_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type
        }
    
    @staticmethod
    def from_json(json_str: str):
        """从 JSON 字符串解析"""
        try:
            data = json.loads(json_str)
            return PlayEvent(
                event_id=data.get('event_id', ''),
                song_id=data.get('song_id', 0),
                user_id=data.get('user_id', ''),
                timestamp=data.get('timestamp', int(time.time() * 1000)),
                event_type=data.get('event_type', 'play')
            )
        except Exception as e:
            logger.error(f"解析播放事件失败: {e}")
            return None


class SongHotness:
    """歌曲热度结果"""
    
    def __init__(self, song_id: int, hotness: float, play_count: int, window_end: int):
        self.song_id = song_id
        self.hotness = hotness
        self.play_count = play_count
        self.window_end = window_end


# ==================== MapFunction：解析 JSON 并转换为 Row ====================

class EventParserMapFunction(MapFunction):
    """将 JSON 字符串解析为 PlayEvent 并转换为 Row"""
    
    def map(self, value: str) -> Row:
        """Map 函数"""
        try:
            event = PlayEvent.from_json(value)
            if event:
                # 转换为 Row 格式，避免使用 PICKLED_BYTE_ARRAY
                return Row(
                    event.event_id,
                    event.song_id,
                    event.user_id,
                    event.timestamp,
                    event.event_type,
                    event.timestamp_sec
                )
            else:
                return None
        except Exception as e:
            logger.error(f"解析事件失败: {e}")
            return None


# ==================== AggregateFunction：增量计算热度 ====================

class HotnessAggregateFunction(AggregateFunction):
    """热度聚合函数（增量计算，避免 OOM）"""
    
    def create_accumulator(self):
        """创建累加器：[播放次数, 时间戳总和]"""
        return (0, 0)
    
    def add(self, element: Row, accumulator):
        """添加元素到累加器"""
        play_count, timestamp_sum = accumulator
        return (play_count + 1, timestamp_sum + element.timestamp_sec)
    
    def merge(self, acc_a, acc_b):
        """合并累加器"""
        count_a, sum_a = acc_a
        count_b, sum_b = acc_b
        return (count_a + count_b, sum_a + sum_b)
    
    def get_result(self, accumulator):
        """获取聚合结果"""
        play_count, timestamp_sum = accumulator
        return (play_count, timestamp_sum)


# ==================== ProcessWindowFunction：计算热度并写入 Redis ====================

class HotnessProcessorFunction(ProcessWindowFunction):
    """热度处理函数（窗口函数）"""
    
    def __init__(self):
        super().__init__()
        self.redis_client = None
    
    def open(self, runtime_context: RuntimeContext):
        """初始化 Redis 连接"""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=False
            )
            logger.info("✅ Flink 窗口函数 Redis 连接成功")
        except Exception as e:
            logger.error(f"❌ Flink 窗口函数 Redis 连接失败: {e}")
    
    def process(self, key, context, elements: List):
        """处理窗口数据
        
        Args:
            key: song_id (字符串类型)
            context: 窗口上下文
            elements: 聚合结果列表 [(play_count, timestamp_sum), ...]
        """
        song_id = int(key)
        
        if not elements:
            return
        
        # 获取聚合结果
        play_count, timestamp_sum = elements[0]
        
        # 获取窗口结束时间
        window_end = context.window().end
        
        # 计算热度
        hotness = self._calculate_hotness(play_count, timestamp_sum, window_end)
        
        logger.info(f"📊 窗口计算: song_id={song_id}, play_count={play_count}, hotness={hotness:.2f}")
        
        # 输出到 Redis
        self._write_to_redis(song_id, hotness)
    
    def _calculate_hotness(self, play_count: int, timestamp_sum: float, window_end: int) -> float:
        """计算热度分数
        
        热度算法：热度 = 播放次数 × 时间衰减因子 × 窗口时间衰减
        
        Args:
            play_count: 播放次数
            timestamp_sum: 时间戳总和（秒）
            window_end: 窗口结束时间（毫秒）
            
        Returns:
            float: 热度分数
        """
        if play_count == 0:
            return 0.0
        
        # 计算平均播放时间（秒）
        avg_play_time = timestamp_sum / play_count
        
        # 窗口结束时间（秒）
        window_end_sec = window_end / 1000.0
        
        # 计算时间衰减因子（越接近窗口末尾，衰减因子越大）
        # 衰减因子范围：[0, 1]，最近播放的歌曲接近1，很久前的接近0
        decay_age_seconds = 300  # 5分钟衰减影响范围
        time_diff = window_end_sec - avg_play_time
        decay_factor = max(0, 1 - (time_diff / decay_age_seconds))
        
        # 热度 = 播放次数 × 时间衰减因子
        hotness = play_count * decay_factor
        
        # 添加额外的时间衰减（窗口内平均时间越接近窗口末尾，热度越高）
        window_age = window_end_sec - avg_play_time
        time_decay = max(0.1, 1 - (window_age / WINDOW_SIZE_SECONDS))
        
        hotness = hotness * time_decay
        
        return hotness
    
    def _write_to_redis(self, song_id: int, hotness: float):
        """写入 Redis（优化版：添加 Top N 限制）
        
        Args:
            song_id: 歌曲ID
            hotness: 热度分数
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis 未连接，无法写入热度")
            return
        
        try:
            key = "music:trending:hot"
            
            # 添加到 ZSET
            self.redis_client.zadd(key, {str(song_id): hotness})
            
            # 只保留前 TOP_N_COUNT 首歌曲（避免无限增长）
            self.redis_client.zremrangebyrank(key, 0, -TOP_N_COUNT - 1)
            
            # 设置过期时间（仅在第一次设置时）
            if self.redis_client.ttl(key) == -1:  # 没有设置过期时间
                self.redis_client.expire(key, 6 * 3600)  # 6小时
            
            logger.debug(f"✅ 写入 Redis: song_id={song_id}, hotness={hotness:.2f}")
        except Exception as e:
            logger.error(f"❌ 写入 Redis 失败: song_id={song_id}, {e}")
    
    def close(self):
        """关闭连接"""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("🔒 Flink 窗口函数 Redis 连接已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭 Redis 连接失败: {e}")


# ==================== Flink 作业主函数 ====================

def create_music_hotness_job():
    """创建音乐热度计算作业"""
    
    # 创建执行环境
    env = StreamExecutionEnvironment.get_execution_environment()
    
    # 配置 Checkpoint（故障恢复）
    env.enable_checkpointing(60000)  # 每 60 秒做一次 checkpoint
    env.get_checkpoint_config().set_checkpoint_timeout(300000)  # checkpoint 超时时间 5 分钟
    env.get_checkpoint_config().set_min_pause_between_checkpoints(30000)  # checkpoint 最小间隔 30 秒
    
    logger.info("✅ Flink 执行环境创建成功")
    
    # 配置 Kafka Consumer
    kafka_props = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': CONSUMER_GROUP_ID,
        'auto.offset.reset': 'latest',  # 从最新消息开始
    }
    
    kafka_consumer = FlinkKafkaConsumer(
        topics=MUSIC_PLAY_EVENTS_TOPIC,
        deserialization_schema=Types.STRING(),
        properties=kafka_props,
        starting_offsets=KafkaOffsetsInitializer.latest()
    )
    
    logger.info(f"✅ Kafka Consumer 创建成功: {MUSIC_PLAY_EVENTS_TOPIC}")
    
    # 创建数据流
    stream = env.add_source(kafka_consumer)
    
    # 解析 JSON 字符串为 Row 格式
    parsed_stream = stream.map(EventParserMapFunction(), output_type=Types.ROW(
        [Types.STRING(), Types.INT(), Types.STRING(), Types.LONG(), Types.STRING(), Types.FLOAT()]
    ))
    
    # 过滤无效事件
    valid_stream = parsed_stream.filter(lambda x: x is not None)
    
    # ✅ 关键修复：添加 Watermark 策略
    watermark_strategy = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.of_seconds(WATERMARK_DELAY_SECONDS))
        .with_timestamp_assigner(lambda event, timestamp: event[3])  # 使用第3个字段：timestamp (毫秒)
        .with_idleness(Duration.of_minutes(5))  # 5分钟无数据视为空闲分区
    )
    
    valid_stream = valid_stream.assign_timestamps_and_watermarks(watermark_strategy)
    logger.info("✅ Watermark 策略已添加")
    
    # 按 song_id 分区
    keyed_stream = valid_stream.key_by(lambda e: str(e[1]), key_type=Types.STRING())  # 使用第1个字段：song_id
    
    # 应用滑动窗口（1小时窗口，5分钟滑动）
    windowed_stream = keyed_stream.window(
        SlidingEventTimeWindows.of(
            size_ms=Duration.of_seconds(WINDOW_SIZE_SECONDS).to_milliseconds(),
            slide_ms=Duration.of_seconds(WINDOW_SLIDE_SECONDS).to_milliseconds()
        )
    )
    
    # ✅ 使用 AggregateFunction + ProcessWindowFunction 组合（避免 OOM）
    # AggregateFunction 增量计算，ProcessWindowFunction 只处理聚合结果
    hotness_stream = windowed_stream.aggregate(
        HotnessAggregateFunction(),
        HotnessProcessorFunction()
    )
    
    logger.info("✅ Flink 作业构建完成（生产级优化版）")
    
    return env


# ==================== 辅助函数 ====================

def submit_job_to_cluster(jar_path: str = None):
    """提交作业到 Flink 集群
    
    Args:
        jar_path: Flink Python 作业 jar 包路径（可选）
    """
    try:
        # 创建作业
        env = create_music_hotness_job()
        
        # 执行作业
        logger.info("🚀 开始执行 Flink 作业...")
        env.execute("Music Hotness Calculator (Production)")
        
    except Exception as e:
        logger.error(f"❌ Flink 作业执行失败: {e}")
        raise


def run_local():
    """本地运行模式（用于测试）"""
    try:
        # 创建作业
        env = create_music_hotness_job()
        
        # 执行作业
        logger.info("🚀 本地运行 Flink 作业...")
        env.execute("Music Hotness Calculator (Local)")
        
    except Exception as e:
        logger.error(f"❌ 本地运行失败: {e}")
        raise


# ==================== 测试函数 ====================

def test_flink_job():
    """测试 Flink 作业
    
    Returns:
        bool: 测试是否成功
    """
    try:
        logger.info("开始测试 Flink 作业...")
        
        # 测试 PlayEvent 解析
        test_json = json.dumps({
            'event_id': 'test-001',
            'song_id': 1,
            'user_id': 'test_user',
            'timestamp': int(time.time() * 1000),
            'event_type': 'play'
        })
        
        event = PlayEvent.from_json(test_json)
        if event:
            logger.info(f"✅ 事件解析成功: {event.to_dict()}")
        else:
            logger.error("❌ 事件解析失败")
            return False
        
        # 测试 AggregateFunction
        agg_func = HotnessAggregateFunction()
        accumulator = agg_func.create_accumulator()
        logger.info(f"✅ AggregateFunction 创建成功: {accumulator}")
        
        # 测试 Redis 连接
        if redis_client:
            redis_client.ping()
            logger.info("✅ Redis 连接正常")
        else:
            logger.warning("⚠️ Redis 未连接")
        
        logger.info("✅ Flink 作业测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ Flink 作业测试失败: {e}")
        return False


# ==================== 主程序 ====================

if __name__ == "__main__":
    import sys
    
    # 日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 命令行参数
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = 'local'  # 默认本地运行
    
    logger.info(f"🎵 Flink 音乐热度计算作业启动模式: {mode}")
    logger.info(f"📊 生产级优化版本：Watermark + AggregateFunction + Top N 限制")
    
    # 测试模式
    if mode == 'test':
        if test_flink_job():
            logger.info("✅ 测试成功")
            sys.exit(0)
        else:
            logger.error("❌ 测试失败")
            sys.exit(1)
    
    # 提交到集群
    elif mode == 'cluster':
        try:
            submit_job_to_cluster()
            logger.info("✅ 作业已提交到集群")
        except Exception as e:
            logger.error(f"❌ 提交作业失败: {e}")
            sys.exit(1)
    
    # 本地运行（默认）
    else:
        try:
            run_local()
            logger.info("✅ 作业执行完成")
        except Exception as e:
            logger.error(f"❌ 本地运行失败: {e}")
            sys.exit(1)
