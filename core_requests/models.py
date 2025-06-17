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


class OdometerReading(Document):
    request = ReferenceField(Request, reverse_delete_rule=2)
    routes = ReferenceField(Route, reverse_delete_rule=2)
    driver = ReferenceField(User, reverse_delete_rule=2)
    car = ReferenceField(Car, null=True, reverse_delete_rule=2)
    start_odometer = FloatField(null=True)
    end_odometer = FloatField(null=True)
    no_goal_mileage = FloatField(null=True)
    created_at = DateTimeField(default=datetime.now)

    def __str__(self):
        return f"Odometer for Route {self.routes} in Request {self.request}"

    @classmethod
    def calculate_no_goal_mileage(cls, current_request):
        current_reading = cls.objects(request=current_request).first()
        if not current_reading or current_reading.start_odometer is None:
            return

        car = current_reading.car
        if not car:
            return

        previous_requests = Request.objects(
            driver=current_request.driver,
            id__ne=current_request.id,
            date__lte=current_request.date
        ).order_by('-date', '-id')

        for req in previous_requests:
            reading = cls.objects(request=req).first()
            if reading and reading.car == car and reading.end_odometer is not None and reading.no_goal_mileage is None:
                no_goal_mileage = abs(current_reading.start_odometer - reading.end_odometer)
                reading.no_goal_mileage = no_goal_mileage
                reading.save()
                return
