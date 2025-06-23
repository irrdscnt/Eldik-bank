# # from channels.generic.websocket import AsyncWebsocketConsumer
# # import json
# # from bson import ObjectId
# # from datetime import datetime, timezone
# # from core.models import DriverLocation, UserLocation,User

# # class LocationConsumer(AsyncWebsocketConsumer):
# #     async def connect(self):
# #         await self.channel_layer.group_add("location_tracking", self.channel_name)
# #         await self.accept()

# #     async def disconnect(self, close_code):
# #         await self.channel_layer.group_discard("location_tracking", self.channel_name)

# #     async def receive(self, text_data):
# #         data = json.loads(text_data)
# #         user_id = data.get("user_id")
# #         role = data.get("role")
# #         coordinates = data.get("coordinates")
# #         location_text = data.get("location_text")

# #         if not all([user_id, role, coordinates]) or len(coordinates) != 2:
# #             return



# #         if role == "driver":
# #             try:
# #                 obj = DriverLocation.objects.get(user=ObjectId(user_id))
# #             except DriverLocation.DoesNotExist:
# #                 obj = DriverLocation(user=ObjectId(user_id))

# #         elif role == "user":
# #             try:
# #                 obj = UserLocation.objects.get(user=ObjectId(user_id))
# #             except UserLocation.DoesNotExist:
# #                 obj = UserLocation(user=ObjectId(user_id))
# #         else:
# #             print("Неизвестная роль:", role)
# #             return

# #         obj.coordinates = [str(c) for c in coordinates]
# #         obj.location_text = location_text
# #         obj.updated_at = datetime.now(timezone.utc)

# #         try:
# #             obj.save()
# #             print(f"Сохранено местоположение для {role} {user_id}")
# #         except Exception as e:
# #             print(f"Ошибка при сохранении локации: {e}")
# #             return

# #         await self.channel_layer.group_send(
# #             "location_tracking",
# #             {
# #                 "type": "broadcast_location",
# #                 "data": {
# #                     "user_id": user_id,
# #                     "role": role,
# #                     "coordinates": obj.coordinates,
# #                     "location_text": location_text,
# #                 }
# #             }
# #         )

# #     async def broadcast_location(self, event):
# #         await self.send(text_data=json.dumps(event["data"]))
# from channels.generic.websocket import AsyncWebsocketConsumer
# import json
# from bson import ObjectId
# from datetime import datetime, timezone
# from core.models import DriverLocation, UserLocation


# class LocationConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         # Получаем user_id и driver_id из query-параметров
#         query_string = self.scope["query_string"].decode()
#         params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
#         self.user_id = params.get("user_id")
#         self.driver_id = params.get("driver_id")
#         self.role = params.get("role")

#         if not self.user_id or not self.driver_id or not self.role:
#             await self.close()
#             return

#         # Группа для пары водитель-юзер
#         self.pair_group = f"pair_{self.user_id}_{self.driver_id}"
#         await self.channel_layer.group_add(self.pair_group, self.channel_name)

#         # Если это диспетчер или водитель — добавляем в глобальную группу
#         if self.role == "dispatcher" or self.role == "driver":
#             await self.channel_layer.group_add("location_tracking", self.channel_name)

#         await self.accept()

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(self.pair_group, self.channel_name)
#         if self.role == "dispatcher" or self.role == "driver":
#             await self.channel_layer.group_discard("location_tracking", self.channel_name)

#     async def receive(self, text_data):
#         data = json.loads(text_data)
#         user_id = data.get("user_id")
#         role = data.get("role")
#         coordinates = data.get("coordinates")
#         location_text = data.get("location_text")

#         if not all([user_id, role, coordinates]) or len(coordinates) != 2:
#             return

#         model = DriverLocation if role == "driver" else UserLocation

#         try:
#             obj = model.objects.get(user=ObjectId(user_id))
#         except model.DoesNotExist:
#             obj = model(user=ObjectId(user_id))

#         obj.coordinates = [str(c) for c in coordinates]
#         obj.location_text = location_text
#         obj.updated_at = datetime.now(timezone.utc)

#         try:
#             obj.save()
#             print(f"Сохранено местоположение для {role} {user_id}")
#         except Exception as e:
#             print(f"Ошибка при сохранении локации: {e}")
#             return

#         payload = {
#             "user_id": user_id,
#             "role": role,
#             "coordinates": obj.coordinates,
#             "location_text": location_text,
#         }

#         # Отправка в свою пару (юзер и водитель друг другу)
#         await self.channel_layer.group_send(
#             self.pair_group,
#             {
#                 "type": "broadcast_location",
#                 "data": payload
#             }
#         )

#         # Отправка диспетчеру — только если это водитель
#         if role == "driver":
#             await self.channel_layer.group_send(
#                 "location_tracking",
#                 {
#                     "type": "broadcast_location",
#                     "data": payload
#                 }
#             )

#     async def broadcast_location(self, event):
#         await self.send(text_data=json.dumps(event["data"]))
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import DriverLocation, UserLocation

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Получаем user_id, driver_id и role из query params
        query_string = self.scope["query_string"].decode()
        params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
        self.user_id = params.get("user_id")
        self.driver_id = params.get("driver_id")
        self.role = params.get("role")

        if not self.user_id or not self.driver_id or not self.role:
            await self.close()
            return

        # Сортируем id, чтобы и водитель и юзер были в одной группе
        ids = sorted([self.user_id, self.driver_id])
        self.pair_group = f"pair_{ids[0]}_{ids[1]}"

        await self.channel_layer.group_add(self.pair_group, self.channel_name)
        print(f"Подключился к группе {self.pair_group} роль: {self.role}")


        # Если диспетчер или водитель — добавляем в глобальную группу
        if self.role in ("dispatcher", "driver"):
            await self.channel_layer.group_add("location_tracking", self.channel_name)
            print(f"Подключился к глобальной группе location_tracking")

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.pair_group, self.channel_name)
        if self.role in ("dispatcher", "driver"):
            await self.channel_layer.group_discard("location_tracking", self.channel_name)
        print(f"Отключился от группы {self.pair_group}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_id = data.get("user_id")
        role = data.get("role")
        coordinates = data.get("coordinates")
        location_text = data.get("location_text")

        if not all([user_id, role, coordinates]) or len(coordinates) != 2:
            print("Неверные данные в receive:", data)
            return

        model = DriverLocation if role == "driver" else UserLocation

        try:
            obj = model.objects.get(user=ObjectId(user_id))
        except model.DoesNotExist:
            obj = model(user=ObjectId(user_id))

        obj.coordinates = [str(c) for c in coordinates]
        obj.location_text = location_text
        obj.updated_at = datetime.now(timezone.utc)

        try:
            obj.save()
            print(f"Сохранено местоположение для {role} {user_id}: {coordinates}")
        except Exception as e:
            print(f"Ошибка при сохранении локации: {e}")
            return

        payload = {
            "user_id": user_id,
            "role": role,
            "coordinates": obj.coordinates,
            "location_text": location_text,
        }

        # Отправляем в общую пару
        await self.channel_layer.group_send(
            self.pair_group,
            {
                "type": "broadcast_location",
                "data": payload
            }
        )
        print(f"Отправлено в группу {self.pair_group}: {payload}")

        # Водитель дополнительно отправляется в глобальную группу диспетчера
        if role == "driver":
            await self.channel_layer.group_send(
                "location_tracking",
                {
                    "type": "broadcast_location",
                    "data": payload
                }
            )
            print(f"Отправлено диспетчеру: {payload}")

    async def broadcast_location(self, event):
        await self.send(text_data=json.dumps(event["data"]))
