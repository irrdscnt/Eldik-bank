from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import Car_user, Location, DriverLocation, UserLocation

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
        lat = data.get("lat")
        lng = data.get("lng")
        location_text = data.get("location_text") 

        if not all([user_id, role, lat, lng]):
            return

        if role == "driver":
            try:
                # car_user = Car_user.objects.get(user=ObjectId(user_id))
                # loc = Location(latitude=lat, longitude=lng)
                # car_user.location_history.append(loc)
                # car_user.save()

                obj = DriverLocation.objects.get(user=ObjectId(user_id))
                created = False
            except DriverLocation.DoesNotExist:
                obj = DriverLocation(user=ObjectId(user_id))
                created = True

            obj.latitude = lat
            obj.longitude = lng
            obj.location_text = location_text
            obj.updated_at = datetime.now(timezone.utc)
            obj.save()

        elif role == "user":
            try:
                obj = UserLocation.objects.get(user=ObjectId(user_id))
                created = False
            except UserLocation.DoesNotExist:
                obj = UserLocation(user=ObjectId(user_id))
                created = True

            obj.latitude = lat
            obj.longitude = lng
            obj.location_text = location_text
            obj.updated_at = datetime.now(timezone.utc)
            obj.save()
        print("Отправляем клиентам:", {
            "user_id": user_id,
            "role": role,
            "lat": lat,
            "lng": lng,
            "location_text": location_text,
        })
        await self.channel_layer.group_send(
            "location_tracking",
            {
                "type": "broadcast_location",
                "data": {
                    "user_id": user_id,
                    "role": role,
                    "lat": lat,
                    "lng": lng,
                    "location_text": location_text, 
                }
            }
        )

    async def broadcast_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))
