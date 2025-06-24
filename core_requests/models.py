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
    status = IntField(default=0, choices=[(0, 'Not completed'), (1, 'Completed')])

    def __str__(self):
        return f"Route from {self.departure} to {self.destination}"

    def save(self, *args, **kwargs):
        self.status = 1 if self.end_time is not None else 0
        super().save(*args, **kwargs)

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
        if not current_reading:
            return
        if current_reading.start_odometer is None:
            return

        car = current_reading.car
        if not car:
            return

        previous_reading = cls.objects(
            driver=current_request.driver,
            request__ne=current_request,
            created_at__lte=current_reading.created_at,
            car=car
        ).order_by('-created_at', '-id').first()

        if not previous_reading:
            return

        if previous_reading.end_odometer is None:
            return

        if previous_reading.no_goal_mileage is None:
            no_goal_mileage = abs(current_reading.start_odometer - previous_reading.end_odometer)
            previous_reading.no_goal_mileage = no_goal_mileage
            try:
                previous_reading.save()

                saved_reading = cls.objects(request=previous_reading.request).first()
                if saved_reading.no_goal_mileage == no_goal_mileage:
                    print(
                        f"Verified")
                else:
                    print(
                        f"Error: no_goal_mileage not saved correctly for request")
            except Exception as e:
                print(f"Error saving no_goal_mileage for request")
        else:
            print(
                f"Skipping: no_goal_mileage already set")
