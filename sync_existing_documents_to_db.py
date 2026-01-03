"""
将upload文件夹中现有文档的元数据同步到MongoDB
包括：doc_id, file_hash (MD5), filename, file_extension, file_size, file_path
"""

import os
import hashlib
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import sys

# 导入配置
from config import MONGO_URI, MONGO_DB_NAME

# 上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")

# 支持的文件类型
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.pptx'}


async def calculate_md5(file_path: str) -> str:
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            # 分块读取大文件，避免内存问题
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"❌ 计算MD5失败 {file_path}: {e}")
        return None


async def get_document_info(file_path: str) -> dict:
    """
    获取文档的元数据信息
    
    Returns:
        dict: 包含文档信息的字典，失败返回None
    """
    try:
        # 从文件名提取doc_id
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        doc_id = filename.replace(file_ext, "")
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 计算MD5哈希
        file_hash = await calculate_md5(file_path)
        if not file_hash:
            return None
        
        # 获取文件创建时间
        file_stat = os.stat(file_path)
        
        return {
            "doc_id": doc_id,
            "file_hash": file_hash,
            "filename": filename,
            "file_extension": file_ext,
            "file_size": file_size,
            "file_path": file_path,
            "upload_time": datetime.fromtimestamp(file_stat.st_ctime),
            "status": "existing",
            "synced_at": datetime.utcnow()
        }
    except Exception as e:
        print(f"❌ 获取文档信息失败 {file_path}: {e}")
        return None


async def sync_documents_to_mongodb():
    """将upload文件夹的文档同步到MongoDB"""
    
    # 连接MongoDB
    print("🔗 连接MongoDB...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    
    # 确保索引存在
    print("📊 创建索引...")
    await db.documents.create_index([("file_hash", 1)], unique=True)
    await db.documents.create_index([("doc_id", 1)], unique=True)
    await db.documents.create_index([("upload_time", -1)])
    await db.documents.create_index([("file_extension", 1)])
    
    # 获取所有文档文件
    print(f"\n📁 扫描upload文件夹: {UPLOAD_DIR}")
    if not os.path.exists(UPLOAD_DIR):
        print("❌ upload文件夹不存在！")
        return
    
    files = os.listdir(UPLOAD_DIR)
    document_files = [
        f for f in files
        if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    ]
    
    if not document_files:
        print("❌ 没有找到任何文档文件！")
        return
    
    print(f"✅ 找到 {len(document_files)} 个文档文件")
    
    # 同步计数器
    success_count = 0
    skip_count = 0
    error_count = 0
    
    # 遍历所有文档
    print("\n🚀 开始同步...\n")
    
    for idx, filename in enumerate(document_files, 1):
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        print(f"[{idx}/{len(document_files)}] 处理: {filename}")
        
        # 获取文档信息
        doc_info = await get_document_info(file_path)
        
        if not doc_info:
            print(f"  ⚠️  跳过：无法获取文档信息")
            skip_count += 1
            continue
        
        # 检查是否已存在（基于doc_id）
        existing = await db.documents.find_one({
            "doc_id": doc_info["doc_id"]
        })
        
        if existing:
            print(f"  ⏭️  跳过：文档已存在 (doc_id: {doc_info['doc_id']})")
            skip_count += 1
            continue
        
        # 检查是否已存在（基于file_hash）
        existing_hash = await db.documents.find_one({
            "file_hash": doc_info["file_hash"]
        })
        
        if existing_hash:
            print(f"  ⏭️  跳过：相同文档已存在 (MD5: {doc_info['file_hash']})")
            skip_count += 1
            continue
        
        # 插入到MongoDB
        try:
            result = await db.documents.insert_one(doc_info)
            print(f"  ✅ 成功: {doc_info['doc_id']} (MD5: {doc_info['file_hash'][:16]}...)")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            error_count += 1
    
    # 关闭连接
    client.close()
    
    # 输出统计信息
    print("\n" + "="*60)
    print("📊 同步完成！")
    print("="*60)
    print(f"总文档数: {len(document_files)}")
    print(f"✅ 成功同步: {success_count}")
    print(f"⏭️  跳过(已存在): {skip_count}")
    print(f"❌ 失败: {error_count}")
    print("="*60)


if __name__ == "__main__":
    print("="*60)
    print("📚 现有文档同步到MongoDB工具")
    print("="*60)
    print()
    
    # 运行异步函数
    asyncio.run(sync_documents_to_mongodb())
