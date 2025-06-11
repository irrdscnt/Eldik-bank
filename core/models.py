from datetime import datetime

from mongoengine import Document, StringField, EmailField, IntField, EnumField, DateTimeField, ListField
from enum import Enum
from mongoengine import ReferenceField
from datetime import datetime, timezone

from mongoengine import Document, ReferenceField, StringField, DateTimeField
from authorization.models import *

import random
import string
from mongoengine import *


class Car(Document):
    name = StringField(max_length=255, null=True)
    car_type = StringField(max_length=50, null=True)
    number = StringField(max_length=20, null=True)

    def __str__(self):
        return self.name


class Location(EmbeddedDocument):
    latitude = StringField()
    longitude = StringField()


class Car_user(Document):
    user = ReferenceField(User, reverse_delete_rule=2)
    car = ReferenceField(Car, reverse_delete_rule=2)
    status = IntField(null=True)
    location_history = ListField(EmbeddedDocumentField(Location))

    def __str__(self):
        return self.status


class UserLocation(Document):
    user = ReferenceField(User, required=True, unique=True)
    latitude = StringField()
    longitude = StringField()
    location_text = StringField()
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))


class DriverLocation(Document):
    user = ReferenceField(User, required=True, unique=True)
    latitude = StringField()
    longitude = StringField()
    location_text = StringField()
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
