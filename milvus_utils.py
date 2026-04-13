"""
Milvus 向量数据库工具类
高性能向量存储和检索，支持高 QPS 场景
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
    Index,
    AnnSearchRequest,
    WeightedRanker
)

# 导入配置
from config import (
    MILVUS_HOST, MILVUS_PORT, MILVUS_USER, MILVUS_PASSWORD,
    MILVUS_COLLECTION_NAME, MILVUS_INDEX_TYPE, MILVUS_METRIC_TYPE,
    MILVUS_DIM, MILVUS_EF, MILVUS_M, MILVUS_NLIST, MILVUS_NPROBE,
    MILVUS_CONSISTENCY_LEVEL, MILVUS_ENABLED
)

logger = logging.getLogger(__name__)


class MilvusVectorStore:
    """Milvus 向量数据库封装类"""

    def __init__(self):
        """初始化 Milvus 连接"""
        self.connected = False
        self.collection = None
        self.collection_name = MILVUS_COLLECTION_NAME
        
        if not MILVUS_ENABLED:
            logger.info("[MILVUS] 未启用，跳过连接")
            return
        
        self._connect()

    def _connect(self):
        """建立 Milvus 连接"""
        try:
            # 构建连接参数
            connect_kwargs = {
                "host": MILVUS_HOST,
                "port": MILVUS_PORT,
            }
            
            # 如果有认证信息
            if MILVUS_USER and MILVUS_PASSWORD:
                connect_kwargs["user"] = MILVUS_USER
                connect_kwargs["password"] = MILVUS_PASSWORD
            
            # 建立连接
            connections.connect(**connect_kwargs)
            self.connected = True
            logger.info(f"[MILVUS] ✅ 连接成功: {MILVUS_HOST}:{MILVUS_PORT}")
            
            # 确保 Collection 存在
            self._ensure_collection()
            
        except Exception as e:
            logger.error(f"[MILVUS] ❌ 连接失败: {e}")
            self.connected = False

    def _ensure_collection(self):
        """确保 Collection 存在，如果不存在则创建"""
        try:
            if utility.has_collection(self.collection_name):
                logger.info(f"[MILVUS] Collection '{self.collection_name}' 已存在")
                self.collection = Collection(self.collection_name)
                self.collection.load()
            else:
                logger.info(f"[MILVUS] 创建 Collection: {self.collection_name}")
                self._create_collection()
                
        except Exception as e:
            logger.error(f"[MILVUS] 确保 Collection 失败: {e}")

    def _create_collection(self):
        """创建 Collection 和索引"""
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="length", dtype=DataType.INT64),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=MILVUS_DIM)
        ]
        
        # 创建 Schema
        schema = CollectionSchema(
            fields=fields,
            description="知识图谱文档向量存储"
        )
        
        # 创建 Collection
        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
            consistency_level=MILVUS_CONSISTENCY_LEVEL
        )
        
        # 创建索引
        self._create_index()
        
        logger.info(f"[MILVUS] ✅ Collection '{self.collection_name}' 创建成功")

    def _create_index(self):
        """创建向量索引"""
        try:
            if MILVUS_INDEX_TYPE == "HNSW":
                index_params = {
                    "metric_type": MILVUS_METRIC_TYPE,
                    "index_type": "HNSW",
                    "params": {
                        "M": MILVUS_M,
                        "efConstruction": MILVUS_EF
                    }
                }
            elif MILVUS_INDEX_TYPE == "IVF_FLAT":
                index_params = {
                    "metric_type": MILVUS_METRIC_TYPE,
                    "index_type": "IVF_FLAT",
                    "params": {
                        "nlist": MILVUS_NLIST,
                        "nprobe": MILVUS_NPROBE
                    }
                }
            else:
                # 默认使用 HNSW
                index_params = {
                    "metric_type": MILVUS_METRIC_TYPE,
                    "index_type": "HNSW",
                    "params": {
                        "M": MILVUS_M,
                        "efConstruction": MILVUS_EF
                    }
                }

            index = Index(
                collection=self.collection,
                field_name="vector",
                index_params=index_params
            )
            index.wait_for_index_build_completion()
            logger.info(f"[MILVUS] ✅ 索引创建成功: {MILVUS_INDEX_TYPE}")
            
        except Exception as e:
            logger.error(f"[MILVUS] 创建索引失败: {e}")

    def insert(
        self,
        ids: List[str],
        vectors: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> bool:
        """
        插入向量数据

        Args:
            ids: 唯一 ID 列表
            vectors: 向量列表
            documents: 文档内容列表
            metadatas: 元数据列表

        Returns:
            是否插入成功
        """
        if not self.connected or not self.collection:
            logger.error("[MILVUS] 未连接，无法插入数据")
            return False

        try:
            # 准备数据
            data = [
                ids,  # id
                [m.get("doc_id", "") for m in metadatas],  # doc_id
                [m.get("chunk_index", 0) for m in metadatas],  # chunk_index
                documents,  # content
                [m.get("length", 0) for m in metadatas],  # length
                vectors  # vector
            ]
            
            # 插入数据
            self.collection.insert(data)
            self.collection.flush()
            
            logger.info(f"[MILVUS] ✅ 成功插入 {len(ids)} 条数据")
            return True
            
        except Exception as e:
            logger.error(f"[MILVUS] 插入数据失败: {e}")
            return False

    def search(
        self,
        query_vectors: List[List[float]],
        top_k: int = 10,
        filter_expr: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        向量检索

        Args:
            query_vectors: 查询向量列表
            top_k: 返回 top-k 结果
            filter_expr: 过滤表达式（可选）

        Returns:
            检索结果列表
        """
        if not self.connected or not self.collection:
            logger.error("[MILVUS] 未连接，无法检索")
            return []

        try:
            # 搜索参数
            search_params = {
                "metric_type": MILVUS_METRIC_TYPE,
                "params": {}
            }
            
            # 根据索引类型设置搜索参数
            if MILVUS_INDEX_TYPE == "HNSW":
                search_params["params"]["ef"] = MILVUS_EF
            elif MILVUS_INDEX_TYPE == "IVF_FLAT":
                search_params["params"]["nprobe"] = MILVUS_NPROBE

            # 执行搜索
            results = self.collection.search(
                data=query_vectors,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["id", "doc_id", "chunk_index", "content", "length"]
            )

            # 格式化结果
            formatted_results = []
            for hits in results:
                hits_list = []
                for hit in hits:
                    # 计算相似度（Milvus 返回的是距离，需要转换）
                    distance = hit.distance
                    # 距离越小越相似，转换为相似度
                    if MILVUS_METRIC_TYPE == "COSINE" or MILVUS_METRIC_TYPE == "IP":
                        similarity = distance  # 内积或余弦相似度直接使用
                    else:
                        similarity = 1 / (1 + distance)  # L2 距离转换为相似度

                    hits_list.append({
                        "id": hit.entity.get("id"),
                        "doc_id": hit.entity.get("doc_id"),
                        "chunk_index": hit.entity.get("chunk_index"),
                        "content": hit.entity.get("content"),
                        "length": hit.entity.get("length"),
                        "distance": distance,
                        "similarity": similarity
                    })
                formatted_results.append(hits_list)

            return formatted_results

        except Exception as e:
            logger.error(f"[MILVUS] 检索失败: {e}")
            return []

    def delete(self, ids: List[str]) -> bool:
        """
        删除指定 ID 的数据

        Args:
            ids: 要删除的 ID 列表

        Returns:
            是否删除成功
        """
        if not self.connected or not self.collection:
            logger.error("[MILVUS] 未连接，无法删除")
            return False

        try:
            # 构建过滤表达式
            expr = f"id in {ids}"
            self.collection.delete(expr)
            self.collection.flush()
            
            logger.info(f"[MILVUS] ✅ 成功删除 {len(ids)} 条数据")
            return True
            
        except Exception as e:
            logger.error(f"[MILVUS] 删除数据失败: {e}")
            return False

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """
        删除指定文档的所有数据

        Args:
            doc_id: 文档 ID

        Returns:
            是否删除成功
        """
        if not self.connected or not self.collection:
            logger.error("[MILVUS] 未连接，无法删除")
            return False

        try:
            expr = f'doc_id == "{doc_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            
            logger.info(f"[MILVUS] ✅ 成功删除文档 {doc_id} 的所有数据")
            return True
            
        except Exception as e:
            logger.error(f"[MILVUS] 删除文档数据失败: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取 Collection 统计信息"""
        if not self.connected or not self.collection:
            return {"status": "disconnected"}
        
        try:
            stats = self.collection.num_entities
            return {
                "status": "connected",
                "name": self.collection_name,
                "entities": stats
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self):
        """关闭连接"""
        try:
            connections.disconnect("default")
            self.connected = False
            logger.info("[MILVUS] 连接已关闭")
        except Exception as e:
            logger.error(f"[MILVUS] 关闭连接失败: {e}")


# 全局 Milvus 客户端实例
_milvus_client = None


def get_milvus_client() -> Optional[MilvusVectorStore]:
    """获取 Milvus 客户端单例"""
    global _milvus_client
    
    if not MILVUS_ENABLED:
        return None
    
    if _milvus_client is None:
        _milvus_client = MilvusVectorStore()
    
    return _milvus_client


def reset_milvus_client():
    """重置 Milvus 客户端（用于重新连接）"""
    global _milvus_client
    
    if _milvus_client:
        _milvus_client.close()
        _milvus_client = None