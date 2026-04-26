"""
植物大战僵尸多人对战API和WebSocket路由（简化版）
无服务器权威校验，直接转发客户端请求
"""

from fastapi import APIRouter, WebSocket, Depends, HTTPException, Query
from starlette.websockets import WebSocketDisconnect
from services.room_service import simple_room_manager
from websocket.pvz_websocket import ws_manager
from schemas.pvz_schemas import RoomJoin, SimpleSuccessResponse, StartGameRequest
from auth_deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== HTTP API 路由 ====================

@router.post("/pvz/multiplayer/create-room", response_model=SimpleSuccessResponse)
async def create_room_api(current_user: str = Depends(get_current_user)):
    """创建房间"""
    user_id = current_user
    username = current_user
    
    room_state, message = await simple_room_manager.create_room(user_id, username)
    if room_state:
        # 广播房间列表更新给所有大厅用户
        active_rooms = await simple_room_manager.get_active_rooms()
        await ws_manager.broadcast_to_lobby("event.room_list_update", {
            "rooms": active_rooms,
            "message": f"用户 {username} 创建了新房间"
        })
        # 立即返回最新数据，确保格式一致
        return SimpleSuccessResponse(success=True, message=message, data=room_state)
    raise HTTPException(status_code=400, detail=message)


@router.post("/pvz/multiplayer/join-room", response_model=SimpleSuccessResponse)
async def join_room_api(room_join_req: RoomJoin, current_user: str = Depends(get_current_user)):
    """加入房间"""
    user_id = current_user
    username = current_user
    
    room_state, message = await simple_room_manager.join_room(
        room_join_req.room_code, user_id, username
    )
    if room_state:
        # 通知房间内的其他玩家（包括房主）
        await ws_manager.broadcast_to_room(
            room_state["room_id"],
            "event.player_joined",
            {
                "user_id": user_id,
                "username": username,
                "room_id": room_state["room_id"]
            }
        )
        
        # 广播房间列表更新给所有大厅用户
        active_rooms = await simple_room_manager.get_active_rooms()
        if room_state.get("status") == "ready":
            await ws_manager.broadcast_to_lobby("event.room_list_update", {
                "rooms": active_rooms,
                "message": f"房间 {room_state['room_code']} 已准备就绪"
            })
        else:
            await ws_manager.broadcast_to_lobby("event.room_list_update", {
                "rooms": active_rooms,
                "message": f"玩家 {username} 加入了房间 {room_state['room_code']}"
            })
        
        # 确保返回完整房间信息
        return SimpleSuccessResponse(success=True, message=message, data=room_state)
    raise HTTPException(status_code=400, detail=message)


@router.post("/pvz/multiplayer/leave-room", response_model=SimpleSuccessResponse)
async def leave_room_api(current_user: str = Depends(get_current_user)):
    """离开房间"""
    user_id = current_user
    
    # 在离开之前获取用户的房间信息
    room = await simple_room_manager.get_user_room(user_id)
    if not room:
        raise HTTPException(status_code=400, detail="未加入任何房间")
    
    is_host = (room["plant_player"] == user_id)
    room_id = room["room_id"]
    zombie_username = room.get("zombie_player_username", "")
    zombie_user_id = room.get("zombie_player", "")
    
    success, message = await simple_room_manager.leave_room(user_id)
    
    if success:
        # 广播房间列表更新给所有大厅用户
        active_rooms = await simple_room_manager.get_active_rooms()
        await ws_manager.broadcast_to_lobby("event.room_list_update", {
            "rooms": active_rooms,
            "message": "房间列表已更新"
        })
        
        if is_host:
            # 房主离开，通知所有玩家房间被销毁
            await ws_manager.broadcast_to_room(
                room_id,
                "event.room_destroyed",
                {
                    "room_id": room_id,
                    "message": "房主已离开，房间已关闭"
                }
            )
        else:
            # 普通玩家离开，通知房主（排除自己）
            if room.get("plant_player"):
                await ws_manager.send_to_user(
                    room_id,
                    room["plant_player"],
                    "event.player_left",
                    {
                        "user_id": user_id,
                        "username": zombie_username,
                        "room_id": room_id
                    }
                )
        
        return SimpleSuccessResponse(success=True, message=message)
    
    raise HTTPException(status_code=400, detail="离开房间失败")


