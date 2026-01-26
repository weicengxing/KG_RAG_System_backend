"""
清理Redis中所有植物大战僵尸房间相关数据
"""
import redis
import sys

def clear_pvz_rooms():
    """删除所有PVZ房间相关的Redis数据"""
    try:
        # 连接到Redis
        r = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            password=None,
            decode_responses=True
        )
        
        # 测试连接
        r.ping()
        print("✅ Redis连接成功\n")
        
        # 查找所有PVZ相关的keys
        patterns = [
            'pvz:room:*',
            'pvz:room_code:*',
            'pvz:user_room:*'
        ]
        
        total_deleted = 0
        deleted_keys = []
        
        for pattern in patterns:
            keys = r.keys(pattern)
            if keys:
                print(f"找到 {len(keys)} 个匹配 '{pattern}' 的 keys:")
                for key in keys:
                    print(f"  - {key}")
                # 批量删除
                deleted = r.delete(*keys)
                total_deleted += deleted
                deleted_keys.extend(keys)
                print(f"✅ 已删除 {deleted} 个 keys\n")
            else:
                print(f"⚠️  没有找到匹配 '{pattern}' 的 keys\n")
        
        # 删除活跃房间索引（ZSET）
        if r.exists('pvz:active_rooms'):
            r.delete('pvz:active_rooms')
            total_deleted += 1
            deleted_keys.append('pvz:active_rooms')
            print("✅ 已删除 pvz:active_rooms\n")
        else:
            print("⚠️  pvz:active_rooms 不存在\n")
        
        print(f"═════════════════════════════════")
        print(f"📊 清理完成！总共删除了 {total_deleted} 个 keys")
        print(f"═════════════════════════════════")
        
        if total_deleted > 0:
            print(f"\n已清理的 keys:")
            for key in deleted_keys:
                print(f"  - {key}")
        
        return True
        
    except redis.ConnectionError:
        print("❌ Redis连接失败，请确认Redis服务是否运行")
        return False
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False

if __name__ == "__main__":
    print("开始清理Redis中的PVZ房间数据...\n")
    print("=" * 50)
    
    success = clear_pvz_rooms()
    
    sys.exit(0 if success else 1)
