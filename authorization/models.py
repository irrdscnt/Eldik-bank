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
    subdepartment = StringField(max_length=255, null=True)
    number = StringField(max_length=15, null=True)
    password = StringField(required=True)
    role = EnumField(Role, default=Role.USER)

    def __str__(self):
        return self.name or self.email

    @property
    def is_authenticated(self):
        return True

    def get_frequent_routes(self):
        requests = Request.objects(user=self)
        frequent_routes = set()
        for request in requests:
            for route in request.routes:
                if route.is_frequent:
                    frequent_routes.add(route)
        return list(frequent_routes)
