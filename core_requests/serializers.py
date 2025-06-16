from rest_framework import serializers
from authorization.models import *
from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from core_requests.models import *
from authorization.models import *


class TripSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    route = serializers.CharField()
    car_user = serializers.CharField()
    end_time = serializers.DateTimeField(required=False, allow_null=True)

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "route": str(instance.route.id) if instance.route else None,
            "car_user": str(instance.car_user.id) if instance.car_user else None,
            "end_time": instance.end_time,
        }

    def create(self, validated_data):
        route_id = validated_data.pop('route')
        car_user_id = validated_data.pop('car_user')
        route = Route.objects.get(id=ObjectId(route_id))
        car_user = Car_user.objects.get(id=ObjectId(car_user_id))
        return Trip.objects.create(route=route, car_user=car_user, **validated_data)

    def update(self, instance, validated_data):
        if 'route' in validated_data:
            route_id = validated_data.pop('route')
            instance.route = Route.objects.get(id=ObjectId(route_id))

        if 'car_user' in validated_data:
            car_user_id = validated_data.pop('car_user')
            instance.car_user = Car_user.objects.get(id=ObjectId(car_user_id))

        if 'end_time' in validated_data:
            instance.end_time = validated_data['end_time']

        instance.save()
        return instance


class RouteSerializer(serializers.Serializer):
    goal = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(read_only=True)
    departure = serializers.CharField(required=False, allow_blank=True)
    destination = serializers.CharField(required=False, allow_blank=True)
    departure_coordinates = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    destination_coordinates = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    time = serializers.CharField(required=False, allow_blank=True)
    usage_count = serializers.IntegerField(read_only=True)
    start_time = serializers.DateTimeField(required=False, allow_null=True)
    end_time = serializers.DateTimeField(required=False, allow_null=True)
    travel_date = serializers.DateTimeField(required=False, allow_null=True)
    transport_type = serializers.ChoiceField(choices=['passenger', 'cargo', 'light'], required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['start_time'] = instance.start_time.isoformat() if instance.start_time else None
        data['end_time'] = instance.end_time.isoformat() if instance.end_time else None
        data['travel_date'] = instance.travel_date.isoformat() if instance.travel_date else None
        data['departure_coordinates'] = instance.departure_coordinates if instance.departure_coordinates else []
        data['destination_coordinates'] = instance.destination_coordinates if instance.destination_coordinates else []
        return data

    def create(self, validated_data):
        return Route.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RequestSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    date = serializers.DateField(required=False, allow_null=True)
    user = serializers.CharField()
    driver = serializers.CharField(required=False, allow_null=True)
    status = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True)
    routes = RouteSerializer(many=True, required=False)

    def validate(self, data):
        user_role = getattr(self.context['request'].user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if user_role == 'dispetcher':
            allowed_fields = {'status', 'comments', 'driver'}
            if any(key not in allowed_fields for key in data):
                raise serializers.ValidationError(
                    {"detail": "Dispatchers can only update status, comments, and driver."})

            if data.get('status') == 2:
                comments = data.get('comments', '').strip()
                if not comments:
                    raise serializers.ValidationError({"comments": "Comments are required when rejecting a request."})

            if 'driver' in data and data['driver']:
                try:
                    driver = User.objects.get(id=ObjectId(data['driver']))
                    if driver.role != Role.DRIVER:
                        raise serializers.ValidationError({"driver": "Assigned user must have the DRIVER role."})
                except User.DoesNotExist:
                    raise serializers.ValidationError({"driver": "Driver not found."})

        return data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        status_choices = dict(Request.STATUS_CHOICES)
        representation['status_text'] = status_choices.get(instance.status, "Unknown")
        representation["id"] = str(instance.id)
        representation["user"] = str(instance.user.id)
        representation["driver"] = str(instance.driver.id) if instance.driver else None
        route_objects = instance.routes
        representation['routes'] = RouteSerializer(route_objects, many=True).data
        return representation

    def create(self, validated_data):
        routes_data = validated_data.pop("routes", [])
        user_id = validated_data.pop("user")
        driver_id = validated_data.pop("driver", None)
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        if driver_id:
            validated_data["driver"] = User.objects.get(id=ObjectId(driver_id))

        route_refs = []
        for route_data in routes_data:
            existing_route = Route.objects(
                departure=route_data.get("departure"),
                destination=route_data.get("destination")
            ).order_by("-usage_count").first()

            if existing_route:
                route_data["usage_count"] = existing_route.usage_count + 1
                route = existing_route
                route.update(**route_data)
            else:
                route_data["usage_count"] = 1
                route = Route.objects.create(**route_data)
            route_refs.append(route)

        request = Request.objects.create(**validated_data)
        request.routes = route_refs
        request.save()
        return request

    def update(self, instance, validated_data):
        if "user" in validated_data:
            user_id = validated_data.pop("user")
            validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        if "driver" in validated_data:
            driver_id = validated_data.pop("driver", None)
            validated_data["driver"] = User.objects.get(id=ObjectId(driver_id)) if driver_id else None
        routes_data = validated_data.pop("routes", None)
        if routes_data:
            route_refs = []
            for route_data in routes_data:
                existing_route = Route.objects(
                    departure=route_data.get("departure"),
                    destination=route_data.get("destination")
                ).order_by("-usage_count").first()

                if existing_route:
                    route_data["usage_count"] = existing_route.usage_count + 1
                    route = existing_route
                    route.update(**route_data)
                else:
                    route_data["usage_count"] = 1
                    route = Route.objects.create(**route_data)
                route_refs.append(route)
            instance.routes = route_refs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RequestCreateSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    date = serializers.DateField(required=False, allow_null=True)
    user = serializers.CharField()
    routes = RouteSerializer(many=True, required=False)

    def create(self, validated_data):
        routes_data = validated_data.pop("routes", [])
        user_id = validated_data.pop("user")
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))

        route_refs = []
        for route_data in routes_data:
            existing_route = Route.objects(
                departure=route_data.get("departure"),
                destination=route_data.get("destination")
            ).order_by("-usage_count").first()

            if existing_route:
                route_data["usage_count"] = existing_route.usage_count + 1
                route = existing_route
                route.update(**route_data)
            else:
                route_data["usage_count"] = 1
                route = Route.objects.create(**route_data)
            route_refs.append(route)

        request = Request.objects.create(
            **validated_data,
            status=None,
            comments=""
        )
        request.routes = route_refs
        request.save()
        return request
