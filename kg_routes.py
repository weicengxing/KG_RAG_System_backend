"""
知识图谱RAG系统API路由
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import time
import asyncio
import hashlib
from datetime import datetime
from kg_service import kg_service
from database_asy_mon_re import db_manager

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
        traceback.print_exc()


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
