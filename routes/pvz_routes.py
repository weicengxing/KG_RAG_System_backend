"""
植物大战僵尸游戏存档API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
from schemas.pvz_schemas import GameStateSave, GameStateResponse
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# MongoDB连接
MONGO_URI = "mongodb://localhost:27017"
mongo_client = AsyncIOMotorClient(MONGO_URI)


@router.post("/pvz/save", response_model=GameStateResponse)
async def save_game(game_state: GameStateSave, user_id: str = "default"):
    """
    保存游戏状态
    先保存到Redis（快速访问），再保存到MongoDB（持久化）
    """
    save_key = f"pvz_save:{user_id}"
    
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
            "user_id": user_id,
            "game_state": game_state.dict(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # 更新或插入
        await collection.update_one(
            {"user_id": user_id},
            {"$set": save_doc},
            upsert=True
        )
        
        # 关闭Redis连接
        await redis_client.close()
        
        logger.info(f"游戏保存成功: user_id={user_id}")
        return GameStateResponse(
            success=True,
            message="游戏保存成功",
            data=game_state
        )
    except Exception as e:
        logger.error(f"保存游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/pvz/load/{user_id}", response_model=GameStateResponse)
async def load_game(user_id: str = "default"):
    """
    加载游戏状态
    优先从Redis加载，如果Redis没有则从MongoDB加载
    """
    save_key = f"pvz_save:{user_id}"
    
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
            logger.info(f"从Redis加载游戏: user_id={user_id}")
            return GameStateResponse(
                success=True,
                message="存档加载成功（来自Redis）",
                data=GameStateSave(**game_state)
            )
        
        # Redis没有，从MongoDB加载
        db = mongo_client["chat_app_db"]
        collection = db["pvz_saves"]
        
        save_doc = await collection.find_one({"user_id": user_id})
        if save_doc:
            game_state = save_doc["game_state"]
            
            # 同时回写到Redis
            await redis_client.setex(
                save_key,
                timedelta(days=7),
                json.dumps(game_state)
            )
            
            await redis_client.close()
            logger.info(f"从MongoDB加载游戏: user_id={user_id}")
            return GameStateResponse(
                success=True,
                message="存档加载成功（来自MongoDB）",
                data=GameStateSave(**game_state)
            )
        
        await redis_client.close()
        logger.info(f"未找到存档: user_id={user_id}")
        return GameStateResponse(
            success=False,
            message="未找到存档"
        )
    except Exception as e:
        logger.error(f"加载游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")
