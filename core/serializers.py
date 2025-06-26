from rest_framework import serializers
from core_requests.models import *
from bson import ObjectId
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from bson import ObjectId
from django.contrib.auth.hashers import check_password
from core_requests.serializers import *
from rest_framework import serializers
from bson import ObjectId
from authorization.models import User

class CarSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    id_car = serializers.IntegerField(read_only=True)  
    name = serializers.CharField(required=False, allow_blank=True)
    car_type = serializers.CharField(required=False, allow_blank=True)
    number = serializers.CharField(required=False, allow_blank=True)
    main_driver = serializers.CharField(required=True, allow_blank=True)

    def create(self, validated_data):
        main_driver_id = validated_data.pop('main_driver', None)
        main_driver = None

        if main_driver_id:
            try:
                main_driver = User.objects.get(id=ObjectId(main_driver_id))
            except User.DoesNotExist:
                raise serializers.ValidationError("Главный водитель с таким ID не найден")
        id_car = get_next_sequence('id_car')

        car = Car.objects.create(id_car=id_car, main_driver=main_driver, **validated_data)
        return car

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.car_type = validated_data.get('car_type', instance.car_type)
        instance.number = validated_data.get('number', instance.number)

        main_driver_id = validated_data.get('main_driver')
        if main_driver_id:
            try:
                main_driver = User.objects.get(id=ObjectId(main_driver_id))
                instance.main_driver = main_driver
            except User.DoesNotExist:
                raise serializers.ValidationError("Главный водитель с таким ID не найден")

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
    status = serializers.IntegerField(required=False, allow_null=True)  # твой старый статус
    assignment_status = serializers.IntegerField(required=False, default=AssignmentStatus.ASSIGNED.value)
    location_history = LocationSerializer(many=True, required=False)
    created_at = serializers.DateTimeField(read_only=True)
    def create(self, validated_data):
        user = User.objects.get(id=ObjectId(validated_data['user']))
        car = Car.objects.get(id=ObjectId(validated_data['car']))

        existing = Car_user.objects(car=car, assignment_status=AssignmentStatus.ASSIGNED.value).first()

        if existing:
            # Если текущий назначенный водитель совпадает с main_driver, разрешаем создать новую запись без изменений статуса старого
            if car.main_driver and existing.user.id == car.main_driver.id:
                return Car_user.objects.create(
                    user=user,
                    car=car,
                    status=validated_data.get("status"),
                    assignment_status=AssignmentStatus.ASSIGNED.value,
                    location_history=[Location(**loc) for loc in validated_data.get("location_history", [])]
                )
            else:
                # Если назначенный водитель не совпадает с main_driver,
                # меняем статус старого на UNASSIGNED
                existing.assignment_status = AssignmentStatus.UNASSIGNED.value
                existing.save()

        # Создаём новую запись с статусом ASSIGNED для нового пользователя
        return Car_user.objects.create(
            user=user,
            car=car,
            status=validated_data.get("status"),
            assignment_status=AssignmentStatus.ASSIGNED.value,
            location_history=[Location(**loc) for loc in validated_data.get("location_history", [])]
        )
    def update(self, instance, validated_data):
        if 'car' in validated_data:
            car = Car.objects.get(id=ObjectId(validated_data['car']))

            # Проверяем, есть ли другой водитель с ASSIGNED статусом для этой машины, кроме текущего инстанса
            existing = Car_user.objects(
                car=car,
                assignment_status=AssignmentStatus.ASSIGNED.value,
                id__ne=instance.id
            ).first()

            if existing:
                # Если existing.user — не главный водитель, меняем его статус на UNASSIGNED
                if car.main_driver is None or existing.user.id != car.main_driver.id:
                    existing.assignment_status = AssignmentStatus.UNASSIGNED.value
                    existing.save()
                # Если existing.user — главный водитель, ничего не меняем

            # Обновляем машину у текущей записи
            instance.car = car

        if 'user' in validated_data:
            instance.user = User.objects.get(id=ObjectId(validated_data['user']))

        if 'location_history' in validated_data:
            instance.location_history = [Location(**loc) for loc in validated_data['location_history']]

        # Обновляем остальные поля (например, status)
        for attr, value in validated_data.items():
            if attr not in ['car', 'user', 'location_history']:
                setattr(instance, attr, value)

        # По умолчанию при обновлении можно сохранять статус ASSIGNED
        if 'assignment_status' not in validated_data:
            instance.assignment_status = AssignmentStatus.ASSIGNED.value
        else:
            instance.assignment_status = validated_data['assignment_status']

        instance.save()
        return instance
