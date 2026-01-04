"""
知识图谱RAG系统API路由
支持 Kafka 异步处理 + SSE 实时进度推送
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
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

# 导入布隆过滤器工具函数
try:
    from bloom_utils import is_document_uploaded, is_document_uploaded_with_warmup, mark_document_uploaded
except ImportError:
    # 如果导入失败，使用空函数
    def is_document_uploaded(doc_id): return False
    def is_document_uploaded_with_warmup(doc_id, fallback_to_db=False): return (False, False)
    def mark_document_uploaded(doc_id): pass

# 文档上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 辅助函数 ====================

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
    异步保存文档元数据到 MongoDB
    
    Args:
        doc_id: 文档ID (UUID)
        file_hash: 文件MD5 hash
        filename: 原始文件名
        file_extension: 文件扩展名
        file_size: 文件大小（字节）
        file_path: 文件保存路径
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
        
        # 异步插入到 MongoDB
        await db_manager.db.documents.insert_one(document_data)
        print(f"✅ 文档元数据已保存到MongoDB: {doc_id} ({filename})")
    except Exception as e:
        # 如果保存失败，记录错误但不影响主流程
        print(f"❌ 保存文档元数据失败: {e}")
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"保存文档元数据到MongoDB失败: doc_id={doc_id}, error={str(e)}")
        logger.exception(traceback.format_exc())


# ==================== 请求/响应模型 ====================

class QuestionRequest(BaseModel):
    """问答请求"""
    question: str
    stream: bool = False
    conversation_id: Optional[str] = None  # 对话ID，用于从Redis获取对话历史
    model_name: Optional[str] = None  # AI问答模型名称


class GraphQueryRequest(BaseModel):
    """图谱查询请求"""
    doc_id: Optional[str] = None
    limit: int = 100


# ==================== 文档上传与处理 ====================

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """
    上传文档（PDF/TXT/DOCX/PPTX）
    返回：文档ID和文本内容
    使用布隆过滤器防止重复上传
    """
    # 验证文件类型
    allowed_extensions = {'.pdf', '.txt', '.docx', '.pptx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="只支持 PDF、TXT、DOCX、PPTX 文件")

    # 读取文件内容并计算 MD5 hash
    try:
        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件读取失败: {str(e)}")

    # 使用布隆过滤器快速检查（支持Warmup降级）
    doc_exists, used_db_fallback = is_document_uploaded_with_warmup(
        file_hash, 
        fallback_to_db=True  # Warmup未完成时降级到MongoDB查询
    )
    
    if doc_exists:
        # 如果使用了降级查询，说明已经从MongoDB确认了存在
        # 如果没有使用降级，说明布隆过滤器确认存在（可能有误判，但这是可接受的）
        return {
            "error": "文档已存在",
            "duplicate": True,
            "file_hash": file_hash,
            "message": "该文档已上传过，请勿重复上传"
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

    # 标记文档已上传（添加到布隆过滤器，使用 force_save=True 立即保存）
    mark_document_uploaded(file_hash, force_save=True)

    # 解析文档
    try:
        text = kg_service.parse_document(file_path)
        text_length = len(text)

        # 异步保存文档元数据到MongoDB（不阻塞主流程）
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


# ==================== 文本分块 ====================

@router.post("/split-text")
async def split_text(doc_id: str):
    """
    文本分块
    返回：分块列表
    """
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
        # 解析文档
        text = kg_service.parse_document(file_path)

        # 分块
        chunks = kg_service.split_text(text)

        return {
            "doc_id": doc_id,
            "chunks": chunks,
            "total_chunks": len(chunks),
            "message": "文本分块完成"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 实体关系抽取 ====================

@router.post("/extract-entities")
async def extract_entities(doc_id: str):
    """
    实体关系抽取（使用LLM）
    返回：三元组列表（流式返回每个块的处理结果）
    """
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
        # 解析和分块
        text = kg_service.parse_document(file_path)
        chunks = kg_service.split_text(text)

        # 并发抽取实体关系
        triplets = await kg_service.extract_batch_async(chunks)

        return {
            "doc_id": doc_id,
            "triplets": triplets,
            "total_triplets": len(triplets),
            "message": "实体关系抽取完成"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱构建 ====================

@router.post("/build-graph")
async def build_graph(doc_id: str):
    """
    构建知识图谱（完整流程）
    1. 解析文档
    2. 文本分块
    3. 实体关系抽取
    4. 保存到Neo4j
    5. 保存到ChromaDB（向量存储）
    """
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

        # 1. 解析文档
        text = kg_service.parse_document(file_path)

        # 2. 文本分块
        chunks = kg_service.split_text(text)

        # 3. 并发抽取实体关系
        triplets = await kg_service.extract_batch_async(chunks)

        # 4. 保存到Neo4j
        kg_service.save_triplets_to_neo4j(triplets, doc_id)

        # 5. 保存到ChromaDB
        kg_service.save_chunks_to_chromadb(chunks, doc_id)

        elapsed_time = time.time() - start_time

        return {
            "doc_id": doc_id,
            "total_chunks": len(chunks),
            "total_triplets": len(triplets),
            "elapsed_time": round(elapsed_time, 2),
            "message": "知识图谱构建完成"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 图谱查询 ====================

@router.post("/get-graph")
async def get_graph(request: GraphQueryRequest):
    """
    获取图谱数据（用于前端可视化）
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
            "description": model_config.get("description", "")  # 添加描述字段
        })

    return {
        "models": models,
        "default": DEFAULT_QA_MODEL,
        "message": "获取模型列表成功"
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
            "message": "问答完成"
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

        # 流式生成
        async def generate():
            # 首先返回溯源信息
            import json
            sources_data = json.dumps({
                "type": "sources",
                "data": result["sources"]
            }) + "\n"
            yield sources_data

            # 然后流式返回答案
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
    三个部分并行处理并流式返回：
    1. 向量检索结果 (type: vector_chunks)
    2. 图检索结果 (type: graph_data)
    3. AI答案 (type: answer, 流式)
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        # 使用新的并行流式方法，传递对话ID和模型名称
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


# ==================== 管理接口 ====================

@router.delete("/delete-document/{doc_id}")
async def delete_document(doc_id: str):
    """
    删除文档及其相关数据
    """
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")

    # 删除文件
    if os.path.exists(file_path):
        os.remove(file_path)

    # TODO: 从Neo4j和ChromaDB中删除相关数据
    # 这里需要实现清理逻辑

    return {
        "message": "文档删除成功"
    }


@router.get("/list-documents")
async def list_documents():
    """
    列出所有已上传的文档
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

# 全局 Kafka Producer (延迟初始化)
_kafka_producer = None

def get_kafka_producer():
    """获取 Kafka Producer 实例"""
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = KafkaProducer(KAFKA_CONFIG)
    return _kafka_producer


# ==================== 异步文档处理（Kafka + SSE）====================

@router.post("/upload-async")
async def upload_document_async(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """
    异步上传文档（使用 Kafka 处理 + SSE 推送进度）
    
    流程：
    1. 保存文件到本地
    2. 发送任务到 Kafka
    3. 立即返回 task_id
    4. 前端通过 SSE 监听处理进度
    
    返回：
    - task_id: 任务ID，用于 SSE 监听
    - sse_url: SSE 连接地址
    """
    # 验证文件类型
    allowed_extensions = {'.pdf', '.txt', '.docx', '.pptx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="只支持 PDF、TXT、DOCX、PPTX 文件")

    # 读取文件内容
    try:
        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件读取失败: {str(e)}")

    # 使用布隆过滤器检查重复
    doc_exists, _ = is_document_uploaded_with_warmup(file_hash, fallback_to_db=True)
    
    if doc_exists:
        return {
            "error": "文档已存在",
            "duplicate": True,
            "file_hash": file_hash,
            "message": "该文档已上传过，请勿重复上传"
        }

    # 生成任务 ID
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
            callback=lambda msg, err: None  # 可以添加回调处理发送结果
        )
        producer.flush()  # 等待消息发送完成
    except Exception as e:
        # Kafka 发送失败，删除文件并报错
        if os.path.exists(file_path):
            os.remove(file_path)
        task_manager.fail_task(task_id, f"Kafka 发送失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kafka 发送失败: {str(e)}")

    # 异步保存文档元数据（添加错误处理）
    async def safe_save_metadata():
        try:
            await save_document_metadata_async(
                doc_id=doc_id,
                file_hash=file_hash,
                filename=file.filename,
                file_extension=file_ext,
                file_size=len(content),
                file_path=file_path,
                text_length=0  # 初始为 0，处理后会更新
            )
        except Exception as e:
            # 这里可以记录到日志系统，但不应抛出异常影响主流程
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"异步保存文档元数据失败: {str(e)}")
    
    asyncio.create_task(safe_save_metadata())

    return {
        "task_id": task_id,
        "doc_id": doc_id,
        "filename": file.filename,
        "status": "processing",
        "message": "文档已上传，正在后台处理中...",
        "sse_url": f"/api/kg/task/stream/{task_id}",
        "poll_url": f"/api/kg/task/{task_id}"
    }


@router.get("/task/stream/{task_id}")
async def stream_task_progress(
    task_id: str,
    current_user: str = Depends(get_current_user_from_query)  # 从 URL query 参数获取 token
):
    """
    SSE 流式接口：实时推送任务处理进度
    
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
                # 从 Redis 获取任务状态
                task_info = task_manager.get_task_status(task_id)
                
                if task_info is None:
                    # 任务不存在，可能已过期
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务不存在或已过期'})}\n\n"
                    break
                
                status = task_info.get("status")
                progress = task_info.get("progress", 0)
                stage = task_info.get("stage", "")
                message = task_info.get("message", "")
                
                # 只有进度变化或状态变化时才推送
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
                        # 任务完成，推送完整结果
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
                        # 任务失败，推送错误信息
                        error_msg = task_info.get("error_message", "未知错误")
                        payload = {
                            "type": "error",
                            "message": error_msg
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        break
                    
                    last_progress = progress
                
                # 检查任务是否超时（2 小时）
                elapsed = time.time() - task_info.get("created_at", time.time())
                if elapsed > 7200:
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务超时'})}\n\n"
                    break
                
                # 等待 1 秒后再次检查
                await asyncio.sleep(1)
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'SSE 错误: {str(e)}'})}\n\n"
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
    轮询接口：获取任务状态（用于 SSE 不可用时的降级方案）
    
    Args:
        task_id: 任务ID
    
    Returns:
        任务状态信息
    """
    task_info = task_manager.get_task_status(task_id)
    
    if task_info is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    
    # 返回去敏感信息的任务数据
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