@router.get("/pvz/multiplayer/active-rooms", response_model=SimpleSuccessResponse)
async def get_active_rooms_api():
    """获取活跃房间列表"""
    rooms = await simple_room_manager.get_active_rooms()
    return SimpleSuccessResponse(success=True, message="获取成功", data=rooms)


@router.get("/pvz/multiplayer/my-room", response_model=SimpleSuccessResponse)
async def get_my_room_api(current_user: str = Depends(get_current_user)):
    """获取我的房间信息"""
    user_id = current_user
    room = await simple_room_manager.get_user_room(user_id)
    
    if room:
        return SimpleSuccessResponse(success=True, message="获取成功", data=room)
    return SimpleSuccessResponse(success=True, message="未加入任何房间", data=None)


@router.post("/pvz/multiplayer/start-game", response_model=SimpleSuccessResponse)
async def start_game_api(start_game_req: StartGameRequest, current_user: str = Depends(get_current_user)):
    """开始游戏"""
    user_id = current_user
    room_id = start_game_req.room_id
    
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id required")
    
    room = await simple_room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    if room["plant_player"] != user_id:
        raise HTTPException(status_code=403, detail="只有植物玩家可以开始游戏")
    
    if room["status"] != "ready":
        raise HTTPException(status_code=400, detail="房间未准备就绪")
    
    # 更新房间状态为游戏中
    await simple_room_manager.update_room_status(room_id, "playing")
    
    logger.info(f"游戏开始: {room_id} by {user_id}")
    
    # 广播游戏开始事件，包括房主自己
    await ws_manager.broadcast_to_room(room_id, "event.game_start", {
        "room_id": room_id,
        "message": "游戏开始！"
    })
    
    return SimpleSuccessResponse(success=True, message="游戏开始", data={"room_id": room_id, "status": "playing"})


# ==================== WebSocket 路由 ====================

@router.websocket("/ws/pvz/lobby")
async def pvz_lobby_websocket(
    websocket: WebSocket,
    user_id: str = Query(..., alias="user_id")
):
    """植物大战僵尸大厅WebSocket连接 - 用于监听房间列表变化"""
    try:
        # 建立大厅WebSocket连接
        await ws_manager.connect_lobby(websocket, user_id)
        logger.info(f"大厅WebSocket连接建立: 用户 {user_id}")
        
        # 发送当前房间列表给客户端
        active_rooms = await simple_room_manager.get_active_rooms()
        await ws_manager.send_to_lobby_user(user_id, "event.room_list_update", {
            "rooms": active_rooms,
            "message": "欢迎来到游戏大厅"
        })
        
        # 消息处理循环
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            payload = data.get("payload", {})
            
            logger.info(f"大厅收到消息: {message_type} from {user_id}")
            
            # 大厅主要用于监听，可以处理一些简单的心跳消息
            if message_type == "ping":
                await ws_manager.send_to_lobby_user(user_id, "pong", {
                    "timestamp": payload.get("timestamp")
                })
            elif message_type == "refresh_rooms":
                # 客户端主动请求刷新房间列表
                active_rooms = await simple_room_manager.get_active_rooms()
                await ws_manager.send_to_lobby_user(user_id, "event.room_list_update", {
                    "rooms": active_rooms,
                    "message": "房间列表已更新"
                })
            else:
                # 未知消息类型，忽略
                pass
                
    except WebSocketDisconnect:
        # 用户断开连接
        ws_manager.disconnect_lobby(user_id)
        logger.info(f"大厅WebSocket断开: 用户 {user_id}")
    
    except Exception as e:
        logger.error(f"大厅WebSocket错误 (用户 {user_id}): {e}", exc_info=True)
        ws_manager.disconnect_lobby(user_id)


