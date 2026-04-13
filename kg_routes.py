"""
知识图谱RAG系统API路由

支持 Kafka 异步处理 + SSE 实时推送
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import time
import asyncio
import hashlib
import json
from datetime import datetime
from kg_service import kg_service
from database_asy_mon_re import db_manager
from task_manager import task_manager
from confluent_kafka import Producer as KafkaProducer
from auth_deps import get_current_user, get_current_user_from_query

router = APIRouter(prefix="/api/kg", tags=["Knowledge Graph"])

# 文档去重布隆过滤器
try:
    from bloom_utils import is_document_uploaded, is_document_uploaded_with_warmup, mark_document_uploaded
except ImportError:
    # 降级方案：不使用布隆过滤器
    def is_document_uploaded(doc_id): return False
    def is_document_uploaded_with_warmup(doc_id, fallback_to_db=False): return (False, False)
    def mark_document_uploaded(doc_id): pass

# 文档上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 文档元数据保存 ====================

async def save_document_metadata_async(
    doc_id: str,
    file_hash: str,
    filename: str,
    file_extension: str,
    file_size: int,
    file_path: str,
    text_length: int
):
    """
    将文档元数据保存到 MongoDB
    
    Args:
        doc_id: 文档ID (UUID)
        file_hash: 文件MD5 hash
        filename: 文件名
        file_extension: 文件扩展名
        file_size: 文件大小（字节）
        file_path: 文件存储路径
        text_length: 文本长度
    """
    try:
        document_data = {
            "doc_id": doc_id,
            "file_hash": file_hash,
            "filename": filename,
            "file_extension": file_extension,
            "file_size": file_size,
            "file_path": file_path,
            "text_length": text_length,
            "upload_time": datetime.utcnow(),
            "status": "uploaded"
        }
        
        # 保存到MongoDB
        await db_manager.db.documents.insert_one(document_data)
        print(f"[文档] 文档元数据已保存到MongoDB: {doc_id} ({filename})")
    except Exception as e:
        # 记录保存元数据失败错误
        print(f"[错误] 保存文档元数据失败: {e}")
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"保存文档元数据到MongoDB失败: doc_id={doc_id}, error={str(e)}")
        logger.exception(traceback.format_exc())


# ==================== 请求模型 ====================

class QuestionRequest(BaseModel):
    """问答请求模型"""
    question: str
    stream: bool = False
    conversation_id: Optional[str] = None  # 会话ID，用于Redis缓存会话
    model_name: Optional[str] = None  # AI问答模型名称


class GraphQueryRequest(BaseModel):
    """图谱查询请求模型"""
    doc_id: Optional[str] = None
    limit: int = 100


class GraphEditNode(BaseModel):
    id: str
    label: str
    type: Optional[str] = "Entity"
    current_type: Optional[str] = "Entity"


class GraphEditEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    current_label: Optional[str] = None


class GraphEditRequest(BaseModel):
    nodes: List[GraphEditNode] = []
    edges: List[GraphEditEdge] = []


async def save_graph_edits_async(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
    """后台异步写入图谱编辑结果，避免阻塞接口响应。"""
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: kg_service.apply_graph_edits(nodes=nodes, edges=edges)
        )
        print(f"[graph-edit] 图谱编辑异步写入完成: {result}")
    except Exception as e:
        print(f"[graph-edit] 图谱编辑异步写入失败: {e}")
        import traceback
        traceback.print_exc()


# ==================== 文档上传接口 ====================

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """
    上传文档，支持PDF/TXT/DOCX/PPTX
    解析文档内容并提取文本
    """
    # 允许的文件扩展名
    allowed_extensions = {'.pdf', '.txt', '.docx', '.pptx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的文件类型，仅支持PDF/TXT/DOCX/PPTX")

    # 读取文件内容并计算MD5 hash
    try:
        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件读取失败: {str(e)}")

    # 检查文档是否已存在（Warmup方式预热布隆过滤器）
    doc_exists, used_db_fallback = is_document_uploaded_with_warmup(
        file_hash, 
        fallback_to_db=True  # Warmup查询数据库确认
    )
    
    if doc_exists:
        # 从MongoDB查询已存在文档信息
        existing_doc = await db_manager.db.documents.find_one({"file_hash": file_hash})
        
        # 返回已存在文档数据
        existing_doc_data = None
        if existing_doc:
            # 转换ObjectId为字符串
            existing_doc_data = {
                "doc_id": existing_doc.get("doc_id"),
                "filename": existing_doc.get("filename"),
                "file_hash": existing_doc.get("file_hash"),
                "file_extension": existing_doc.get("file_extension"),
                "file_size": existing_doc.get("file_size"),
                "text_length": existing_doc.get("text_length"),
                "upload_time": existing_doc.get("upload_time").isoformat() if existing_doc.get("upload_time") else None,
                "status": existing_doc.get("status", "unknown")
            }
        
        return {
            "error": "文档已存在",
            "duplicate": True,
            "file_hash": file_hash,
            "existing_doc": existing_doc_data,
            "message": "该文档已上传，请勿重复上传"
        }

    # 生成文档ID
    doc_id = str(uuid.uuid4())

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_ext}")
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 标记文档已上传
    mark_document_uploaded(file_hash, force_save=True)

    # 解析文档
    try:
        text = kg_service.parse_document(file_path)
        text_length = len(text)
        if hasattr(kg_service, "pipeline_cache"):
            kg_service.pipeline_cache[doc_id] = {
                "text": text,
                "chunks": None,
                "triplets": None,
                "updated_at": time.time()
            }

        # 异步保存文档元数据到MongoDB
        asyncio.create_task(
            save_document_metadata_async(
                doc_id=doc_id,
                file_hash=file_hash,
                filename=file.filename,
                file_extension=file_ext,
                file_size=len(content),
                file_path=file_path,
                text_length=text_length
            )
        )

        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "text_preview": text[:500],  # 预览前500字符
            "text_length": text_length,
            "file_hash": file_hash,
            "message": "文档上传成功"
        }
    except Exception as e:
        # 清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文档分词 ====================

@router.post("/split-text")
async def split_text(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    """
    文档分词
    将文档内容切分成文本块
    
    Args:
        request: FastAPI 请求对象
        current_user: 当前用户（JWT token验证）
    """
    print(f"[split-text] 收到 分词请求 | 用户: {current_user}")
    
    try:
        # 获取请求Content-Type
        content_type = request.headers.get("content-type", "")
        print(f"[split-text] 收到 Content-Type: {content_type}")
        
        # 读取请求体（最多500字符用于调试）
        body_bytes = await request.body()
        print(f"[split-text] 收到 请求体原始(前500字符): {body_bytes[:500]}")
        
        # 尝试解析JSON
        try:
            body = await request.json()
            print(f"[split-text] 解析JSON成功: {body}")
        except Exception as json_error:
            print(f"[split-text] 解析JSON失败: {json_error}")
            print(f"[split-text] 原始请求体解码: {body_bytes.decode('utf-8', errors='replace')}")
            raise HTTPException(
                status_code=400, 
                detail=f"JSON解析失败: {str(json_error)}"
            )
        
        doc_id = body.get("doc_id")
        print(f"[split-text] 获取 请求参数 doc_id: {doc_id}")
        
        if not doc_id:
            print(f"[split-text] 缺少 doc_id 参数")
            raise HTTPException(status_code=400, detail="缺少doc_id参数")
            
    except HTTPException:
        # 重新抛出HTTPException
        raise
    except Exception as e:
        print(f"[split-text] 解析请求失败: {e}")
        import traceback
        print(f"[split-text] 详细堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"请求解析失败: {str(e)}")
    
    # 查找文档文件
    file_path = None
    for ext in ['.pdf', '.txt', '.docx', '.pptx']:
        path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            file_path = path
            break

    if not file_path:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        # 处理文档
        pipeline_data = await kg_service.process_document_pipeline_async(
            file_path=file_path,
            doc_id=doc_id,
            include_triplets=False
        )
        chunks = pipeline_data["chunks"]

        return {
            "doc_id": doc_id,
            "chunks": chunks,
            "total_chunks": len(chunks),
            "message": "文档分词成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 实体抽取 ====================

@router.post("/extract-entities")
async def extract_entities(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    """
    实体抽取
    从文档中提取知识三元组
    
    Args:
        request: FastAPI 请求对象
        current_user: 当前用户（JWT token验证）
    """
    try:
        body = await request.json()
        doc_id = body.get("doc_id")
        
        if not doc_id:
            raise HTTPException(status_code=400, detail="缺少doc_id参数")
    except Exception as e:
        raise HTTPException(status_code=400, detail="请求解析失败")

    # 查找文档文件
    file_path = None
    for ext in ['.pdf', '.txt', '.docx', '.pptx']:
        path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            file_path = path
            break

    if not file_path:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        # 处理文档
        pipeline_data = await kg_service.process_document_pipeline_async(
            file_path=file_path,
            doc_id=doc_id,
            include_triplets=True
        )
        triplets = pipeline_data["triplets"]

        return {
            "doc_id": doc_id,
            "triplets": triplets,
            "total_triplets": len(triplets),
            "message": "实体抽取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 构建图谱 ====================

@router.post("/build-graph")
async def build_graph(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    """
    构建知识图谱
    1. 解析文档
    2. 文档分词
    3. 实体抽取
    4. 保存到Neo4j
    5. 保存到ChromaDB
    
    Args:
        request: FastAPI 请求对象
        current_user: 当前用户（JWT token验证）
    """
    try:
        body = await request.json()
        doc_id = body.get("doc_id")
        
        if not doc_id:
            raise HTTPException(status_code=400, detail="缺少doc_id参数")
    except Exception as e:
        raise HTTPException(status_code=400, detail="请求解析失败")

    # 查找文档文件
    file_path = None
    for ext in ['.pdf', '.txt', '.docx', '.pptx']:
        path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            file_path = path
            break

    if not file_path:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        start_time = time.time()

        pipeline_data = await kg_service.process_document_pipeline_async(
            file_path=file_path,
            doc_id=doc_id,
            include_triplets=True
        )
        chunks = pipeline_data["chunks"]
        triplets = pipeline_data["triplets"]

        # 4. 保存三元组到Neo4j
        kg_service.save_triplets_to_neo4j(triplets, doc_id)

        # 5. 保存文本块到ChromaDB
        kg_service.save_chunks_to_chromadb(chunks, doc_id)

        elapsed_time = time.time() - start_time

        return {
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "total_triplets": len(triplets),
            "elapsed_time": round(elapsed_time, 2),
            "message": "知识图谱构建成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 获取图谱 ====================

@router.post("/get-graph")
async def get_graph(
    request: GraphQueryRequest,
    current_user: str = Depends(get_current_user)
):
    """
    获取知识图谱数据
    
    Args:
        request: 图谱查询请求模型
        current_user: 当前用户（JWT token验证）
    """
    try:
        graph_data = kg_service.get_graph_data(
            doc_id=request.doc_id,
            limit=request.limit
        )

        return {
            "graph": graph_data,
            "message": "图谱数据获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-graph-edits")
async def save_graph_edits(
    request: GraphEditRequest,
    current_user: str = Depends(get_current_user)
):
    """
    保存问答图谱编辑结果。
    接口立即返回，Neo4j 后台异步写入。
    """
    if not request.nodes and not request.edges:
        raise HTTPException(status_code=400, detail="没有可保存的图谱修改")

    asyncio.create_task(
        save_graph_edits_async(
            nodes=[node.model_dump() for node in request.nodes],
            edges=[edge.model_dump() for edge in request.edges]
        )
    )

    return {
        "message": "图谱修改已提交，正在后台异步保存",
        "accepted": True,
        "node_count": len(request.nodes),
        "edge_count": len(request.edges)
    }


# ==================== RAG问答 ====================

@router.get("/available-models")
async def get_available_models():
    """
    获取可用的AI问答模型列表
    """
    from config import QA_MODELS, DEFAULT_QA_MODEL

    models = []
    for model_config in QA_MODELS:
        models.append({
            "name": model_config["name"],
            "model": model_config["model"],
            "description": model_config.get("description", "")
        })

    return {
        "models": models,
        "default": DEFAULT_QA_MODEL,
        "message": "模型列表获取成功"
    }


@router.post("/ask")
async def ask_question(request: QuestionRequest):
    """
    RAG问答（非流式）
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        result = await kg_service.answer_question(
            question=request.question,
            stream=False,
            model_name=request.model_name
        )

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "message": "问答成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask-stream")
async def ask_question_stream(request: QuestionRequest):
    """
    RAG问答（流式）
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        result = await kg_service.answer_question(
            question=request.question,
            stream=True,
            model_name=request.model_name
        )

        # 流式返回
        async def generate():
            # 先返回来源信息
            import json
            sources_data = json.dumps({
                "type": "sources",
                "data": result["sources"]
            }) + "\n"
            yield sources_data

            # 流式返回答案
            for chunk in result["stream"]:
                if chunk.choices[0].delta.content:
                    answer_data = json.dumps({
                        "type": "answer",
                        "content": chunk.choices[0].delta.content
                    }) + "\n"
                    yield answer_data

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask-parallel-stream")
async def ask_question_parallel_stream(request: QuestionRequest):
    """
    RAG问答（并行流式）
    同时返回：
    1. 向量检索结果 (type: vector_chunks)
    2. 图数据 (type: graph_data)
    3. AI答案 (type: answer)
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        # 并行流式返回答案
        async def generate():
            async for chunk in kg_service.answer_question_parallel_stream(
                request.question,
                conversation_id=request.conversation_id,
                model_name=request.model_name
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文档管理 ====================

@router.delete("/delete-document/{doc_id}")
async def delete_document(doc_id: str):
    """
    删除文档及其相关数据
    """
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")

    # 删除文件
    if os.path.exists(file_path):
        os.remove(file_path)

    # TODO: 清理Neo4j和ChromaDB数据（待实现）

    return {
        "message": "文档删除成功"
    }


@router.get("/list-documents")
async def list_documents():
    """
    列出所有已上传文档
    """
    if not os.path.exists(UPLOAD_DIR):
        return {"documents": []}

    files = os.listdir(UPLOAD_DIR)
    documents = []

    for filename in files:
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.pdf', '.txt', '.docx', '.pptx']:
            doc_id = filename.replace(ext, '')
            file_path = os.path.join(UPLOAD_DIR, filename)
            stat = os.stat(file_path)

            documents.append({
                "doc_id": doc_id,
                "filename": filename,
                "size": stat.st_size,
                "created_at": stat.st_ctime
            })

    return {"documents": documents}


# ==================== ====================

# Kafka 配置
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'kg-api-producer'
}

