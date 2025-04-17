from rest_framework import serializers
from core.models import User,Trip, Route, Car,Request
from bson import ObjectId

class UserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['user', 'admin', 'driver'], default='user')

    def create(self, validated_data):
        from django.contrib.auth.hashers import make_password
        validated_data['password'] = make_password(validated_data['password'])
        return User.objects.create(**validated_data)



class RequestSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    goal = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateTimeField(required=False, allow_null=True)
    user = serializers.CharField()  
    status = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        status_choices = dict(Request.STATUS_CHOICES)
        representation['status_text'] = status_choices.get(instance.status, "Unknown")
        if "_id" in instance:
            representation["id"] = str(instance["_id"])
        return representation

    def create(self, validated_data):
        # Преобразуем строку user обратно в ObjectId
        user_id = validated_data.pop("user")
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        return Request.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if "user" in validated_data:
            user_id = validated_data.pop("user")
            validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class CarSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    car_type = serializers.CharField(required=False, allow_blank=True)
    number = serializers.CharField(required=False, allow_blank=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())  # Ссылка на пользователя
    status = serializers.IntegerField(required=False, allow_null=True)

    def create(self, validated_data):
        return Car.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.car_type = validated_data.get('car_type', instance.car_type)
        instance.number = validated_data.get('number', instance.number)
        instance.user = validated_data.get('user', instance.user)
        instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance
    
class RouteSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    departure = serializers.CharField(required=False, allow_blank=True)
    destination = serializers.CharField(required=False, allow_blank=True)
    waiting_time = serializers.IntegerField(required=False, allow_null=True)
    request = serializers.PrimaryKeyRelatedField(queryset=Request.objects.all())  # Ссылка на запрос
    time = serializers.IntegerField(required=False, allow_null=True)

    def create(self, validated_data):
        return Route.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.departure = validated_data.get('departure', instance.departure)
        instance.destination = validated_data.get('destination', instance.destination)
        instance.waiting_time = validated_data.get('waiting_time', instance.waiting_time)
        instance.request = validated_data.get('request', instance.request)
        instance.time = validated_data.get('time', instance.time)
        instance.save()
        return instance
    

class TripSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    route = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all())  # Ссылка на маршрут
    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all())  # Ссылка на автомобиль
    end_time = serializers.DateTimeField(required=False, allow_null=True)

    def create(self, validated_data):
        return Trip.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.route = validated_data.get('route', instance.route)
        instance.car = validated_data.get('car', instance.car)
        instance.end_time = validated_data.get('end_time', instance.end_time)
        instance.save()
        return instance