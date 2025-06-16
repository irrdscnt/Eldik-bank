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


from rest_framework import serializers
from bson import ObjectId

class CarUserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    user = serializers.CharField()
    car = serializers.CharField()
    status = serializers.IntegerField(required=False, allow_null=True)
    location_history = LocationSerializer(many=True, required=False)

    def create(self, validated_data):
        user = User.objects.get(id=ObjectId(validated_data['user']))
        car = Car.objects.get(id=ObjectId(validated_data['car']))
        
        existing = Car_user.objects(car=car).first()
        if existing:
            raise serializers.ValidationError("This car is already assigned to another user.")

        return Car_user.objects.create(
            user=user,
            car=car,
            status=validated_data.get("status"),
            location_history=[Location(**loc) for loc in validated_data.get("location_history", [])]
        )

    def update(self, instance, validated_data):
        if 'car' in validated_data:
            car = Car.objects.get(id=ObjectId(validated_data['car']))

            # Найти другого пользователя, которому уже назначена эта машина
            existing = Car_user.objects(car=car, id__ne=instance.id).first()
            if existing:
                # Обнуляем машину у другого пользователя
                existing.car = None
                existing.save()

            # Назначаем машину текущему пользователю
            instance.car = car

        if 'user' in validated_data:
            instance.user = User.objects.get(id=ObjectId(validated_data['user']))

        if 'location_history' in validated_data:
            instance.location_history = [Location(**loc) for loc in validated_data['location_history']]

        for attr, value in validated_data.items():
            if attr not in ['car', 'user', 'location_history']:
                setattr(instance, attr, value)

        instance.save()
        return instance