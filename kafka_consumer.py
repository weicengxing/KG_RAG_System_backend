"""
Kafka 消费者服务
用于异步处理知识图谱文档构建任务
"""

import sys
import json
import time
import asyncio
import logging
from confluent_kafka import Consumer, KafkaException, KafkaError, AdminClient, NewTopic
from task_manager import task_manager
from kg_service import kg_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Kafka 配置
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'kg-doc-processor',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True
}


class DocProcessor:
    """文档处理器"""
    
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    async def process_document(self, task_id: str, doc_id: str, file_path: str, filename: str):
        """
        异步处理文档（解析、分块、抽取、建图谱、向量化）
        
        Args:
            task_id: 任务ID
            doc_id: 文档ID
            file_path: 文件路径
            filename: 文件名
        """
        start_time = time.time()
        
        try:
            logger.info(f"📄 开始处理文档: {filename} (doc_id={doc_id}, task_id={task_id})")
            
            # 更新进度：开始解析
            task_manager.update_progress(task_id, 10, "parsing", f"正在解析文档: {filename}")
            logger.info(f"📖 [10%] 开始解析文档: {filename}")
            
            # 1. 解析文档
            text = kg_service.parse_document(file_path)
            text_length = len(text)
            logger.info(f"✅ [20%] 文档解析完成，文本长度: {text_length} 字符")
            
            # 更新进度：开始分块
            task_manager.update_progress(task_id, 30, "chunking", "正在进行文本分块...")
            logger.info(f"🔪 [30%] 开始文本分块")
            
            # 2. 文本分块
            chunks = kg_service.split_text(text)
            logger.info(f"✅ [40%] 文本分块完成，共 {len(chunks)} 个分块")
            
            # 更新进度：开始抽取实体关系
            task_manager.update_progress(task_id, 50, "extracting", "正在抽取实体关系...")
            logger.info(f"🔍 [50%] 开始抽取实体关系")
            
            # 3. 并发抽取实体关系
            triplets = await kg_service.extract_batch_async(chunks)
            logger.info(f"✅ [70%] 实体关系抽取完成，共 {len(triplets)} 个三元组")
            
            # 更新进度：抽取完成
            task_manager.update_progress(task_id, 70, "extracting", f"实体关系抽取完成，共 {len(triplets)} 个三元组")
            
            # 更新进度：开始构建知识图谱
            task_manager.update_progress(task_id, 80, "building_graph", "正在构建知识图谱...")
            logger.info(f"🕸️ [80%] 开始保存到 Neo4j")
            
            # 4. 保存到 Neo4j
            kg_service.save_triplets_to_neo4j(triplets, doc_id)
            logger.info(f"✅ [85%] Neo4j 图谱构建完成")
            
            # 更新进度：开始向量化
            task_manager.update_progress(task_id, 90, "embedding", "正在生成向量嵌入...")
            logger.info(f"🔢 [90%] 开始向量化并保存到 ChromaDB")
            
            # 5. 保存到 ChromaDB
            kg_service.save_chunks_to_chromadb(chunks, doc_id)
            logger.info(f"✅ [95%] ChromaDB 向量化完成")
            
            # 6. 获取图谱数据（用于前端展示）
            logger.info(f"📊 [98%] 获取图谱数据")
            graph_data = kg_service.get_graph_data(doc_id, limit=100)
            
            # 计算耗时
            elapsed_time = round(time.time() - start_time, 2)
            logger.info(f"⏱️ 处理完成，总耗时: {elapsed_time} 秒")
            
            # 7. 标记任务完成
            result_data = {
                "doc_id": doc_id,
                "filename": filename,
                "total_chunks": len(chunks),
                "total_triplets": len(triplets),
                "elapsed_time": elapsed_time,
                "graph_data": graph_data,
                "text_length": text_length
            }
            
            task_manager.complete_task(task_id, result_data)
            logger.info(f"✅✅✅ 任务完成: {task_id}")
            
            return result_data
            
        except Exception as e:
            error_msg = f"文档处理失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception(e)
            
            # 标记任务失败
            task_manager.fail_task(task_id, error_msg)
            
            raise e
    
    def run_async_task(self, task_id: str, doc_id: str, file_path: str, filename: str):
        """
        在事件循环中运行异步任务
        
        Args:
            task_id: 任务ID
            doc_id: 文档ID
            file_path: 文件路径
            filename: 文件名
        """
        try:
            # 在事件循环中运行异步任务
            result = self.loop.run_until_complete(
                self.process_document(task_id, doc_id, file_path, filename)
            )
            return result
        except Exception as e:
            logger.error(f"❌ 异步任务执行失败: {e}")
            return None
    
    def close(self):
        """关闭事件循环"""
        self.loop.close()


