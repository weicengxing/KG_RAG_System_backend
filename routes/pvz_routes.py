"""
植物大战僵尸游戏存档API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
from schemas.pvz_schemas import GameStateSave, GameStateResponse, GameStatsData, UpdateGameStatsRequest, GameStatsResponse
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
import json
from datetime import datetime, timedelta
import logging
from auth_deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# MongoDB连接
MONGO_URI = "mongodb://localhost:27017"
mongo_client = AsyncIOMotorClient(MONGO_URI)


@router.post("/pvz/save", response_model=GameStateResponse)
async def save_game(
    game_state: GameStateSave,
    current_user: str = Depends(get_current_user)
):
    """
    保存游戏状态
    先保存到Redis（快速访问），再保存到MongoDB（持久化）
    """
    save_key = f"pvz_save:{current_user}"
    
    try:
        # 创建Redis连接
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 保存到Redis（设置7天过期）
        await redis_client.setex(
            save_key,
            timedelta(days=7),
            json.dumps(game_state.dict())
        )
        
        # 保存到MongoDB
        db = mongo_client["chat_app_db"]
        collection = db["pvz_saves"]
        
        save_doc = {
            "user_id": current_user,
            "game_state": game_state.dict(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # 更新或插入
        await collection.update_one(
            {"user_id": current_user},
            {"$set": save_doc},
            upsert=True
        )
        
        # 关闭Redis连接
        await redis_client.close()
        
        logger.info(f"游戏保存成功: user_id={current_user}")
        return GameStateResponse(
            success=True,
            message="游戏保存成功",
            data=game_state
        )
    except Exception as e:
        logger.error(f"保存游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/pvz/load", response_model=GameStateResponse)
async def load_game(current_user: str = Depends(get_current_user)):
    """
    加载游戏状态
    优先从Redis加载，如果Redis没有则从MongoDB加载
    """
    save_key = f"pvz_save:{current_user}"
    
    try:
        # 创建Redis连接
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 先尝试从Redis加载
        redis_data = await redis_client.get(save_key)
        if redis_data:
            game_state = json.loads(redis_data)
            await redis_client.close()
            logger.info(f"从Redis加载游戏: user_id={current_user}")
            return GameStateResponse(
                success=True,
                message="存档加载成功（来自Redis）",
                data=GameStateSave(**game_state)
            )
        
        # Redis没有，从MongoDB加载
        db = mongo_client["chat_app_db"]
        collection = db["pvz_saves"]
        
        save_doc = await collection.find_one({"user_id": current_user})
        if save_doc:
            game_state = save_doc["game_state"]
            
            # 同时回写到Redis
            await redis_client.setex(
                save_key,
                timedelta(days=7),
                json.dumps(game_state)
            )
            
            await redis_client.close()
            logger.info(f"从MongoDB加载游戏: user_id={current_user}")
            return GameStateResponse(
                success=True,
                message="存档加载成功（来自MongoDB）",
                data=GameStateSave(**game_state)
            )
        
        await redis_client.close()
        logger.info(f"未找到存档: user_id={current_user}")
        return GameStateResponse(
            success=False,
            message="未找到存档"
        )
    except Exception as e:
        logger.error(f"加载游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")


@router.post("/pvz/update-stats", response_model=GameStatsResponse)
async def update_game_stats(
    stats_request: UpdateGameStatsRequest,
    current_user: str = Depends(get_current_user)
):
    """
    更新游戏统计数据
    先保存到Redis（快速访问），再保存到MongoDB（持久化）
    """
    stats_key = f"pvz_stats:{current_user}"
    
    try:
        # 创建Redis连接
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 从Redis获取现有统计或创建新统计
        redis_stats = await redis_client.get(stats_key)
        if redis_stats:
            current_stats = json.loads(redis_stats)
        else:
            current_stats = {
                "highScore": 0,
                "totalKills": 0,
                "totalWaves": 0
            }
        
        # 更新统计数据
        current_stats["totalKills"] = current_stats.get("totalKills", 0) + stats_request.kills
        current_stats["totalWaves"] = current_stats.get("totalWaves", 0) + stats_request.waves
        
        # 更新最高分
        if stats_request.score > current_stats.get("highScore", 0):
            current_stats["highScore"] = stats_request.score
        
        # 保存到Redis（设置30天过期）
        await redis_client.setex(
            stats_key,
            timedelta(days=30),
            json.dumps(current_stats)
        )
        
        # 保存到MongoDB
        db = mongo_client["chat_app_db"]
        collection = db["pvz_stats"]
        
        stats_doc = {
            "user_id": current_user,
            "stats": current_stats,
            "updated_at": datetime.utcnow()
        }
        
        await collection.update_one(
            {"user_id": current_user},
            {"$set": stats_doc},
            upsert=True
        )
        
        await redis_client.close()
        
        logger.info(f"游戏统计更新成功: user_id={current_user}, stats={current_stats}")
        return GameStatsResponse(
            success=True,
            message="统计数据更新成功",
            data=GameStatsData(**current_stats)
        )
    except Exception as e:
        logger.error(f"更新游戏统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.get("/pvz/get-stats", response_model=GameStatsResponse)
async def get_game_stats(current_user: str = Depends(get_current_user)):
    """
    获取游戏统计数据
    优先从Redis加载，如果Redis没有则从MongoDB加载
    """
    stats_key = f"pvz_stats:{current_user}"
    
    try:
        # 创建Redis连接
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 先尝试从Redis加载
        redis_stats = await redis_client.get(stats_key)
        if redis_stats:
            stats = json.loads(redis_stats)
            await redis_client.close()
            logger.info(f"从Redis获取游戏统计: user_id={current_user}")
            return GameStatsResponse(
                success=True,
                message="统计数据获取成功（来自Redis）",
                data=GameStatsData(**stats)
            )
        
        # Redis没有，从MongoDB加载
        db = mongo_client["chat_app_db"]
        collection = db["pvz_stats"]
        
        stats_doc = await collection.find_one({"user_id": current_user})
        if stats_doc:
            stats = stats_doc["stats"]
            
            # 同时回写到Redis
            await redis_client.setex(
                stats_key,
                timedelta(days=30),
                json.dumps(stats)
            )
            
            await redis_client.close()
            logger.info(f"从MongoDB获取游戏统计: user_id={current_user}")
            return GameStatsResponse(
                success=True,
                message="统计数据获取成功（来自MongoDB）",
                data=GameStatsData(**stats)
            )
        
        await redis_client.close()
        
        # 没有统计数据，返回默认值
        default_stats = GameStatsData()
        logger.info(f"未找到统计数据: user_id={current_user}, 返回默认值")
        return GameStatsResponse(
            success=True,
            message="未找到统计数据，返回默认值",
            data=default_stats
        )
    except Exception as e:
        logger.error(f"获取游戏统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
