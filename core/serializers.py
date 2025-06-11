from rest_framework import serializers
from core_requests.models import *
from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from bson import ObjectId
from django.contrib.auth.hashers import check_password
from core_requests.serializers import *


class CarSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    car_type = serializers.CharField(required=False, allow_blank=True)
    number = serializers.CharField(required=False, allow_blank=True)

    # user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    # status = serializers.IntegerField(required=False, allow_null=True)

    def create(self, validated_data):
        return Car.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.car_type = validated_data.get('car_type', instance.car_type)
        instance.number = validated_data.get('number', instance.number)
        # instance.user = validated_data.get('user', instance.user)
        # instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance


class LocationSerializer(serializers.Serializer):
    latitude = serializers.CharField()
    longitude = serializers.CharField()


class CarUserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user = serializers.CharField()
    car = serializers.CharField()
    status = serializers.IntegerField(required=False, allow_null=True)
    location_history = LocationSerializer(many=True, required=False)

    def create(self, validated_data):
        user = User.objects.get(id=validated_data['user'])
        car = Car.objects.get(id=validated_data['car'])
        location_history = validated_data.get("location_history", [])

        car_user = Car_user.objects.create(
            user=user,
            car=car,
            status=validated_data.get("status"),
            location_history=location_history
        )
        return car_user

    def update(self, instance, validated_data):
        if 'user' in validated_data:
            user_id = validated_data.pop('user')
            instance.user = User.objects.get(id=ObjectId(user_id))

        if 'car' in validated_data:
            car_id = validated_data.pop('car')
            instance.car = Car.objects.get(id=ObjectId(car_id))
        if 'location_history' in validated_data:
            locations = validated_data.pop('location_history')
            instance.location_history = [Location(**loc) for loc in locations]
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
