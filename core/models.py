from datetime import datetime

from mongoengine import Document, StringField, EmailField, IntField, EnumField, DateTimeField, ListField
from enum import Enum
from mongoengine import ReferenceField
from datetime import datetime, timezone

from mongoengine import Document, ReferenceField, StringField, DateTimeField

class Role(Enum):
    USER = 'user'
    ADMIN = 'admin'
    DRIVER = 'driver'
    DISPETCHER = 'dispetcher'


class User(Document):
    name = StringField(max_length=255, null=True)
    email = EmailField(required=True, unique=True)
    number = StringField(max_length=15, null=True)
    password = StringField(required=True)
    role = EnumField(Role, default=Role.USER)

    def __str__(self):
        return self.name or self.email

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        This mimics Django's User model behavior for compatibility with IsAuthenticated.
        """
        return True

    def get_frequent_routes(self):
        requests = Request.objects(user=self)
        frequent_routes = set()
        for request in requests:
            for route in request.routes:
                if route.is_frequent:
                    frequent_routes.add(route)
        return list(frequent_routes)


import random
import string
from mongoengine import *


class EmailVerification(Document):
    email = EmailField(required=True)
    code = StringField(required=True)
    is_verified = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)

    def generate_code(self, length=6):
        self.code = ''.join(random.choices(string.digits, k=length))


class Request(Document):
    STATUS_CHOICES = (
        (0, 'Created'),
        (1, 'In Progress'),
        (2, 'Completed'),
        (3, 'Rejected'),
    )

    # goal = StringField(null=True)
    date = DateField(null=True)
    user = ReferenceField(User, reverse_delete_rule=2)  # CASCADE
    status = IntField(choices=STATUS_CHOICES, default=0)
    comments = StringField(null=True, default=0)
    routes = ListField(ReferenceField('Route'))

    def __str__(self):
        return f"Request by {self.user.name}"


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


class Route(Document):
    goal = StringField(null=True)
    departure = StringField(max_length=255, null=True)
    destination = StringField(max_length=255, null=True)
    # waiting_time = IntField(null=True)
    request = ReferenceField(Request, reverse_delete_rule=2)
    time = StringField(max_length=100, null=True)
    usage_count = IntField(default=0)

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

    # def update_route_usage(self):
    #     """Увеличивает счетчик использования маршрута."""
    #     self.route.update(inc__usage_count=1)
    #     self.route.reload() 
    #     self.route.mark_as_frequent()





class DeviceToken(Document):
    user = ReferenceField(User, reverse_delete_rule=CASCADE)
    fcm_token = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'indexes': [
            'user',
            'fcm_token'
        ]
    }

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