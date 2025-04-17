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
    password = StringField(max_length=255)  
    role = EnumField(Role, default=Role.USER)

    def __str__(self):
        return self.name
    

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
    user = ReferenceField(User, reverse_delete_rule=2)  # CASCADE
    status = IntField(null=True)

    def __str__(self):
        return self.name

class Route(Document):
    departure = StringField(max_length=255, null=True)
    destination = StringField(max_length=255, null=True)
    waiting_time = IntField(null=True)
    request = ReferenceField(Request, reverse_delete_rule=2)  # CASCADE
    time = IntField(null=True)

    def __str__(self):
        return f"Route from {self.departure} to {self.destination}"

class Trip(Document):
    route = ReferenceField('Route', reverse_delete_rule=2)  # CASCADE
    car = ReferenceField(Car, reverse_delete_rule=2)  # CASCADE
    end_time = DateTimeField(null=True)

    def __str__(self):
        return f"Trip with {self.car.name}"