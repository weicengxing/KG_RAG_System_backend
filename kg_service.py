"""
知识图谱RAG系统核心服务
包含文档处理、图谱构建、向量存储、RAG问答等功能
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time
import hashlib


# 文档处理
from PyPDF2 import PdfReader

# 文本分块器 - 兼容不同版本的langchain
try:
    # 新版本 langchain
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    try:
        # 旧版本 langchain
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        # 如果都不行，使用简单的分块实现
        class RecursiveCharacterTextSplitter:
            def __init__(self, chunk_size, chunk_overlap, **kwargs):
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap

            def split_text(self, text):
                """简单的文本分块实现"""
                chunks = []
                start = 0
                text_length = len(text)

                while start < text_length:
                    end = start + self.chunk_size
                    chunk = text[start:end]
                    chunks.append(chunk)
                    start = end - self.chunk_overlap

                return chunks

# 向量数据库
import chromadb
from chromadb.config import Settings

# Neo4j图数据库
from neo4j import GraphDatabase

# LLM和Embeddings
from openai import OpenAI


# 引入你刚才在 config.py 中定义的新变量名
from config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,           # LLM 相关
    EMBED_API_KEY, EMBED_BASE_URL, EMBED_MODEL,         # Embedding 相关 (注意变量名对齐)
    CHUNK_SIZE, CHUNK_OVERLAP,
    VECTOR_SEARCH_TOP_K, GRAPH_SEARCH_HOPS
)


class KnowledgeGraphService:
    """知识图谱RAG服务类"""

    def __init__(self):
        """初始化服务"""
        # Neo4j连接
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

        # ChromaDB客户端（持久化存储）
        chroma_data_dir = os.path.join(os.path.dirname(__file__), "chroma_data")
        os.makedirs(chroma_data_dir, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=chroma_data_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # 创建或获取集合
        self.collection = self.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )

          # 3. 初始化 LLM 客户端 (使用 LLM 专用配置)
        self.llm_client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )

        # 4. 初始化 Embedding 客户端 (使用 ModelScope 配置)
        self.embed_client = OpenAI(
            api_key=EMBED_API_KEY,
            base_url=EMBED_BASE_URL
        )

        # 文本分块器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""]
        )

        # 线程池用于并发处理
        self.executor = ThreadPoolExecutor(max_workers=10)

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'neo4j_driver'):
            self.neo4j_driver.close()

    # ==================== 文档处理 ====================

    def parse_pdf(self, file_path: str) -> str:
        """解析PDF文档"""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            raise Exception(f"PDF解析失败: {str(e)}")

    def split_text(self, text: str) -> List[Dict[str, Any]]:
        """分块文本"""
        chunks = self.text_splitter.split_text(text)

        # 返回带有元数据的分块列表
        chunk_list = []
        for idx, chunk in enumerate(chunks):
            chunk_list.append({
                "index": idx,
                "content": chunk,
                "length": len(chunk)
            })

        return chunk_list

    # ==================== 实体关系抽取 ====================

    def extract_entities_and_relations(self, text: str) -> List[Dict[str, str]]:
        """使用LLM提取实体和关系（三元组）"""

        prompt = f"""你是一个知识图谱专家。请从以下文本中提取实体和关系，以JSON格式输出。

要求：
1. 识别文本中的关键实体（人物、组织、地点、概念等）
2. 识别实体之间的关系
3. 输出格式为JSON数组，每个元素包含：head（头实体）、relation（关系）、tail（尾实体）、entity_type（实体类型）

示例输出格式：
[
  {{"head": "张三", "relation": "任职于", "tail": "阿里巴巴", "head_type": "Person", "tail_type": "Organization"}},
  {{"head": "阿里巴巴", "relation": "位于", "tail": "杭州", "head_type": "Organization", "tail_type": "Location"}}
]

文本内容：
{text}

