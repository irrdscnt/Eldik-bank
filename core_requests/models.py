from mongoengine import Document, StringField, EmailField, IntField, EnumField, DateTimeField, ListField
from enum import Enum
from mongoengine import ReferenceField
from datetime import datetime, timezone
from mongoengine import Document, ReferenceField, StringField, DateTimeField, CASCADE, DateField
from authorization.models import *
from core.models import *
from bson import ObjectId


class Request(Document):
    STATUS_CHOICES = (
        (0, 'In Progress'),
        (1, 'Confirm'),
        (2, 'Rejected'),
    )
    date = DateField(null=True)
    user = ReferenceField(User, reverse_delete_rule=2)
    driver = ReferenceField(User, null=True, reverse_delete_rule=2)
    status = IntField(choices=STATUS_CHOICES, default=0)
    comments = StringField(null=True, default="")
    routes = ListField(ReferenceField('Route'))

    def __str__(self):
        return f"Request by {self.user.name}"


class DeviceToken(Document):
    user = ReferenceField(User, reverse_delete_rule=CASCADE)
    fcm_token = StringField(required=True, unique_with='user')
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'indexes': [
            'user',
            'fcm_token'
        ]
    }


class Route(Document):
    goal = StringField(null=True)
    departure = StringField(max_length=255, null=True)
    destination = StringField(max_length=255, null=True)
    departure_coordinates = ListField(StringField(), default=list)  # [latitude, longitude]
    destination_coordinates = ListField(StringField(), default=list)  # [latitude, longitude]
    time = StringField(max_length=100, null=True)
    usage_count = IntField(default=0)
    start_time = DateTimeField(null=True)
    end_time = DateTimeField(null=True)
    travel_date = DateTimeField(null=True)
    transport_type = StringField(choices=['passenger', 'cargo', 'light'], null=True)

    def __str__(self):
        return f"Route from {self.departure} to {self.destination}"

    def mark_as_frequent(self, threshold=5):
        if self.usage_count >= threshold:
            self.is_frequent = True
            self.save()


class Trip(Document):
    route = ReferenceField('Route', reverse_delete_rule=CASCADE)
    car_user = ReferenceField(Car_user, reverse_delete_rule=CASCADE)
    end_time = DateTimeField(null=True)
