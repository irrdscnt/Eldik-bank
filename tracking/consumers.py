from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import DriverLocation, UserLocation
from core_requests.models import Request
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
        self.user_id = params.get("user_id")
        self.role = params.get("role")

        if not self.user_id or not self.role:
            await self.close()
            return

        self.user_object_id = ObjectId(self.user_id)

        try:
            self.pair_user_id, self.pair_driver_id = await self.get_pair_ids(self.user_object_id, self.role)

            if not self.pair_user_id or not self.pair_driver_id:
                await self.close()
                return

            self.other_id = self.pair_driver_id if self.role == "user" else self.pair_user_id

        except Exception as e:
            logger.error(f"❌ Ошибка получения пары: {str(e)}")
            await self.close()
            return

        ids = sorted([self.pair_user_id, self.pair_driver_id])
        self.pair_group = f"pair_{ids[0]}_{ids[1]}"

        await self.channel_layer.group_add(self.pair_group, self.channel_name)
        logger.info(f"✅ Подключился к группе {self.pair_group} как {self.role}")

        if self.role in ("driver", "dispatcher"):
            await self.channel_layer.group_add("location_tracking", self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'pair_group'):
            await self.channel_layer.group_discard(self.pair_group, self.channel_name)
        if self.role in ("driver", "dispatcher"):
            await self.channel_layer.group_discard("location_tracking", self.channel_name)
        logger.info(f"❎ Отключился от группы {getattr(self, 'pair_group', '')}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user_id = data.get("user_id")
            role = data.get("role")
            coordinates = data.get("coordinates")
            location_text = data.get("location_text")

            if not all([user_id, role, coordinates]) or len(coordinates) != 2:
                logger.warning("❗ Неверные данные в receive: %s", data)
                return

            model = DriverLocation if role == "driver" else UserLocation

            await self.save_location(model, ObjectId(user_id), coordinates, location_text)

            payload = {
                "user_id": user_id,
                "role": role,
                "coordinates": coordinates,
                "location_text": location_text,
            }

            await self.channel_layer.group_send(
                self.pair_group,
                {"type": "broadcast_location", "data": payload}
            )

            if role == "driver":
                await self.channel_layer.group_send(
                    "location_tracking",
                    {"type": "broadcast_location", "data": payload}
                )

        except Exception as e:
            logger.error(f"⛔ Ошибка обработки сообщения: {str(e)}")

    async def broadcast_location(self, event):
        try:
            await self.send(text_data=json.dumps(event["data"]))
        except Exception as e:
            logger.error(f"⛔ Ошибка отправки сообщения: {str(e)}")

    @database_sync_to_async
    def get_pair_ids(self, user_id, role):
        try:
            if role == "user":
                req = Request.objects(user=user_id).first()
            elif role == "driver":
                req = Request.objects(driver=user_id).first()
            else:
                return None, None

            if req:
                return str(req.user.id), str(req.driver.id)
            return None, None
        except Exception as e:
            logger.exception("Ошибка в get_pair_ids")
            return None, None

    @database_sync_to_async
    def save_location(self, model, user_id, coordinates, location_text):
        obj = model.objects(user=user_id).first()
        if not obj:
            obj = model(user=user_id)

        if obj.coordinates != coordinates or obj.location_text != location_text:
            obj.coordinates = coordinates
            obj.location_text = location_text
            obj.updated_at = datetime.now(timezone.utc)
            logger.debug(f"📦 Пытаемся сохранить: {coordinates} (тип: {type(coordinates[0])})")

            obj.save()
            logger.info(f"💾 Локация {user_id} обновлена: {coordinates}")