请直接返回JSON数组，不要有其他文字说明："""

        try:
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的知识图谱构建助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            result_text = response.choices[0].message.content.strip()

            # 解析JSON
            # 尝试提取JSON（有时LLM会返回带代码块的内容）
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            triplets = json.loads(result_text)

            # 验证格式
            if isinstance(triplets, list):
                return triplets
            else:
                return []

        except Exception as e:
            print(f"实体关系抽取失败: {str(e)}")
            return []

    # 请确保这个函数在 class KnowledgeGraphService: 的缩进范围内（通常前面有4个空格）
    async def extract_batch_async(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并发处理多个文本块，但限制最高并发量并增加控速"""
        # 信号量控制并发数
        semaphore = asyncio.Semaphore(8) 

        async def sem_task(chunk):
            async with semaphore:
                loop = asyncio.get_event_loop()
                # 增加延迟防止请求撞车
                await asyncio.sleep(0.5) 
                try:
                    # 在线程池中运行同步的抽取函数
                    result = await loop.run_in_executor(
                        self.executor,
                        self.extract_entities_and_relations,
                        chunk["content"]
                    )
                    return result
                except Exception as e:
                    print(f"抽取块 {chunk['index']} 失败: {e}")
                    return []

        # 创建所有任务
        tasks = [sem_task(chunk) for chunk in chunks]
        
        # 并发等待所有任务完成
        results = await asyncio.gather(*tasks)

        # 整合结果
        all_triplets = []
        for idx, triplets_list in enumerate(results):
            if triplets_list and isinstance(triplets_list, list):
                for triplet in triplets_list:
                    # 记录来源块索引
                    triplet["source_chunk_index"] = chunks[idx]["index"]
                    all_triplets.append(triplet)

        return all_triplets
    # ==================== Neo4j图谱存储 ====================

    def save_triplets_to_neo4j(self, triplets: List[Dict[str, Any]], doc_id: str):
        """将三元组保存到Neo4j"""

        with self.neo4j_driver.session() as session:
            # 创建文档节点
            session.run(
                "MERGE (d:Document {id: $doc_id})",
                doc_id=doc_id
            )

            # 批量创建实体和关系
            for triplet in triplets:
                try:
                    head = triplet.get("head", "")
                    tail = triplet.get("tail", "")
                    relation = triplet.get("relation", "RELATED_TO")
                    head_type = triplet.get("head_type", "Entity")
                    tail_type = triplet.get("tail_type", "Entity")

                    if not head or not tail:
                        continue

                    # 创建头实体
                    session.run(
                        f"MERGE (h:{head_type} {{name: $head}}) "
                        "ON CREATE SET h.created_at = timestamp() "
                        "MERGE (d:Document {id: $doc_id}) "
                        "MERGE (h)-[:FROM_DOCUMENT]->(d)",
                        head=head,
                        doc_id=doc_id
                    )

                    # 创建尾实体
                    session.run(
                        f"MERGE (t:{tail_type} {{name: $tail}}) "
                        "ON CREATE SET t.created_at = timestamp() "
                        "MERGE (d:Document {id: $doc_id}) "
                        "MERGE (t)-[:FROM_DOCUMENT]->(d)",
                        tail=tail,
                        doc_id=doc_id
                    )

                    # 创建关系（动态关系类型）
                    # Neo4j不支持参数化关系类型，需要用字符串拼接（注意安全性）
                    safe_relation = "".join([c if c.isalnum() or c == "_" else "_" for c in relation])
                    session.run(
                        f"MATCH (h {{name: $head}}) "
                        f"MATCH (t {{name: $tail}}) "
                        f"MERGE (h)-[r:{safe_relation}]->(t) "
                        "ON CREATE SET r.created_at = timestamp()",
                        head=head,
                        tail=tail
                    )

                except Exception as e:
                    print(f"保存三元组失败: {triplet}, 错误: {str(e)}")
                    continue

    def get_graph_data(self, doc_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """获取图谱数据（用于前端可视化）"""

        with self.neo4j_driver.session() as session:
            if doc_id:
                # 查询特定文档的图谱
                result = session.run(
                    """
                    MATCH (n)-[r]->(m)
                    WHERE (n)-[:FROM_DOCUMENT]->(:Document {id: $doc_id})
                       OR (m)-[:FROM_DOCUMENT]->(:Document {id: $doc_id})
                    RETURN n, r, m
                    LIMIT $limit
                    """,
                    doc_id=doc_id,
                    limit=limit
                )
            else:
                # 查询所有图谱
                result = session.run(
                    """
                    MATCH (n)-[r]->(m)
                    WHERE NOT type(r) = 'FROM_DOCUMENT'
                    RETURN n, r, m
                    LIMIT $limit
                    """,
                    limit=limit
                )

            nodes = {}
            edges = []

            for record in result:
                n = record["n"]
                r = record["r"]
                m = record["m"]

                # 节点
                if n.element_id not in nodes:
                    nodes[n.element_id] = {
                        "id": n.element_id,
                        "label": n.get("name", "Unknown"),
                        "type": list(n.labels)[0] if n.labels else "Entity"
                    }

                if m.element_id not in nodes:
                    nodes[m.element_id] = {
                        "id": m.element_id,
                        "label": m.get("name", "Unknown"),
                        "type": list(m.labels)[0] if m.labels else "Entity"
                    }

                # 边
                edges.append({
                    "source": n.element_id,
                    "target": m.element_id,
                    "label": r.type
                })

            return {
                "nodes": list(nodes.values()),
                "edges": edges
            }

    # ==================== ChromaDB向量存储 ====================

    def save_chunks_to_chromadb(self, chunks: List[Dict[str, Any]], doc_id: str):
        """将文本块保存到ChromaDB"""

        # 使用OpenAI Embedding API（DeepSeek也支持）
        texts = [chunk["content"] for chunk in chunks]

        # 生成embeddings（批量）
        try:
            embeddings_response = self.embed_client.embeddings.create(
            model=EMBED_MODEL,
            input=texts,
            encoding_format="float" # 对应魔搭的要求
        )

            embeddings = [item.embedding for item in embeddings_response.data]

            # 保存到ChromaDB
            ids = [f"{doc_id}_{chunk['index']}" for chunk in chunks]
            metadatas = [
                {
                    "doc_id": doc_id,
                    "chunk_index": chunk["index"],
                    "length": chunk["length"]
                }
                for chunk in chunks
            ]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

        except Exception as e:
            raise Exception(f"向量存储失败: {str(e)}")

    def search_similar_chunks(self, query: str, n_results: int = None) -> List[Dict[str, Any]]:
        """向量检索相似文本块"""

        if n_results is None:
            n_results = VECTOR_SEARCH_TOP_K

        try:
            # 生成查询向量
            query_embedding_response = self.embed_client.embeddings.create(
            model=EMBED_MODEL,
            input=[query],
            encoding_format="float"
        )

            query_embedding = query_embedding_response.data[0].embedding

            # 检索
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            # 格式化结果
            chunks = []
            if results and results["documents"]:
                for i in range(len(results["documents"][0])):
                    chunks.append({
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })

            return chunks

        except Exception as e:
            print(f"向量检索失败: {str(e)}")
            return []

    def search_graph_neighbors(self, entities: List[str], hops: int = None) -> Dict[str, Any]:
            """图检索：查找实体的邻居节点（已修正变长路径语法错误）"""
            if not entities:
                return {"nodes": [], "edges": []}

            if hops is None:
                hops = GRAPH_SEARCH_HOPS

            with self.neo4j_driver.session() as session:
                # 修正后的查询：使用 relationships(p) 获取路径中的所有关系并过滤
                query = f"""
                MATCH p = (n)-[*1..{hops}]-(m)
                WHERE n.name IN $entities
                AND ALL(rel IN relationships(p) WHERE type(rel) <> 'FROM_DOCUMENT')
                RETURN n, relationships(p) as r_list, m
                LIMIT 50
                """

                result = session.run(query, entities=entities)

                nodes = {}
                edges = []

                for record in result:
                    n = record["n"]
                    m = record["m"]
                    r_list = record["r_list"] # 这是一个关系列表

                    # 1. 处理节点 n
                    if n.element_id not in nodes:
                        nodes[n.element_id] = {
                            "id": str(n.element_id),
                            "label": str(n.get("name", "Unknown")),
                            "type": str(list(n.labels)[0]) if n.labels else "Entity",
                            "highlighted": True
                        }

                    # 2. 处理节点 m
                    if m.element_id not in nodes:
                        nodes[m.element_id] = {
                            "id": str(m.element_id),
                            "label": str(m.get("name", "Unknown")),
                            "type": str(list(m.labels)[0]) if m.labels else "Entity",
                            "highlighted": True
                        }

                    # 3. 处理路径中的所有边 (修正点：变长路径需要循环处理边)
                    for rel in r_list:
                        edge_id = f"{rel.start_node.element_id}-{rel.type}-{rel.end_node.element_id}"
                        # 避免重复添加边
                        if not any(e['id'] == edge_id for e in edges):
                            edges.append({
                                "id": edge_id,
                                "source": str(rel.start_node.element_id),
                                "target": str(rel.end_node.element_id),
                                "label": str(rel.type)
                            })

                return {
                    "nodes": list(nodes.values()),
                    "edges": edges
                }

    def extract_entities_from_question(self, question: str) -> List[str]:
        """从问题中提取实体（用于图检索）"""

        prompt = f"""从以下问题中提取关键实体名称，以JSON数组格式返回。

问题：{question}

只返回实体名称数组，例如：["张三", "阿里巴巴"]

请直接返回JSON数组："""

        try:
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个实体识别助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )

            result_text = response.choices[0].message.content.strip()

            # 解析JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            entities = json.loads(result_text)
            return entities if isinstance(entities, list) else []

        except Exception as e:
            print(f"实体提取失败: {str(e)}")
            return []

    # ==================== RAG问答 ====================

    async def answer_question(self, question: str, stream: bool = False) -> Dict[str, Any]:
        """RAG问答（混合检索 + LLM生成）"""

        # 1. 向量检索
        vector_chunks = self.search_similar_chunks(question, n_results=3)

        # 2. 图检索
        entities = self.extract_entities_from_question(question)
        graph_data = self.search_graph_neighbors(entities, hops=2)

        # 3. 构建上下文
        context_parts = []

        # 向量检索的文本
        if vector_chunks:
            context_parts.append("【相关文档片段】")
            for i, chunk in enumerate(vector_chunks, 1):
                context_parts.append(f"{i}. {chunk['content']}")

        # 图谱检索的三元组
        if graph_data["nodes"]:
            context_parts.append("\n【相关知识图谱】")
            for node in graph_data["nodes"][:10]:
                context_parts.append(f"- {node['label']} ({node['type']})")

        context = "\n".join(context_parts)

        # 4. 生成答案
        prompt = f"""请基于以下上下文回答问题。如果上下文中没有相关信息，请如实说明。

上下文：
{context}

问题：{question}

请提供详细的答案："""

        try:
            if stream:
                # 流式返回
                response = self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个专业的知识问答助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                    stream=True
                )

                return {
                    "stream": response,
                    "sources": {
                        "vector_chunks": vector_chunks,
                        "graph_data": graph_data
                    }
                }
            else:
                # 非流式返回
                response = self.llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个专业的知识问答助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )

                answer = response.choices[0].message.content

                return {
                    "answer": answer,
                    "sources": {
                        "vector_chunks": vector_chunks,
                        "graph_data": graph_data
                    }
                }

        except Exception as e:
            raise Exception(f"答案生成失败: {str(e)}")


# 全局服务实例
kg_service = KnowledgeGraphService()
