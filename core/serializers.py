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

from bson import ObjectId

class RouteSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    departure = serializers.CharField(required=False, allow_blank=True)
    destination = serializers.CharField(required=False, allow_blank=True)
    waiting_time = serializers.IntegerField(required=False, allow_null=True)
    time = serializers.IntegerField(required=False, allow_null=True)

    # вместо полной сериализации Request, просто передаём ID
    request = serializers.CharField(required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['request'] = str(instance.request.id) if instance.request else None
        return data

    def create(self, validated_data):
        request_id = validated_data.pop("request", None)
        if request_id:
            validated_data["request"] = Request.objects.get(id=ObjectId(request_id))
        return Route.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if "request" in validated_data:
            request_id = validated_data.pop("request")
            validated_data["request"] = Request.objects.get(id=ObjectId(request_id))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class RequestSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    goal = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateTimeField(required=False, allow_null=True)
    user = serializers.CharField()
    status = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True)

    # Добавляем список маршрутов
    routes = RouteSerializer(many=True, required=False)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        status_choices = dict(Request.STATUS_CHOICES)
        representation['status_text'] = status_choices.get(instance.status, "Unknown")

        # вручную конвертируем ObjectId
        representation["id"] = str(instance.id)

        # сериализуем маршруты
        route_objects = Route.objects(request=instance)
        representation['routes'] = RouteSerializer(route_objects, many=True).data

        return representation

    def create(self, validated_data):
        routes_data = validated_data.pop("routes", [])
        user_id = validated_data.pop("user")
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))

        # Создаем заявку
        request = Request.objects.create(**validated_data)

        # Создаем маршруты и связываем с заявкой
        route_refs = []
        for route_data in routes_data:
            route = Route.objects.create(request=request, **route_data)
            route_refs.append(route)

        # Добавляем ссылки на маршруты в заявку
        request.routes = route_refs
        request.save()

        return request

    def update(self, instance, validated_data):
        if "user" in validated_data:
            user_id = validated_data.pop("user")
            validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        validated_data.pop("routes", None)
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