# 懒加载 Kafka Producer
_kafka_producer = None

def get_kafka_producer():
    """获取 Kafka Producer 实例"""
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = KafkaProducer(KAFKA_CONFIG)
    return _kafka_producer


# ==================== Kafka + SSE 异步上传 ====================

@router.post("/upload-async")
async def upload_document_async(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """
    异步上传文档（Kafka + SSE）
    
    流程：
    1. 读取文档内容
    2. 发送到 Kafka
    3. 生成 task_id
    4. 返回 SSE 链接用于推送进度
    
    返回：
    - task_id: 任务ID，用于SSE推送
    - sse_url: SSE推送链接
    """
    # 允许的文件扩展名
    allowed_extensions = {'.pdf', '.txt', '.docx', '.pptx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的文件类型，仅支持PDF/TXT/DOCX/PPTX")

    # 读取文件内容并计算MD5 hash
    try:
        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件读取失败: {str(e)}")

    # 检查文档是否已存在
    doc_exists, _ = is_document_uploaded_with_warmup(file_hash, fallback_to_db=True)
    
    if doc_exists:
        return {
            "error": "文档已存在",
            "duplicate": True,
            "file_hash": file_hash,
            "message": "该文档已上传，请勿重复上传"
        }

    # 生成任务ID和文档ID
    task_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_ext}")
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 标记文档已上传
    mark_document_uploaded(file_hash, force_save=True)

    # 创建任务记录
    task_info = task_manager.create_task(task_id, current_user, "kb_build")

    # 发送到 Kafka
    producer = get_kafka_producer()
    kafka_message = {
        "task_id": task_id,
        "doc_id": doc_id,
        "user_id": current_user,
        "filename": file.filename,
        "file_path": file_path,
        "file_size": len(content),
        "file_hash": file_hash,
        "created_at": time.time()
    }

    try:
        producer.produce(
            'doc-upload',
            key=task_id.encode('utf-8'),
            value=json.dumps(kafka_message).encode('utf-8'),
            callback=lambda msg, err: None
        )
        producer.flush()
    except Exception as e:
        # Kafka发送失败，清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        task_manager.fail_task(task_id, f"Kafka发送失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kafka发送失败: {str(e)}")

    # 异步保存元数据（不阻塞主流程）
    async def safe_save_metadata():
        try:
            await save_document_metadata_async(
                doc_id=doc_id,
                file_hash=file_hash,
                filename=file.filename,
                file_extension=file_ext,
                file_size=len(content),
                file_path=file_path,
                text_length=0  # 异步处理，初始为0
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"异步保存文档元数据失败: {str(e)}")
    
    asyncio.create_task(safe_save_metadata())

    return {
        "task_id": task_id,
        "doc_id": doc_id,
        "filename": file.filename,
        "status": "processing",
        "message": "文档上传成功，异步处理中...",
        "sse_url": f"/api/kg/task/stream/{task_id}",
        "poll_url": f"/api/kg/task/{task_id}"
    }


@router.get("/task/stream/{task_id}")
async def stream_task_progress(
    task_id: str,
    current_user: str = Depends(get_current_user_from_query)  # 从URL query获取token
):
    """
    SSE 实时推送任务进度
    
    Args:
        task_id: 任务ID
    
    Returns:
        StreamingResponse: SSE 流
    """
    async def event_generator():
        """SSE 事件生成器"""
        last_progress = -1
        
        while True:
            try:
                # 从Redis获取任务状态
                task_info = task_manager.get_task_status(task_id)
                
                if task_info is None:
                    # 任务不存在
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务不存在'})}\n\n"
                    break
                
                status = task_info.get("status")
                progress = task_info.get("progress", 0)
                stage = task_info.get("stage", "")
                message = task_info.get("message", "")
                
                # 进度变化或完成/失败时推送
                if progress != last_progress or status in ["completed", "failed"]:
                    
                    if status == "processing":
                        payload = {
                            "type": "progress",
                            "progress": progress,
                            "stage": stage,
                            "message": message or "处理中..."
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    
                    elif status == "completed":
                        # 任务完成，返回结果
                        result = task_info.get("result", {})
                        payload = {
                            "type": "completed",
                            "progress": 100,
                            "stage": "completed",
                            "data": result
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        break
                    
                    elif status == "failed":
                        # 任务失败，返回错误信息
                        error_msg = task_info.get("error_message", "未知错误")
                        payload = {
                            "type": "error",
                            "message": error_msg
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        break
                    
                    last_progress = progress
                
                # 超时检查（2小时）
                elapsed = time.time() - task_info.get("created_at", time.time())
                if elapsed > 7200:
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务超时'})}\n\n"
                    break
                
                # 每秒轮询
                await asyncio.sleep(1)
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'SSE错误: {str(e)}'})}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/task/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """
    获取任务状态（轮询接口）
    
    Args:
        task_id: 任务ID
    
    Returns:
        任务状态信息
    """
    task_info = task_manager.get_task_status(task_id)
    
    if task_info is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 返回任务状态信息
    return {
        "task_id": task_info.get("task_id"),
        "status": task_info.get("status"),
        "progress": task_info.get("progress", 0),
        "stage": task_info.get("stage", ""),
        "message": task_info.get("message", ""),
        "created_at": task_info.get("created_at"),
        "updated_at": task_info.get("updated_at"),
        "result": task_info.get("result") if task_info.get("status") == "completed" else None,
        "error_message": task_info.get("error_message") if task_info.get("status") == "failed" else None
    }
