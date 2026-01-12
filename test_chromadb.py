#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试ChromaDB向量保存功能"""

import sys
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """测试所有依赖导入"""
    print("=" * 60)
    print("测试1: 检查依赖导入")
    print("=" * 60)
    
    try:
        import chromadb
        print(f"✅ ChromaDB version: {chromadb.__version__}")
    except Exception as e:
        print(f"❌ ChromaDB导入失败: {e}")
        return False
    
    try:
        import onnxruntime
        print(f"✅ ONNX Runtime version: {onnxruntime.__version__}")
    except Exception as e:
        print(f"❌ ONNX Runtime导入失败: {e}")
        return False
    
    try:
        import chromadb.api
        print("✅ ChromaDB API导入成功")
    except Exception as e:
        print(f"❌ ChromaDB API导入失败: {e}")
        return False
    
    print()
    return True

def test_chromadb_client():
    """测试ChromaDB客户端创建"""
    print("=" * 60)
    print("测试2: 创建ChromaDB客户端")
    print("=" * 60)
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        # 创建临时目录
        chroma_data_dir = os.path.join(os.path.dirname(__file__), "test_chroma_data")
        os.makedirs(chroma_data_dir, exist_ok=True)
        
        # 创建客户端
        client = chromadb.PersistentClient(
            path=chroma_data_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        print(f"✅ ChromaDB PersistentClient创建成功")
        print(f"   路径: {chroma_data_dir}")
        
        # 创建集合
        collection = client.get_or_create_collection(
            name="test_collection",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"✅ 集合创建成功: {collection.name}")
        
        return client, collection
    except Exception as e:
        print(f"❌ 创建ChromaDB客户端失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_vector_operations(client, collection):
    """测试向量操作"""
    print("=" * 60)
    print("测试3: 测试向量增删改查")
    print("=" * 60)
    
    try:
        # 准备测试数据
        ids = ["doc1", "doc2", "doc3"]
        embeddings = [
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
            [3.0, 4.0, 5.0]
        ]
        documents = ["这是第一个测试文档", "这是第二个测试文档", "这是第三个测试文档"]
        metadatas = [
            {"source": "test", "index": 0},
            {"source": "test", "index": 1},
            {"source": "test", "index": 2}
        ]
        
        # 添加数据
        print("添加向量数据...")
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        print(f"✅ 成功添加 {len(ids)} 条向量数据")
        
        # 查询数据
        print("查询向量数据...")
        results = collection.query(
            query_embeddings=[[1.5, 2.5, 3.5]],
            n_results=2
        )
        print(f"✅ 查询成功，返回 {len(results['ids'][0])} 条结果")
        
        # 统计
        count = collection.count()
        print(f"✅ 集合中总共有 {count} 条数据")
        
        return True
    except Exception as e:
        print(f"❌ 向量操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("ChromaDB 功能测试")
    print("=" * 60 + "\n")
    
    # 测试1: 导入检查
    if not test_imports():
        print("\n❌ 依赖导入测试失败！")
        sys.exit(1)
    
    # 测试2: 客户端创建
    client, collection = test_chromadb_client()
    if client is None or collection is None:
        print("\n❌ 客户端创建失败！")
        sys.exit(1)
    
    # 测试3: 向量操作
    if not test_vector_operations(client, collection):
        print("\n❌ 向量操作测试失败！")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()