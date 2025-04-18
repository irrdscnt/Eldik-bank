from datetime import datetime

from mongoengine import Document, StringField, EmailField, IntField, EnumField, DateTimeField, ListField
from enum import Enum
from mongoengine import ReferenceField

class Role(Enum):
    USER = 'user'
    ADMIN = 'admin'
    DRIVER = 'driver'

class User(Document):
    name = StringField(max_length=255, null=True)
    email = EmailField(required=True, unique=True)
    number = StringField(max_length=15, null=True)
    password = StringField(required=True)
    role = EnumField(Role, default=Role.USER)

    def __str__(self):
        return self.name
    def get_frequent_routes(self):
        # Получаем все запросы пользователя
        requests = Request.objects(user=self)
        frequent_routes = set()
        for request in requests:
            for route in request.routes:
                if route.is_frequent:  # Фильтруем только постоянные маршруты
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

    goal = StringField(null=True)
    date = DateTimeField(null=True)
    user = ReferenceField(User, reverse_delete_rule=2)  # CASCADE
    status = IntField(choices=STATUS_CHOICES, default=0)  # Значение по умолчанию: 0
    comments = StringField(null=True,default=0)
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
    user = ReferenceField(User, reverse_delete_rule=2)  # CASCADE
    car = ReferenceField(Car, reverse_delete_rule=2)  # CASCADE
    status = IntField(null=True)
    location_history = ListField(EmbeddedDocumentField(Location))

    def __str__(self):
        return self.status

class Route(Document):
    departure = StringField(max_length=255, null=True)
    destination = StringField(max_length=255, null=True)
    waiting_time = IntField(null=True)
    request = ReferenceField(Request, reverse_delete_rule=2)  # CASCADE
    time = IntField(null=True)
    usage_count = IntField(default=0)  # Счетчик использования маршрута
    is_frequent = BooleanField(default=False)  # Пометка о том, является ли маршрут постоянным

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

    def update_route_usage(self):
        """Увеличивает счетчик использования маршрута."""
        self.route.update(inc__usage_count=1)
        self.route.reload()  # Перезагружаем объект маршрута
        self.route.mark_as_frequent()  # Проверяем, стал ли маршрут постоянным