@router.websocket("/ws/pvz/room/{room_id}")
async def pvz_websocket(
    websocket: WebSocket,
    room_id: str,
    user_id: str = Query(..., alias="user_id")  # 简化版：直接从query获取user_id
):
    """植物大战僵尸多人对战WebSocket连接"""
    try:
        # 验证用户是否在房间中
        room = await simple_room_manager.get_room(room_id)
        if not room:
            await websocket.close(code=4004, reason="Room not found")
            return
        
        # 检查用户是否是房间的玩家
        is_plant = (room["plant_player"] == user_id)
        is_zombie = (room["zombie_player"] == user_id)
        
        if not (is_plant or is_zombie):
            await websocket.close(code=4003, reason="Not a player in this room")
            return
        
        # 确定用户角色
        role = "plant" if is_plant else "zombie"
        
        # 建立WebSocket连接
        await ws_manager.connect(websocket, room_id, user_id)
        logger.info(f"WebSocket连接建立: 用户 {user_id} 加入房间 {room_id} 角色: {role}")
        
        # 发送初始状态给连接的客户端
        await ws_manager.send_to_user(room_id, user_id, "event.connected", {
            "room_id": room_id,
            "user_id": user_id,
            "role": role,
            "room_status": room["status"],
            "message": f"已连接到房间，你的角色是: {role}"
        })
        
        # 如果房间状态是playing，发送当前游戏状态（如果有）
        if room["status"] == "playing" and room.get("game_state"):
            await ws_manager.send_to_user(room_id, user_id, "state.snapshot", {
                "room_id": room_id,
                "game_state": room["game_state"]
            })
        
        # 消息处理循环
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            payload = data.get("payload", {})
            
            logger.info(f"收到消息: {message_type} from {user_id} in room {room_id}")
            
            # 简化版：直接转发所有游戏相关消息
            # 游戏消息类型包括：plant_action, zombie_action, game_state_update等
            
            if message_type == "plant_selection_complete":
                # 植物选择完成
                selected_plants = payload.get("selected_plants", [])
                await ws_manager.handle_plant_selection(room_id, user_id, selected_plants)
                
            elif message_type == "zombie_selection_complete":
                # 僵尸选择完成
                selected_zombies = payload.get("selected_zombies", [])
                await ws_manager.handle_zombie_selection(room_id, user_id, selected_zombies)
                
            elif message_type.startswith("plant_") and role == "plant":
                # 植物玩家的操作，转发给僵尸玩家
                await ws_manager.broadcast_to_others(room_id, user_id, message_type, payload)
                
            elif message_type.startswith("zombie_") and role == "zombie":
                # 僵尸玩家的操作，转发给植物玩家
                await ws_manager.broadcast_to_others(room_id, user_id, message_type, payload)
                
            elif message_type == "game_state_update":
                # 游戏状态更新，广播给所有玩家
                await ws_manager.broadcast_to_room(room_id, "state.sync", payload)
                
                # 同时保存到Redis
                await simple_room_manager.update_room_state(room_id, payload)
                
            elif message_type == "plant_state_delta" and role == "plant":
                await ws_manager.broadcast_to_others(room_id, user_id, "plant_state_delta", payload)

            elif message_type == "ping":
                # 心跳包，回复pong
                await ws_manager.send_to_user(room_id, user_id, "pong", {
                    "timestamp": payload.get("timestamp")
                })
                
            elif message_type == "game_over":
                # 游戏结束，广播给所有玩家
                await ws_manager.broadcast_to_room(room_id, "event.game_over", {
                    "room_id": room_id,
                    "winner": payload.get("winner"),
                    "reason": payload.get("reason")
                })
                
                # 更新房间状态
                await simple_room_manager.update_room_status(room_id, "finished")
                
            else:
                logger.warning(f"未知的消息类型: {message_type}")
                
    except WebSocketDisconnect:
        # 玩家断开连接
        ws_manager.disconnect(room_id, user_id)
        logger.info(f"用户 {user_id} 断开WebSocket连接")
        
        # 检查是否还有其他玩家在房间
        if ws_manager.get_room_connections_count(room_id) > 0:
            # 通知房间内的其他玩家
            await ws_manager.broadcast_to_room(room_id, "event.player_disconnected", {
                "user_id": user_id,
                "message": f"玩家 {user_id} 已断开连接"
            })
    
    except Exception as e:
        logger.error(f"WebSocket错误 (用户 {user_id} 房间 {room_id}): {e}", exc_info=True)
        ws_manager.disconnect(room_id, user_id)
