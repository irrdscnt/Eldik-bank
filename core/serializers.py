from rest_framework import serializers
from core.models import *
from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from bson import ObjectId
from core.models import User, Role
from django.contrib.auth.hashers import check_password


class UserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['user', 'admin', 'driver', 'dispetcher'], default='user')

    def validate(self, data):

        user_role = getattr(self.context['request'].user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value
        print(f"Validating role: user_role={user_role}, data={data}")

        if 'role' in data and user_role != 'admin':
            raise serializers.ValidationError({"role": "Only admins can change the role."})
        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return User.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.email = validated_data.get('email', instance.email)
        instance.number = validated_data.get('number', instance.number)
        instance.role = validated_data.get('role', instance.role)

        if 'password' in validated_data:
            instance.password = make_password(validated_data['password'])

        if 'email' in validated_data and validated_data['email'] != instance.email:
            if User.objects(email=validated_data['email']).exclude(id=instance.id).first():
                raise serializers.ValidationError({"email": "This email is already in use."})

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['id'] = str(instance.id)
        data['role'] = instance.role.value if instance.role else 'user'
        return data


class RouteSerializer(serializers.Serializer):
    goal = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(read_only=True)
    departure = serializers.CharField(required=False, allow_blank=True)
    destination = serializers.CharField(required=False, allow_blank=True)
    time = serializers.CharField(required=False, allow_blank=True)
    # waiting_time = serializers.IntegerField(required=False, allow_null=True)
    usage_count = serializers.IntegerField(read_only=True)
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
    date = serializers.DateField(required=False, allow_null=True)
    user = serializers.CharField()
    status = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True)
    routes = RouteSerializer(many=True, required=False)

    def validate(self, data):
        user_role = getattr(self.context['request'].user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value
        print(f"Validating request: user_role={user_role}, data={data}")  # Debug

        if user_role == 'dispetcher':

            allowed_fields = {'status', 'comments'}
            if any(key not in allowed_fields for key in data):
                raise serializers.ValidationError({"detail": "Dispatchers can only update status and comments."})

            if data.get('status') == 3:
                comments = data.get('comments', '').strip()
                if not comments:
                    raise serializers.ValidationError({"comments": "Comments are required when rejecting a request."})

        return data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        status_choices = dict(Request.STATUS_CHOICES)
        representation['status_text'] = status_choices.get(instance.status, "Unknown")
        representation["id"] = str(instance.id)
        route_objects = Route.objects(request=instance)
        representation['routes'] = RouteSerializer(route_objects, many=True).data
        return representation

    def create(self, validated_data):
        routes_data = validated_data.pop("routes", [])
        user_id = validated_data.pop("user")
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))
        request = Request.objects.create(**validated_data)

        route_refs = []
        for route_data in routes_data:
            route = Route.objects.create(request=request, **route_data)
            route_refs.append(route)

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


class RequestCreateSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    # goal = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False, allow_null=True)
    user = serializers.CharField()
    routes = RouteSerializer(many=True, required=False)

    def create(self, validated_data):
        routes_data = validated_data.pop("routes", [])
        user_id = validated_data.pop("user")
        validated_data["user"] = User.objects.get(id=ObjectId(user_id))

        request = Request.objects.create(
            **validated_data,
            status=None,
            comments=""
        )

        for route_data in routes_data:
            existing_route = Route.objects(
                departure=route_data.get("departure"),
                destination=route_data.get("destination"),
            ).order_by("-usage_count").first()

            if existing_route:
                route_data["usage_count"] = existing_route.usage_count + 1
            else:
                route_data["usage_count"] = 1

            Route.objects.create(request=request, **route_data)

        return request


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


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()


class RegisterResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ForgotPasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField()


class ResetPasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = self.context['user']
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not check_password(old_password, user.password):
            raise serializers.ValidationError({"old_password": "Incorrect old password."})

        if len(new_password) < 8:
            raise serializers.ValidationError({"new_password": "New password must be at least 8 characters long."})

        if old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password must be different from the old password."})

        return data
