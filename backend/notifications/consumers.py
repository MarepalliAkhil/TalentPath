from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import redeem_ws_ticket, user_group


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """ws/notifications?ticket=... ; ticket from POST /api/realtime/ticket."""

    group_name = None

    async def connect(self):
        query = parse_qs(self.scope.get("query_string", b"").decode())
        ticket = (query.get("ticket") or [""])[0]
        user_id = await sync_to_async(redeem_ws_ticket)(ticket)
        if not user_id:
            await self.close(code=4401)
            return
        self.group_name = user_group(user_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notify(self, event):
        await self.send_json(event["payload"])
