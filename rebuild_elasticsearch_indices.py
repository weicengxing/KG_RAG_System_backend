"""
重建 Elasticsearch 索引脚本
删除所有现有索引（music_songs 和 logs），使用新的 IK 分词器配置重新创建
"""
from elasticsearch_utils import es_manager, ES_INDEX_MUSIC, ES_INDEX_LOGS

def delete_all_indices():
    """删除所有索引"""
    print("=" * 60)
    print("开始删除 Elasticsearch 索引")
    print("=" * 60)
    
    indices_to_delete = [ES_INDEX_MUSIC, ES_INDEX_LOGS]
    deleted_count = 0
    
    for index_name in indices_to_delete:
        try:
            if es_manager.client.indices.exists(index=index_name):
                result = es_manager.client.indices.delete(index=index_name)
                print(f"✅ 成功删除索引: {index_name}")
                deleted_count += 1
            else:
                print(f"⚠️ 索引不存在: {index_name} (跳过)")
        except Exception as e:
            print(f"❌ 删除索引失败 {index_name}: {e}")
    
    print(f"\n共删除 {deleted_count} 个索引")
    print("=" * 60)
    return deleted_count

def create_all_indices():
    """创建所有索引"""
    print("\n" + "=" * 60)
    print("开始创建 Elasticsearch 索引（使用 IK 分词器）")
    print("=" * 60)
    
    success_count = 0
    
    # 创建日志索引
    if es_manager._init_logs_index():
        print(f"✅ 日志索引创建成功")
        success_count += 1
    else:
        print(f"❌ 日志索引创建失败")
    
    # 创建音乐索引
    if es_manager._init_music_index():
        print(f"✅ 音乐索引创建成功")
        success_count += 1
    else:
        print(f"❌ 音乐索引创建失败")
    
    print(f"\n共创建 {success_count} 个索引")
    print("=" * 60)
    return success_count

def verify_indices():
    """验证索引配置"""
    print("\n" + "=" * 60)
    print("验证索引配置")
    print("=" * 60)
    
    for index_name in [ES_INDEX_MUSIC, ES_INDEX_LOGS]:
        try:
            if es_manager.client.indices.exists(index=index_name):
                # 获取索引映射
                mapping = es_manager.client.indices.get_mapping(index=index_name)
                print(f"\n📋 索引: {index_name}")
                print(f"   状态: ✅ 存在")
                
                # 检查分词器配置
                properties = mapping[index_name]['mappings']['properties']
                ik_fields = []
                
                for field_name, field_config in properties.items():
                    if 'analyzer' in field_config:
                        analyzer = field_config['analyzer']
                        if 'ik' in analyzer:
                            ik_fields.append(f"{field_name}({analyzer})")
                
                if ik_fields:
                    print(f"   IK 分词器字段: {', '.join(ik_fields)}")
                else:
                    print(f"   ⚠️ 警告: 未发现使用 IK 分词器的字段")
                    
            else:
                print(f"\n❌ 索引不存在: {index_name}")
        except Exception as e:
            print(f"\n❌ 验证索引失败 {index_name}: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    print("\n🚀 Elasticsearch 索引重建脚本")
    print("此脚本将删除现有索引并使用 IK 分词器重新创建\n")
    
    # 确认操作
    response = input("⚠️ 警告: 此操作将删除所有现有索引数据！确认继续吗？(yes/no): ")
    if response.lower() != 'yes':
        print("❌ 操作已取消")
        exit(0)
    
    try:
        # 步骤 1: 删除所有索引
        deleted = delete_all_indices()
        
        # 步骤 2: 创建所有索引
        created = create_all_indices()
        
        # 步骤 3: 验证索引配置
        verify_indices()
        
        # 总结
        print("\n" + "=" * 60)
        print("📊 操作总结")
        print("=" * 60)
        print(f"删除索引数: {deleted}")
        print(f"创建索引数: {created}")
        
        if deleted > 0 and created > 0:
            print("\n✅ 索引重建成功！")
            print("\n下一步:")
            print("1. 运行 sync_music_to_es.py 重新同步音乐数据")
            print("2. 测试搜索功能，验证 IK 分词器是否正常工作")
        else:
            print("\n⚠️ 索引重建未完全成功，请检查日志")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 执行过程中发生错误: {e}")
        print("请检查 Elasticsearch 服务是否正常运行")