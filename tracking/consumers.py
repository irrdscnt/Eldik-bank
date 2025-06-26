from channels.generic.websocket import AsyncWebsocketConsumer
import json
from bson import ObjectId
from datetime import datetime, timezone
from core.models import DriverLocation, UserLocation
from core_requests.models import Request
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
import logging
from authorization.models import User

logger = logging.getLogger(__name__)

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        params = dict(q.split("=") for q in query_string.split("&") if "=" in q)
        self.user_id = params.get("user_id")
        self.role = params.get("role")

        logger.info(f"CONNECT request: user_id={self.user_id}, role={self.role}, channel={self.channel_name}")

        if self.role == "dispetcher":
            await self.channel_layer.group_add("location_tracking", self.channel_name)
            await self.accept()
            logger.info(f"Dispatcher connected, added to group 'location_tracking', channel: {self.channel_name}")

            all_drivers = await self.get_all_drivers_status()
            logger.info(f"Sending initial driver locations to dispatcher, count={len(all_drivers)}")

            for driver_data in all_drivers:
                if driver_data["coordinates"]:
                    await self.send(text_data=json.dumps({
                        "user_id": driver_data["user_id"],
                        "role": "driver",
                        "coordinates": driver_data["coordinates"],
                        "location_text": driver_data["location_text"],
                        "busy": driver_data["busy"],
                        "name": driver_data["name"]
                    }))
                    logger.debug(f"Sent driver location to dispatcher: {driver_data['user_id']}")

            return

        if not self.user_id or not self.role:
            logger.warning("CONNECT failed: missing user_id or role")
            await self.close()
            return

        self.user_object_id = ObjectId(self.user_id)

        # 🚕 Обработка водителя
        if self.role == "driver":
            self.pair_user_id, self.pair_driver_id = await self.get_pair_ids(self.user_object_id, self.role)
            logger.info(f"Driver {self.user_id} pair ids: user={self.pair_user_id}, driver={self.pair_driver_id}")

            if self.pair_user_id and self.pair_driver_id:
                ids = sorted([self.pair_user_id, self.pair_driver_id])
                self.pair_group = f"pair_{ids[0]}_{ids[1]}"
                await self.channel_layer.group_add(self.pair_group, self.channel_name)
                logger.info(f"Driver {self.user_id} joined pair group {self.pair_group}")
            else:
                logger.info(f"Driver {self.user_id} has no pair, connecting without pair group")

            await self.channel_layer.group_add("location_tracking", self.channel_name)
            logger.info(f"Driver {self.user_id} added to 'location_tracking' group")
            await self.accept()
            return

        # 👤 Обработка пользователя
        if self.role == "user":
            self.pair_user_id, self.pair_driver_id = await self.get_pair_ids(self.user_object_id, self.role)
            logger.info(f"User {self.user_id} pair ids: user={self.pair_user_id}, driver={self.pair_driver_id}")

            if not self.pair_user_id or not self.pair_driver_id:
                logger.warning(f"User {self.user_id} has no active pair, connection closed")
                await self.close()
                return

            ids = sorted([self.pair_user_id, self.pair_driver_id])
            self.pair_group = f"pair_{ids[0]}_{ids[1]}"
            await self.channel_layer.group_add(self.pair_group, self.channel_name)
            logger.info(f"User {self.user_id} joined pair group {self.pair_group}")
            await self.accept()
            return

        logger.warning(f"CONNECT failed: unknown role '{self.role}'")
        await self.close()

    async def disconnect(self, close_code):
        logger.info(f"DISCONNECT: user_id={self.user_id}, role={self.role}, code={close_code}")
        if hasattr(self, "pair_group"):
            await self.channel_layer.group_discard(self.pair_group, self.channel_name)
            logger.info(f"Removed from pair group {self.pair_group}")
        if self.role in ("driver", "dispetcher"):
            await self.channel_layer.group_discard("location_tracking", self.channel_name)
            logger.info(f"Removed from 'location_tracking' group")
        logger.info(f"Client disconnected: {self.user_id} role: {self.role}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user_id = data.get("user_id")
            role = data.get("role")
            coordinates = data.get("coordinates")
            location_text = data.get("location_text")

            logger.debug(f"RECEIVE data: user_id={user_id}, role={role}, coordinates={coordinates}")

            if not all([user_id, role, coordinates]) or len(coordinates) != 2:
                logger.warning(f"Invalid data received: {data}")
                return

            model = DriverLocation if role == "driver" else UserLocation
            await self.save_location(model, ObjectId(user_id), coordinates, location_text)

            busy = False
            name = ""

            user = await self.get_user(ObjectId(user_id))
            if user:
                name = user.name
                logger.debug(f"User found: {user_id} name: {name}")

            if role == "driver":
                busy = await self.is_driver_busy(ObjectId(user_id))
                logger.debug(f"Driver {user_id} busy status: {busy}")

            payload = {
                "user_id": user_id,
                "role": role,
                "coordinates": coordinates,
                "location_text": location_text,
                "busy": busy,
                "name": name
            }

            if hasattr(self, "pair_group"):
                logger.info(f"Sending location update to pair group {self.pair_group} for user {user_id}")
                await self.channel_layer.group_send(
                    self.pair_group,
                    {"type": "broadcast_location", "data": payload}
                )
            else:
                logger.info(f"Sending location update to 'location_tracking' group for user {user_id}")
                await self.channel_layer.group_send(
                    "location_tracking",
                    {"type": "broadcast_location", "data": payload}
                )

            if role == "driver":
                logger.info(f"Additionally sending driver {user_id} update to 'location_tracking' group")
                await self.channel_layer.group_send(
                    "location_tracking",
                    {"type": "broadcast_location", "data": payload}
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def broadcast_location(self, event):
        try:
            await self.send(text_data=json.dumps(event["data"]))
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)

    @database_sync_to_async
    def is_driver_busy(self, driver_id):
        busy = Request.objects(driver=driver_id, status=1).first() is not None
        logger.debug(f"is_driver_busy({driver_id}) -> {busy}")
        return busy

    @database_sync_to_async
    def get_pair_ids(self, user_id, role):
        try:
            if role == "user":
                req = Request.objects(user=user_id, status=1).first()
            elif role == "driver":
                req = Request.objects(driver=user_id, status=1).first()
            else:
                logger.debug(f"get_pair_ids called with invalid role {role}")
                return None, None

            if req:
                logger.debug(f"Found active Request for role {role}: user={req.user.id}, driver={req.driver.id}")
                return str(req.user.id), str(req.driver.id)
            logger.debug(f"No active Request found for user_id={user_id}, role={role}")
            return None, None
        except Exception as e:
            logger.exception("Exception in get_pair_ids")
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
            logger.debug(f"Saving location for user {user_id}: {coordinates} / {location_text}")
            obj.save()
            logger.info(f"Location updated for user {user_id}")

    @database_sync_to_async
    def get_all_drivers_status(self):
        drivers = User.objects(role='driver')
        result = []
        for driver in drivers:
            busy = Request.objects(driver=driver.id, status=1).first() is not None
            loc = DriverLocation.objects(user=driver.id).first()
            coords = loc.coordinates if loc else None
            loc_text = loc.location_text if loc else ""

            result.append({
                "user_id": str(driver.id),
                "coordinates": coords,
                "location_text": loc_text,
                "busy": busy,
                "name": driver.name
            })
            logger.debug(f"Driver status collected: {driver.id} busy={busy} coords={coords}")
        return result

    @database_sync_to_async
    def get_user(self, user_id):
        user = User.objects(id=user_id).first()
        logger.debug(f"get_user({user_id}) found: {user is not None}")
        return user