def create_topic_if_not_exists(topic_name: str, num_partitions: int = 3, replication_factor: int = 1):
    """
    自动创建 Kafka Topic（如果不存在）
    
    Args:
        topic_name: Topic 名称
        num_partitions: 分区数
        replication_factor: 副本因子
    """
    try:
        # 创建 AdminClient
        admin_client = AdminClient({'bootstrap.servers': 'localhost:9092'})
        
        # 检查 Topic 是否存在
        metadata = admin_client.list_topics(timeout=10)
        if topic_name in metadata.topics:
            logger.info(f"✅ Topic '{topic_name}' 已存在")
            return True
        
        # 创建新 Topic
        logger.info(f"📝 正在创建 Topic '{topic_name}'...")
        new_topic = NewTopic(
            topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor
        )
        
        future = admin_client.create_topics([new_topic])
        
        # 等待创建完成
        for name, f in future.items():
            try:
                f.result()
                logger.info(f"✅ Topic '{name}' 创建成功")
            except Exception as e:
                logger.error(f"❌ 创建 Topic '{name}' 失败: {str(e)}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"❌ 检查/创建 Topic 失败: {str(e)}")
        logger.info("ℹ️ 请手动创建 Topic: bin/kafka-topics.sh --create --topic doc-upload --bootstrap-server localhost:9092")
        return False


def consume_messages():
    """
    消费 Kafka 消息的主函数
    """
    # 自动创建 Topic（如果不存在）
    topic = 'doc-upload'
    create_topic_if_not_exists(topic, num_partitions=3, replication_factor=1)
    
    # 创建消费者
    consumer = Consumer(KAFKA_CONFIG)
    
    # 订阅主题
    consumer.subscribe([topic])
    
    logger.info("🎧 Kafka 消费者已启动，正在监听主题: " + topic)
    
    # 创建文档处理器
    processor = DocProcessor()
    
    try:
        while True:
            # 轮询消息（超时 1 秒）
            msg = consumer.poll(1.0)
            
            if msg is None:
                # 没有消息，继续等待
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # 到达分区末尾，不是错误
                    continue
                else:
                    # 其他错误
                    logger.error(f"❌ Kafka 消费错误: {msg.error()}")
                    raise KafkaException(msg.error())
            
            # 成功获取消息
            try:
                # 解析消息
                kafka_message = json.loads(msg.value().decode('utf-8'))
                task_id = kafka_message.get('task_id')
                doc_id = kafka_message.get('doc_id')
                file_path = kafka_message.get('file_path')
                filename = kafka_message.get('filename')
                
                logger.info(f"📥 收到消息: task_id={task_id}, doc_id={doc_id}, filename={filename}")
                
                # 处理文档
                processor.run_async_task(task_id, doc_id, file_path, filename)
                
                # 手动提交偏移量
                consumer.commit(msg)
                logger.info(f"✅ 偏移量已提交: topic={msg.topic()}, partition={msg.partition()}, offset={msg.offset()}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON 解析失败: {e}")
            except Exception as e:
                logger.error(f"❌ 处理消息失败: {e}")
                logger.exception(e)
    
    except KeyboardInterrupt:
        logger.info("⏸️ 收到中断信号，正在关闭消费者...")
    except Exception as e:
        logger.error(f"❌ 消费者异常: {e}")
        logger.exception(e)
    finally:
        # 关闭资源
        processor.close()
        consumer.close()
        logger.info("🛑 Kafka 消费者已关闭")


if __name__ == '__main__':
    # 启动消费者
    try:
        consume_messages()
    except Exception as e:
        logger.error(f"❌ 程序异常退出: {e}")
        sys.exit(1)
