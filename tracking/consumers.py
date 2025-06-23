from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import DriverLocation, UserLocation,User
from core_requests.models import Request   

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

# class LocationConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         # Получаем user_id, driver_id и role из query params
#         query_string = self.scope["query_string"].decode()
#         params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
#         self.user_id = params.get("user_id")
#         self.driver_id = params.get("driver_id")
#         self.role = params.get("role")

#         if not self.user_id or not self.driver_id or not self.role:
#             await self.close()
#             return

#         # Сортируем id, чтобы и водитель и юзер были в одной группе
#         ids = sorted([self.user_id, self.driver_id])
#         self.pair_group = f"pair_{ids[0]}_{ids[1]}"

#         await self.channel_layer.group_add(self.pair_group, self.channel_name)
#         print(f"Подключился к группе {self.pair_group} роль: {self.role}")


#         # Если диспетчер или водитель — добавляем в глобальную группу
#         if self.role in ("dispatcher", "driver"):
#             await self.channel_layer.group_add("location_tracking", self.channel_name)
#             print(f"Подключился к глобальной группе location_tracking")

#         await self.accept()

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(self.pair_group, self.channel_name)
#         if self.role in ("dispatcher", "driver"):
#             await self.channel_layer.group_discard("location_tracking", self.channel_name)
#         print(f"Отключился от группы {self.pair_group}")

#     async def receive(self, text_data):
#         data = json.loads(text_data)
#         user_id = data.get("user_id")
#         role = data.get("role")
#         coordinates = data.get("coordinates")
#         location_text = data.get("location_text")

#         if not all([user_id, role, coordinates]) or len(coordinates) != 2:
#             print("Неверные данные в receive:", data)
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
#             print(f"Сохранено местоположение для {role} {user_id}: {coordinates}")
#         except Exception as e:
#             print(f"Ошибка при сохранении локации: {e}")
#             return

#         payload = {
#             "user_id": user_id,
#             "role": role,
#             "coordinates": obj.coordinates,
#             "location_text": location_text,
#         }

#         # Отправляем в общую пару
#         await self.channel_layer.group_send(
#             self.pair_group,
#             {
#                 "type": "broadcast_location",
#                 "data": payload
#             }
#         )
#         print(f"Отправлено в группу {self.pair_group}: {payload}")

#         # Водитель дополнительно отправляется в глобальную группу диспетчера
#         if role == "driver":
#             await self.channel_layer.group_send(
#                 "location_tracking",
#                 {
#                     "type": "broadcast_location",
#                     "data": payload
#                 }
#             )
#             print(f"Отправлено диспетчеру: {payload}")

#     async def broadcast_location(self, event):
#         await self.send(text_data=json.dumps(event["data"]))

# import requests
# from asgiref.sync import sync_to_async
# class LocationConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         query_string = self.scope["query_string"].decode()
#         params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
#         self.user_id = params.get("user_id")
#         self.role = params.get("role")

#         if not self.user_id or not self.role:
#             await self.close()
#             return

#         try:
#             # Получаем пару (user_id и driver_id) через API
#             response = await sync_to_async(requests.get)(
#                 f"http://127.0.0.1:8000/api/get-pair/?user_id={self.user_id}&role={self.role}"
#             )
#             pair_data = response.json()
            
#             self.pair_user_id = pair_data["user_id"]
#             self.pair_driver_id = pair_data["driver_id"]
            
#             # Определяем ID пары в зависимости от текущей роли
#             if self.role == "user":
#                 self.other_id = self.pair_driver_id
#             elif self.role == "driver":
#                 self.other_id = self.pair_user_id
#             else:
#                 await self.close()
#                 return

#         except Exception as e:
#             print(f"❌ Ошибка получения пары: {str(e)}")
#             await self.close()
#             return

#         # Создаем группу для пары
#         ids = sorted([self.pair_user_id, self.pair_driver_id])
#         self.pair_group = f"pair_{ids[0]}_{ids[1]}"

#         await self.channel_layer.group_add(self.pair_group, self.channel_name)
#         print(f"✅ Подключился к группе {self.pair_group} как {self.role}")

#         # Драйверы и диспетчеры подключаются к общей группе
#         if self.role in ("driver", "dispatcher"):
#             await self.channel_layer.group_add("location_tracking", self.channel_name)

#         await self.accept()

#     async def disconnect(self, close_code):
#         if hasattr(self, 'pair_group'):
#             await self.channel_layer.group_discard(self.pair_group, self.channel_name)
#         if self.role in ("driver", "dispatcher"):
#             await self.channel_layer.group_discard("location_tracking", self.channel_name)
#         print(f"❎ Отключился от группы {self.pair_group if hasattr(self, 'pair_group') else ''}")

#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)
#             user_id = data.get("user_id")
#             role = data.get("role")
#             coordinates = data.get("coordinates")
#             location_text = data.get("location_text")

