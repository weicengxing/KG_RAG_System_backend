"""
删除Elasticsearch中的music_songs索引
"""
from elasticsearch_utils import es_manager

try:
    result = es_manager.client.indices.delete(index='music_songs')
    print(f"✅ 成功删除索引: {result}")
except Exception as e:
    if "index_not_found_exception" in str(e):
        print("⚠️ 索引不存在，无需删除")
    else:
        print(f"❌ 删除索引失败: {e}")