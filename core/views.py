from bson.errors import InvalidId
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core_requests.models import *
from core_requests.serializers import *
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password, check_password
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView, ListAPIView
from django.shortcuts import get_object_or_404
from mongoengine.errors import DoesNotExist, ValidationError as MongoValidationError
from rest_framework.exceptions import NotFound
import openpyxl
from openpyxl.utils import get_column_letter
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from bson import ObjectId, errors as bson_errors
from bson import ObjectId
from authorization.models import User
from authorization.serializers import UserSerializer
from core_requests.utils import send_push_notification_to_user
from rest_framework.pagination import LimitOffsetPagination
from django.shortcuts import render
from authorization.views import *
from core.serializers import *
from mongoengine import Document, StringField, BooleanField
from collections import Counter, defaultdict
from datetime import datetime
import csv
from collections import defaultdict
from django.http import HttpResponse


def test_location_view(request):
    return render(request, 'test-location.html')


class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")
        if not start_date or not end_date:
            return Response({"detail": "Start and end dates required."}, status=400)

        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return Response({"detail": "Invalid date format. Use ISO format."}, status=400)
        requests_in_range = Request.objects(date__gte=start, date__lte=end)
        request_ids = [req.id for req in requests_in_range]
        routes = Route.objects(request__in=request_ids)

        trips = Trip.objects(end_time__gte=start, end_time__lte=end)
        driver_trip_counts = defaultdict(int)
        for trip in trips:
            if trip.car_user and trip.car_user.user:
                driver_trip_counts[str(trip.car_user.user.id)] += 1

        return Response({
            "routes_count": routes.count(),
            "driver_load": driver_trip_counts,
        })


class ReportCSVDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = request.user.role.value
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")
        if not start_date or not end_date:
            return Response({"detail": "Start and end dates required."}, status=400)

        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return Response({"detail": "Invalid date format. Use ISO format."}, status=400)

        requests_in_range = Request.objects(date__gte=start, date__lte=end)
        request_ids = [req.id for req in requests_in_range]
        routes = Route.objects(request__in=request_ids)

        trips = Trip.objects(end_time__gte=start, end_time__lte=end)
        driver_trip_counts = defaultdict(int)
        for trip in trips:
            if trip.car_user and trip.car_user.user:
                driver_trip_counts[str(trip.car_user.user.id)] += 1

        response = HttpResponse(content_type='text/csv')
        filename = f"report_{start.date()}_to_{end.date()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Отчёт по маршрутам и загрузке водителей'])
        writer.writerow(['Период:', f'{start}', '-', f'{end}'])
        writer.writerow([])

        writer.writerow(['Количество маршрутов за период', routes.count()])
        writer.writerow([])

        writer.writerow(['ID водителя', 'Количество поездок'])
        for driver_id, trip_count in driver_trip_counts.items():
            writer.writerow([driver_id, trip_count])

        return response


class CarListCreateAPIView(APIView):
    pagination_class = UnlimitedPagination
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получить список автомобилей с пагинацией.",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество машин на странице (по умолчанию 10, максимум не ограничен)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка (по умолчанию 0)",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список автомобилей",
                schema=CarSerializer(many=True)
            ),
            400: "Неверные параметры запроса (например, отрицательный limit/offset)"
        }
    )
    def get(self, request):
        cars = Car.objects.all()
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(cars, request)
        serializer = CarSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Создать новый автомобиль.",
        request_body=CarSerializer,
        responses={
            201: CarSerializer,
            400: "Ошибка валидации данных"
        }
    )
    def post(self, request):
        serializer = CarSerializer(data=request.data)
        if serializer.is_valid():
            car = serializer.save()
            return Response(CarSerializer(car).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CarDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: CarSerializer()}
    )
    def get_object(self, pk):
        try:
            return Car.objects.get(id=pk)
        except Car.DoesNotExist:
            raise NotFound(detail="Car not found", code=404)

    @swagger_auto_schema(
        request_body=CarSerializer,
        responses={200: CarSerializer()}
    )
    def put(self, request, pk):
        car = self.get_object(pk)
        serializer = CarSerializer(car, data=request.data)
        if serializer.is_valid():
            updated_car = serializer.save()
            return Response(CarSerializer(updated_car).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={204: 'No Content'}
    )
    def delete(self, request, pk):
        car = get_object_or_404(Car, pk=pk)
        car.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CarUserListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить список связей 'Автомобиль-Пользователь' с пагинацией.",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество элементов на странице (по умолчанию 10, максимум не ограничен)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка (по умолчанию 0)",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список связей 'Автомобиль-Пользователь'",
                schema=CarUserSerializer(many=True)
            ),
            400: "Неверные параметры запроса (например, отрицательный limit/offset)"
        }
    )
    def get(self, request):
        car_users = Car_user.objects.all()
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(car_users, request)
        serializer = CarUserSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Создать новую связь 'Автомобиль-Пользователь'.",
        request_body=CarUserSerializer,
        responses={
            201: CarUserSerializer,
            400: "Ошибка валидации данных"
        }
    )
    def post(self, request):
        serializer = CarUserSerializer(data=request.data)
        if serializer.is_valid():
            car_user = serializer.save()
            return Response(CarUserSerializer(car_user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CarUserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Car_user.objects.get(id=pk)
        except Car_user.DoesNotExist:
            raise NotFound("Car_user not found")

    @swagger_auto_schema(responses={200: CarUserSerializer()})
    def get(self, request, pk):
        car_user = self.get_object(pk)
        return Response(CarUserSerializer(car_user).data)

    @swagger_auto_schema(
        request_body=CarUserSerializer,
        responses={200: CarUserSerializer()}
    )
    def put(self, request, pk):
        try:
            car_user = Car_user.objects.get(id=ObjectId(pk))
        except Car_user.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CarUserSerializer(car_user, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(CarUserSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(request_body=CarUserSerializer, responses={200: CarUserSerializer()})
    def patch(self, request, pk):
        try:
            car_user = Car_user.objects.get(id=ObjectId(pk))
        except Car_user.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CarUserSerializer(car_user, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(CarUserSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(responses={204: 'No content'})
    def delete(self, request, pk):
        car_user = self.get_object(pk)
        car_user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