#             if not all([user_id, role, coordinates]) or len(coordinates) != 2:
#                 print("❗ Неверные данные в receive:", data)
#                 return

#             # Сохраняем локацию
#             model = DriverLocation if role == "driver" else UserLocation
            
#             obj, created = await sync_to_async(model.objects.update_or_create)(
#                 user=ObjectId(user_id),
#                 defaults={
#                     'coordinates': [str(c) for c in coordinates],
#                     'location_text': location_text,
#                     'updated_at': datetime.now(timezone.utc)
#                 }
#             )
            
#             print(f"💾 {'Создана' if created else 'Обновлена'} локация для {role} {user_id}: {coordinates}")

#             payload = {
#                 "user_id": user_id,
#                 "role": role,
#                 "coordinates": coordinates,
#                 "location_text": location_text,
#             }

#             # Отправка в пару
#             await self.channel_layer.group_send(
#                 self.pair_group,
#                 {
#                     "type": "broadcast_location",
#                     "data": payload
#                 }
#             )

#             # Дополнительная отправка для драйверов
#             if role == "driver":
#                 await self.channel_layer.group_send(
#                     "location_tracking",
#                     {
#                         "type": "broadcast_location",
#                         "data": payload
#                     }
#                 )

#         except Exception as e:
#             print(f"⛔ Ошибка обработки сообщения: {str(e)}")

#     async def broadcast_location(self, event):
#         try:
#             await self.send(text_data=json.dumps(event["data"]))
#         except Exception as e:
#             print(f"⛔ Ошибка отправки сообщения: {str(e)}")

import requests
from asgiref.sync import sync_to_async
class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
        self.user_id = params.get("user_id")
        self.role = params.get("role")

        if not self.user_id or not self.role:
            await self.close()
            return

        try:
            # Получаем пару user/driver через API
            response = await sync_to_async(requests.get)(
                f"http://127.0.0.1:8000/api/get-pair/?user_id={self.user_id}&role={self.role}"
            )
            pair_data = response.json()

            self.pair_user_id = pair_data["user_id"]
            self.pair_driver_id = pair_data["driver_id"]

            if self.role == "user":
                self.other_id = self.pair_driver_id
            elif self.role == "driver":
                self.other_id = self.pair_user_id
            else:
                await self.close()
                return

        except Exception as e:
            print(f"❌ Ошибка получения пары: {str(e)}")
            await self.close()
            return

        # Создаём группу для пары
        ids = sorted([self.pair_user_id, self.pair_driver_id])
        self.pair_group = f"pair_{ids[0]}_{ids[1]}"

        await self.channel_layer.group_add(self.pair_group, self.channel_name)
        print(f"✅ Подключился к группе {self.pair_group} как {self.role}")

        if self.role in ("driver", "dispatcher"):
            await self.channel_layer.group_add("location_tracking", self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'pair_group'):
            await self.channel_layer.group_discard(self.pair_group, self.channel_name)
        if self.role in ("driver", "dispatcher"):
            await self.channel_layer.group_discard("location_tracking", self.channel_name)
        print(f"❎ Отключился от группы {getattr(self, 'pair_group', '')}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user_id = data.get("user_id")
            role = data.get("role")
            coordinates = data.get("coordinates")
            location_text = data.get("location_text")

            if not all([user_id, role, coordinates]) or len(coordinates) != 2:
                print("❗ Неверные данные в receive:", data)
                return

            # Выбираем модель по роли
            model = DriverLocation if role == "driver" else UserLocation

            def save_location_sync(model, user_id, coordinates, location_text):
                obj = model.objects(user=ObjectId(user_id)).first()
                if not obj:
                    obj = model(user=ObjectId(user_id))
                obj.coordinates = [str(c) for c in coordinates]
                obj.location_text = location_text
                obj.updated_at = datetime.now(timezone.utc)
                obj.save()

            await sync_to_async(save_location_sync)(model, user_id, coordinates, location_text)

            print(f"💾 Локация для {role} {user_id} сохранена: {coordinates}")

            payload = {
                "user_id": user_id,
                "role": role,
                "coordinates": coordinates,
                "location_text": location_text,
            }

            # Отправка в WebSocket-пару
            await self.channel_layer.group_send(
                self.pair_group,
                {
                    "type": "broadcast_location",
                    "data": payload
                }
            )

            if role == "driver":
                await self.channel_layer.group_send(
                    "location_tracking",
                    {
                        "type": "broadcast_location",
                        "data": payload
                    }
                )

        except Exception as e:
            print(f"⛔ Ошибка обработки сообщения: {str(e)}")

    async def broadcast_location(self, event):
        try:
            await self.send(text_data=json.dumps(event["data"]))
        except Exception as e:
            print(f"⛔ Ошибка отправки сообщения: {str(e)}")