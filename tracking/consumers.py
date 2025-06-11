from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import DriverLocation, UserLocation,User

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("location_tracking", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("location_tracking", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_id = data.get("user_id")
        role = data.get("role")
        coordinates = data.get("coordinates")
        location_text = data.get("location_text")

        if not all([user_id, role, coordinates]) or len(coordinates) != 2:
            return



        if role == "driver":
            try:
                obj = DriverLocation.objects.get(user=ObjectId(user_id))
            except DriverLocation.DoesNotExist:
                obj = DriverLocation(user=ObjectId(user_id))

        elif role == "user":
            try:
                obj = UserLocation.objects.get(user=ObjectId(user_id))
            except UserLocation.DoesNotExist:
                obj = UserLocation(user=ObjectId(user_id))
        else:
            print("Неизвестная роль:", role)
            return

        obj.coordinates = [str(c) for c in coordinates]
        obj.location_text = location_text
        obj.updated_at = datetime.now(timezone.utc)

        try:
            obj.save()
            print(f"Сохранено местоположение для {role} {user_id}")
        except Exception as e:
            print(f"Ошибка при сохранении локации: {e}")
            return

        await self.channel_layer.group_send(
            "location_tracking",
            {
                "type": "broadcast_location",
                "data": {
                    "user_id": user_id,
                    "role": role,
                    "coordinates": obj.coordinates,
                    "location_text": location_text,
                }
            }
        )

    async def broadcast_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))
