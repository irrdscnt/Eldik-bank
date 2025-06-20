from django.shortcuts import render
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
from rest_framework.pagination import LimitOffsetPagination
from mongoengine import Document, StringField, BooleanField
from authorization.views import *
import pandas as pd
from django.http import HttpResponse
from core_requests.utils import *
from collections import defaultdict


class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"detail": "FCM token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            DeviceToken.objects(user=request.user).delete()

            DeviceToken.objects.create(
                user=request.user,
                fcm_token=fcm_token,
                created_at=datetime.utcnow()
            )
            return Response({"detail": "Token saved successfully."}, status=status.HTTP_200_OK)
        except NotUniqueError:
            return Response({"detail": "FCM token already exists for another user."},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"Error saving token: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TripCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Get paginated list of all trips",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Number of items per page (default: 10, max: unlimited)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Number of items to skip (default: 0)",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of trips",
                schema=TripSerializer(many=True)
            ),
            400: "Invalid pagination parameters"
        }
    )
    def get(self, request):
        trips = Trip.objects.all()
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(trips, request)
        serializer = TripSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new trip",
        request_body=TripSerializer,
        responses={
            201: TripSerializer,
            400: "Validation error"
        }
    )
    def post(self, request):
        serializer = TripSerializer(data=request.data)
        if serializer.is_valid():
            trip = serializer.save()
            return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TripDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Trip.objects.get(id=ObjectId(pk))
        except Trip.DoesNotExist:
            return None

    @swagger_auto_schema(
        responses={200: TripSerializer()}
    )
    def get(self, request, pk):
        trip = self.get_object(pk)
        if not trip:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TripSerializer(trip).data)

    @swagger_auto_schema(
        request_body=TripSerializer,
        responses={200: TripSerializer()}
    )
    def patch(self, request, pk):
        trip = self.get_object(pk)
        if not trip:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TripSerializer(trip, data=request.data, partial=True)
        if serializer.is_valid():
            trip = serializer.save()
            return Response(TripSerializer(trip).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={204: 'No Content'}
    )
    def delete(self, request, pk):
        trip = self.get_object(pk)
        if not trip:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(
    method='get',
    operation_description="Генерация отчёта по поездкам с деталями водителей и маршрутов, выгрузка в Excel",
    responses={200: 'Excel файл с отчётом'}
)
@api_view(['GET'])
def trip_report_export(request):
    trips = Trip.objects.all()
    rows = []

    for trip in trips:
        driver_id = str(trip.car_user.id) if trip.car_user else 'Unknown'
        driver_name = (
            getattr(trip.car_user.user, 'name', 'Unknown')
            if trip.car_user and trip.car_user.user else 'Unknown'
        )

        route = trip.route
        route_id = str(route.id) if route else 'Unknown'
        route_goal = getattr(route, 'goal', 'Unknown') if route else 'Unknown'
        departure = getattr(route, 'departure', 'Unknown') if route else 'Unknown'
        destination = getattr(route, 'destination', 'Unknown') if route else 'Unknown'

        request_obj = getattr(route, 'request', None) if route else None
        trip_date = request_obj.date.strftime('%Y-%m-%d') if request_obj and request_obj.date else 'Unknown'
        request_user = getattr(request_obj.user, 'name', 'Unknown') if request_obj and request_obj.user else 'Unknown'

        end_time = trip.end_time.strftime('%Y-%m-%d %H:%M:%S') if trip.end_time else 'Unknown'

        rows.append({
            'trip_id': str(trip.id),
            'driver_id': driver_id,
            'driver_name': driver_name,
            'route_id': route_id,
            'route_goal': route_goal,
            'departure': departure,
            'destination': destination,
            'trip_date': trip_date,
            'end_time': end_time,
            'request_user': request_user,
        })

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trip Report"

    headers = [
        'trip_id', 'driver_id', 'driver_name', 'route_id', 'route_goal',
        'departure', 'destination', 'trip_date', 'end_time', 'request_user'
    ]
    ws.append(headers)

    for row in rows:
        ws.append([row[h] for h in headers])

    for col_idx, header in enumerate(headers, start=1):
        max_length = len(header)
        for row in rows:
            cell_value = str(row[header]) if row[header] is not None else ''
            max_length = max(max_length, len(cell_value))
        adjusted_width = max_length + 2
        ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=trip_report.xlsx'
    wb.save(response)
    return response


class UserTripsView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить все маршруты из заявок пользователя по его ID с пагинацией",
        manual_parameters=[
            openapi.Parameter('limit', openapi.IN_QUERY,
                              description="Количество элементов на странице (не ограничено)",
                              type=openapi.TYPE_INTEGER),
            openapi.Parameter('offset', openapi.IN_QUERY,
                              description="Смещение от начала списка",
                              type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список маршрутов",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'next': openapi.Schema(type=openapi.TYPE_STRING),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT)
                        )
                    }
                )
            ),
            403: "Нет прав доступа",
            404: "Пользователь не найден",
            400: "Неверный формат ID пользователя"
        }
    )
    def get(self, request, user_id):
        if str(request.user.id) != user_id and request.user.role != 'admin':
            return Response(
                {"detail": "You do not have permission to view these routes."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not ObjectId.is_valid(user_id):
            return Response(
                {"detail": "Invalid user ID format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=ObjectId(user_id))
            requests = Request.objects(user=user)
            serializer = RequestSerializer(requests, many=True)

            all_routes = []
            for request_data in serializer.data:
                all_routes.extend(request_data.get('routes', []))

            paginator = self.pagination_class()
            paginated_routes = paginator.paginate_queryset(all_routes, request)

            if paginated_routes is not None:
                return paginator.get_paginated_response(paginated_routes)

            return Response(all_routes, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RouteList(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить список всех маршрутов с пагинацией",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество элементов на странице (без ограничений)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список маршрутов",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество маршрутов"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу",
                                               nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу", nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING, description="ID маршрута"),
                                    'goal': openapi.Schema(type=openapi.TYPE_STRING, description="Цель маршрута",
                                                           nullable=True),
                                    'departure': openapi.Schema(type=openapi.TYPE_STRING,
                                                                description="Место отправления", nullable=True),
                                    'destination': openapi.Schema(type=openapi.TYPE_STRING,
                                                                  description="Место назначения", nullable=True),
                                    'departure_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты отправления [latitude, longitude]"
                                    ),
                                    'destination_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты назначения [latitude, longitude]"
                                    ),
                                    'time': openapi.Schema(type=openapi.TYPE_STRING, description="Время",
                                                           nullable=True),
                                    'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                                  description="Количество использований"),
                                    'start_time': openapi.Schema(type=openapi.TYPE_STRING, description="Время начала",
                                                                 nullable=True),
                                    'end_time': openapi.Schema(type=openapi.TYPE_STRING, description="Время окончания",
                                                               nullable=True),
                                    'travel_date': openapi.Schema(type=openapi.TYPE_STRING, description="Дата поездки",
                                                                  nullable=True),
                                    'transport_type': openapi.Schema(type=openapi.TYPE_STRING,
                                                                     description="Тип транспорта", nullable=True),
                                }
                            )
                        )
                    }
                )
            )
        }
    )
    def get(self, request):
        routes = Route.objects.all()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(routes, request)
        serializer = RouteSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CreateRouteWithRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Создать маршрут и привязать к существующей заявке",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['goal', 'departure', 'destination'],
            properties={
                'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
                'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                'departure_coordinates': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING),
                    example=["42.8746", "74.5698"],
                    description="List of [latitude, longitude] for departure"
                ),
                'destination_coordinates': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING),
                    example=["42.8167", "74.6167"],
                    description="List of [latitude, longitude] for destination"
                ),
                'time': openapi.Schema(type=openapi.TYPE_STRING, example="11:00"),
                'request_id': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f")
            }
        ),
        responses={201: RouteSerializer}
    )
    def post(self, request):
        data = request.data
        departure = data.get("departure")
        destination = data.get("destination")
        request_id = data.get("request_id")

        existing_route = Route.objects(departure=departure, destination=destination).order_by("-usage_count").first()
        if existing_route:
            data["usage_count"] = existing_route.usage_count + 1
            route = existing_route
            serializer = RouteSerializer(route, data=data, partial=True)
        else:
            data["usage_count"] = 1
            serializer = RouteSerializer(data=data)

        if serializer.is_valid():
            route = serializer.save()
            if request_id:
                try:
                    request_obj = Request.objects.get(id=ObjectId(request_id))
                    if route not in request_obj.routes:
                        request_obj.routes.append(route)
                        request_obj.save()
                except Request.DoesNotExist:
                    return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(RouteSerializer(route).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FrequentRoutesView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить список часто используемых маршрутов (usage_count > 5) с пагинацией",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество элементов на странице",
                type=openapi.TYPE_INTEGER,
                default=10
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка",
                type=openapi.TYPE_INTEGER,
                default=0
            ),
            openapi.Parameter(
                'min_usage',
                openapi.IN_QUERY,
                description="Минимальное количество использований для фильтрации (по умолчанию 5)",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список часто используемых маршрутов",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество маршрутов"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу",
                                               nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу", nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING, description="ID маршрута"),
                                    'goal': openapi.Schema(type=openapi.TYPE_STRING, description="Цель маршрута",
                                                           nullable=True),
                                    'departure': openapi.Schema(type=openapi.TYPE_STRING,
                                                                description="Место отправления", nullable=True),
                                    'destination': openapi.Schema(type=openapi.TYPE_STRING,
                                                                  description="Место назначения", nullable=True),
                                    'departure_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты отправления [latitude, longitude]"
                                    ),
                                    'destination_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты назначения [latitude, longitude]"
                                    ),
                                    'time': openapi.Schema(type=openapi.TYPE_STRING, description="Время",
                                                           nullable=True),
                                    'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                                  description="Количество использований"),
                                    'start_time': openapi.Schema(type=openapi.TYPE_STRING, description="Время начала",
                                                                 nullable=True),
                                    'end_time': openapi.Schema(type=openapi.TYPE_STRING, description="Время окончания",
                                                               nullable=True),
                                    'travel_date': openapi.Schema(type=openapi.TYPE_STRING, description="Дата поездки",
                                                                  nullable=True),
                                    'transport_type': openapi.Schema(type=openapi.TYPE_STRING,
                                                                     description="Тип транспорта", nullable=True),
                                }
                            )
                        )
                    }
                )
            ),
            400: openapi.Response(description="Неверные параметры запроса")
        }
    )
    def get(self, request):
        try:
            min_usage = int(request.query_params.get('min_usage', 5))
        except ValueError:
            return Response({"detail": "Invalid min_usage parameter."}, status=status.HTTP_400_BAD_REQUEST)

        routes = Route.objects(usage_count__gt=min_usage).order_by('-usage_count')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(routes, request)
        serializer = RouteSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RouteDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Route.objects.get(pk=pk)
        except Route.DoesNotExist:
            return None

    @swagger_auto_schema(
        operation_description="Получить информацию о маршруте по ID",
        responses={
            200: RouteSerializer,
            404: openapi.Response(description="Маршрут не найден")
        }
    )
    def get(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Полностью обновить маршрут по ID",
        request_body=RouteSerializer,
        responses={
            200: RouteSerializer,
            400: openapi.Response(description="Неверные данные"),
            404: openapi.Response(description="Маршрут не найден")
        }
    )
    def put(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Частично обновить маршрут по ID",
        request_body=RouteSerializer,
        responses={
            200: RouteSerializer,
            400: openapi.Response(description="Неверные данные"),
            404: openapi.Response(description="Маршрут не найден")
        }
    )
    def patch(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Удалить маршрут по ID",
        responses={
            204: openapi.Response(description="Маршрут успешно удален"),
            404: openapi.Response(description="Маршрут не найден")
        }
    )
    def delete(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)

        requests = Request.objects(routes=route)
        for req in requests:
            req.routes.remove(route)
            req.save()

        route.delete()
        return Response({"detail": "Route deleted."}, status=status.HTTP_204_NO_CONTENT)


class UserFrequentRoutes(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить самые частые маршруты пользователя",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество возвращаемых маршрутов",
                type=openapi.TYPE_INTEGER,
                default=5
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка",
                type=openapi.TYPE_INTEGER,
                default=0
            ),
            openapi.Parameter(
                'min_count',
                openapi.IN_QUERY,
                description="Минимальное количество поездок по маршруту",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Список самых частых маршрутов пользователя",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество маршрутов"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу",
                                               nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу", nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING, description="ID маршрута"),
                                    'departure': openapi.Schema(type=openapi.TYPE_STRING,
                                                                description="Место отправления", nullable=True),
                                    'destination': openapi.Schema(type=openapi.TYPE_STRING,
                                                                  description="Место назначения", nullable=True),
                                    'departure_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты отправления [latitude, longitude]"
                                    ),
                                    'destination_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        description="Координаты назначения [latitude, longitude]"
                                    ),
                                    'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                                  description="Количество использований"),
                                    'is_frequent': openapi.Schema(type=openapi.TYPE_BOOLEAN,
                                                                  description="Частый маршрут")
                                }
                            )
                        )
                    }
                )
            ),
            400: openapi.Response(description="Неверный формат ID пользователя"),
            404: openapi.Response(description="Пользователь не найден"),
            500: openapi.Response(description="Внутренняя ошибка сервера")
        }
    )
    def get(self, request, user_id):
        if not ObjectId.is_valid(user_id):
            return Response({"detail": "Invalid user ID format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            min_count = int(request.query_params.get('min_count', 1))
            user = User.objects.get(id=ObjectId(user_id))
            requests = Request.objects(user=user)

            all_routes = []
            for req in requests:
                all_routes.extend(req.routes)

            route_groups = defaultdict(list)
            for route in all_routes:
                key = (route.departure.strip().lower() if route.departure else "",
                       route.destination.strip().lower() if route.destination else "")
                if key != ("", ""):
                    route_groups[key].append(route)

            count_map = {k: len(v) for k, v in route_groups.items() if len(v) >= min_count}

            sorted_routes = []
            for key, count in sorted(count_map.items(), key=lambda x: x[1], reverse=True):
                route = route_groups[key][0]
                route.usage_count = count
                route.is_frequent = True
                route.save()
                sorted_routes.append(route)

            paginator = self.pagination_class()
            paginated_routes = paginator.paginate_queryset(sorted_routes, request)
            serializer = RouteSerializer(paginated_routes, many=True)

            return paginator.get_paginated_response(serializer.data)

        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "Invalid min_count parameter."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignDriverToRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Назначить водителя на заявку (только для диспетчеров).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['driver_id'],
            properties={
                'driver_id': openapi.Schema(type=openapi.TYPE_STRING, description="ID водителя"),
            }
        ),
        responses={
            200: RequestSerializer,
            400: "Неверные данные",
            403: "Нет прав на назначение",
            404: "Заявка или водитель не найдены"
        }
    )
    def post(self, request, pk):
        user_role = getattr(request.user, 'role', None)
        if hasattr(user_role, 'value'):
            user_role = user_role.value
        if user_role != 'dispetcher':
            return Response({"detail": "Only dispatchers can assign drivers."}, status=status.HTTP_403_FORBIDDEN)

        try:
            request_obj = Request.objects.get(id=ObjectId(pk))
        except (DoesNotExist, InvalidId):
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        driver_id = request.data.get('driver_id')
        if not driver_id:
            return Response({"detail": "Driver ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            driver = User.objects.get(id=ObjectId(driver_id))
            if driver.role != Role.DRIVER:
                return Response({"detail": "Assigned user must have the DRIVER role."},
                                status=status.HTTP_400_BAD_REQUEST)
        except (DoesNotExist, InvalidId):
            return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)

        request_obj.driver = driver
        request_obj.status = 1
        request_obj.save()

        user_title = "Ваша заявка принята в работу"
        user_body = f"Водитель {driver.name or driver.email} назначен на вашу заявку от {request_obj.date}."
        send_push_notification_to_user(request_obj.user, user_title, user_body)

        driver_title = "Назначена новая заявка"
        route_info = f"{request_obj.routes[0].departure} → {request_obj.routes[0].destination}" if request_obj.routes else "Маршрут не указан"
        driver_body = f"Вам назначена заявка от {request_obj.user.name or request_obj.user.email} на {request_obj.date}. Маршрут: {route_info}."
        send_push_notification_to_user(driver, driver_title, driver_body)

        serializer = RequestSerializer(request_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RequestSerializer
    pagination_class = UnlimitedPagination

    def get_queryset(self, user_id):
        try:
            user = User.objects.get(id=ObjectId(user_id))
            return Request.objects(Q(user=user) | Q(driver=user)).order_by('-date')
        except (ObjectDoesNotExist, ObjectId.InvalidId):
            return Request.objects.none()

    @swagger_auto_schema(
        operation_description="Получить список всех заявок, связанных с указанным пользователем (как пользователь или водитель) с пагинацией",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_PATH,
                description="ID пользователя для фильтрации заявок",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество элементов на странице (без ограничений)",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка",
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список заявок пользователя",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество заявок"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу",
                                               nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу", nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING, description="ID заявки"),
                                    'date': openapi.Schema(type=openapi.TYPE_STRING, description="Дата заявки",
                                                           nullable=True),
                                    'user': openapi.Schema(type=openapi.TYPE_STRING, description="ID пользователя"),
                                    'driver': openapi.Schema(type=openapi.TYPE_STRING, description="ID водителя",
                                                             nullable=True),
                                    'status': openapi.Schema(type=openapi.TYPE_INTEGER, description="Статус заявки"),
                                    'status_text': openapi.Schema(type=openapi.TYPE_STRING,
                                                                  description="Текстовое описание статуса"),
                                    'comments': openapi.Schema(type=openapi.TYPE_STRING, description="Комментарии",
                                                               nullable=True),
                                    'routes': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'id': openapi.Schema(type=openapi.TYPE_STRING,
                                                                     description="ID маршрута"),
                                                'goal': openapi.Schema(type=openapi.TYPE_STRING,
                                                                       description="Цель маршрута", nullable=True),
                                                'departure': openapi.Schema(type=openapi.TYPE_STRING,
                                                                            description="Место отправления",
                                                                            nullable=True),
                                                'destination': openapi.Schema(type=openapi.TYPE_STRING,
                                                                              description="Место назначения",
                                                                              nullable=True),
                                                'departure_coordinates': openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                                    description="Координаты отправления [latitude, longitude]"
                                                ),
                                                'destination_coordinates': openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                                    description="Координаты назначения [latitude, longitude]"
                                                ),
                                                'time': openapi.Schema(type=openapi.TYPE_STRING, description="Время",
                                                                       nullable=True),
                                                'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                                              description="Количество использований"),
                                                'start_time': openapi.Schema(type=openapi.TYPE_STRING,
                                                                             description="Время начала", nullable=True),
                                                'end_time': openapi.Schema(type=openapi.TYPE_STRING,
                                                                           description="Время окончания",
                                                                           nullable=True),
                                                'travel_date': openapi.Schema(type=openapi.TYPE_STRING,
                                                                              description="Дата поездки",
                                                                              nullable=True),
                                                'transport_type': openapi.Schema(type=openapi.TYPE_STRING,
                                                                                 description="Тип транспорта",
                                                                                 nullable=True),
                                            }
                                        )
                                    )
                                }
                            )
                        )
                    }
                )
            ),
            400: openapi.Response(description="Неверный ID пользователя"),
            401: openapi.Response(description="Неавторизован"),
            403: openapi.Response(description="Нет прав доступа")
        }
    )
    def get(self, request, user_id, *args, **kwargs):
        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if user_role not in ['dispetcher', 'admin'] and str(request.user.id) != user_id:
            return Response(
                {"detail": "You do not have permission to view requests for this user."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            ObjectId(user_id)
        except ObjectId.InvalidId:
            return Response({"detail": "Invalid user ID format."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset(user_id)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create one or multiple requests with associated routes",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            oneOf=[
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'date': openapi.Schema(type=openapi.TYPE_STRING, format='date', example="2025-05-01"),
                        'user': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f"),
                        'routes': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
                                    'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                                    'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                                    'departure_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        example=["42.8746", "74.5698"],
                                        description="List of [latitude, longitude] for departure"
                                    ),
                                    'destination_coordinates': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(type=openapi.TYPE_STRING),
                                        example=["42.8167", "74.6167"],
                                        description="List of [latitude, longitude] for destination"
                                    ),
                                    'time': openapi.Schema(type=openapi.TYPE_STRING, example="11:00"),
                                }
                            )
                        ),
                    },
                    required=['user']
                ),
                openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'date': openapi.Schema(type=openapi.TYPE_STRING, format='date', example="2025-05-01"),
                            'user': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f"),
                            'routes': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'goal': openapi.Schema(type=openapi.TYPE_STRING,
                                                               example="В командировку в Бишкек"),
                                        'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                                        'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                                        'departure_coordinates': openapi.Schema(
                                            type=openapi.TYPE_ARRAY,
                                            items=openapi.Schema(type=openapi.TYPE_STRING),
                                            example=["42.8746", "74.5698"],
                                            description="List of [latitude, longitude] for departure"
                                        ),
                                        'destination_coordinates': openapi.Schema(
                                            type=openapi.TYPE_ARRAY,
                                            items=openapi.Schema(type=openapi.TYPE_STRING),
                                            example=["42.8167", "74.6167"],
                                            description="List of [latitude, longitude] for destination"
                                        ),
                                        'time': openapi.Schema(type=openapi.TYPE_STRING, example="11:00"),
                                    }
                                )
                            ),
                        },
                        required=['user']
                    )
                ),
            ]
        ),
        responses={
            201: RequestCreateSerializer(many=True),
            400: "Invalid data"
        }
    )
    def post(self, request):
        data = request.data
        is_list = isinstance(data, list)

        if is_list:
            serializer = RequestCreateSerializer(data=data, many=True)
            if serializer.is_valid():
                instances = serializer.save()
                return Response(RequestCreateSerializer(instances, many=True).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = RequestCreateSerializer(data=data)
            if serializer.is_valid():
                instance = serializer.save()
                return Response(RequestCreateSerializer(instance).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Request.objects.get(id=ObjectId(pk))
        except (ObjectDoesNotExist, ObjectId.InvalidId):
            return None

    def send_status_notification(self, request_obj, new_status):
        new_status = int(new_status)
        status_choices = dict(Request.STATUS_CHOICES)
        status_text = status_choices.get(new_status, "Unknown")

        user_token = DeviceToken.objects(user=request_obj.user).first()
        driver_token = DeviceToken.objects(user=request_obj.driver).first() if request_obj.driver else None

        if user_token and new_status in [1, 2]:
            title = "Заявка одобрена" if new_status == 1 else "Заявка отклонена"
            body = (f"Ваша заявка от {request_obj.date} была одобрена." if new_status == 1
                    else f"Ваша заявка от {request_obj.date} была отклонена. Причина: {request_obj.comments or 'Не указана'}.")
            send_push_notification_to_user(request_obj.user, title, body)

        if driver_token and new_status == 1 and (not user_token or driver_token.fcm_token != user_token.fcm_token):
            driver_title = f"Заявка {status_text}"
            route_info = f"{request_obj.routes[0].departure} → {request_obj.routes[0].destination}" if request_obj.routes else "Маршрут не указан"
            driver_body = f"Статус заявки от {request_obj.user.name or request_obj.user.email} на {request_obj.date} изменён на '{status_text}'. Маршрут: {route_info}."
            send_push_notification_to_user(request_obj.driver, driver_title, driver_body)

    @swagger_auto_schema(
        operation_description="Получить информацию о заявке по ID",
        responses={
            200: RequestSerializer,
            404: openapi.Response(description="Заявка не найдена")
        }
    )
    def get(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestSerializer(request_obj)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Полностью обновить заявку по ID (диспетчеры могут менять только статус, комментарии и водителя, админы — все поля)",
        request_body=RequestSerializer,
        responses={
            200: RequestSerializer,
            400: openapi.Response(description="Неверные данные"),
            403: openapi.Response(description="Нет прав на изменение"),
            404: openapi.Response(description="Заявка не найдена")
        }
    )
    def put(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if user_role not in ['dispetcher', 'admin'] and str(request_obj.user.id) != str(request.user.id):
            return Response({"detail": "You do not have permission to update this request."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = RequestSerializer(request_obj, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            if 'status' in request.data:
                self.send_status_notification(request_obj, request.data['status'])
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Частично обновить заявку по ID (диспетчеры могут менять только статус, комментарии и водителя, админы — все поля)",
        request_body=RequestSerializer,
        responses={
            200: RequestSerializer,
            400: openapi.Response(description="Неверные данные"),
            403: openapi.Response(description="Нет прав на изменение"),
            404: openapi.Response(description="Заявка не найдена")
        }
    )
    def patch(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if user_role not in ['dispetcher', 'admin'] and str(request_obj.user.id) != str(request.user.id):
            return Response({"detail": "You do not have permission to update this request."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = RequestSerializer(request_obj, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            serializer.save()
            if 'status' in request.data:
                self.send_status_notification(request_obj, request.data['status'])
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Ошибка при обновлении заявки {pk}: {str(e)}")
            return Response({"detail": "Failed to update request."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FastRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить быстрый список заявок с маршрутами через MongoDB aggregation с фильтрацией по статусу и имени пользователя",
        manual_parameters=[
            openapi.Parameter(
                'limit',
                openapi.IN_QUERY,
                description="Количество записей на странице (по умолчанию: 10)",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'offset',
                openapi.IN_QUERY,
                description="Смещение от начала списка (по умолчанию: 0)",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Фильтр по статусу заявки (0: In Progress, 1: Confirm, 2: Rejected)",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'username',
                openapi.IN_QUERY,
                description="Фильтр по имени пользователя (частичное совпадение, создатель или водитель)",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список заявок с маршрутами",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество заявок"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="URL следующей страницы",
                                               nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING, description="URL предыдущей страницы",
                                                   nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING, description="ID заявки"),
                                    'date': openapi.Schema(type=openapi.TYPE_STRING, description="Дата заявки",
                                                           nullable=True),
                                    'user': openapi.Schema(type=openapi.TYPE_STRING,
                                                           description="Имя создателя заявки"),
                                    'driver': openapi.Schema(type=openapi.TYPE_STRING, description="Имя водителя",
                                                             nullable=True),
                                    'status': openapi.Schema(type=openapi.TYPE_INTEGER, description="Статус заявки"),
                                    'status_text': openapi.Schema(type=openapi.TYPE_STRING,
                                                                  description="Текстовое описание статуса"),
                                    'comments': openapi.Schema(type=openapi.TYPE_STRING, description="Комментарии",
                                                               nullable=True),
                                    'routes': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'id': openapi.Schema(type=openapi.TYPE_STRING,
                                                                     description="ID маршрута"),
                                                'goal': openapi.Schema(type=openapi.TYPE_STRING,
                                                                       description="Цель маршрута", nullable=True),
                                                'departure': openapi.Schema(type=openapi.TYPE_STRING,
                                                                            description="Место отправления",
                                                                            nullable=True),
                                                'destination': openapi.Schema(type=openapi.TYPE_STRING,
                                                                              description="Подснежный", nullable=True),
                                                'departure_coordinates': openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                                    description="Координаты отправления [latitude, longitude]"
                                                ),
                                                'destination_coordinates': openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                                    description="Координаты назначения [latitude, longitude]"
                                                ),
                                                'time': openapi.Schema(type=openapi.TYPE_STRING, description="Время",
                                                                       nullable=True),
                                                'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                                              description="Количество использований")
                                            }
                                        )
                                    )
                                }
                            )
                        )
                    }
                )
            ),
            400: openapi.Response(description="Неверные параметры запроса")
        }
    )
    def get(self, request):
        db = get_db()

        try:
            limit = int(request.GET.get("limit", self.pagination_class.default_limit))
            offset = int(request.GET.get("offset", 0))
            status_filter = request.GET.get("status")
            username_filter = request.GET.get("username")
        except ValueError:
            return Response({"error": "Invalid pagination or filter parameters"}, status=status.HTTP_400_BAD_REQUEST)

        pipeline = []
        match_stage = {}
        if status_filter is not None:
            try:
                status_filter = int(status_filter)
                if status_filter not in [0, 1, 2]:
                    return Response({"error": "Invalid status value. Must be 0, 1, or 2."},
                                    status=status.HTTP_400_BAD_REQUEST)
                match_stage["status"] = status_filter
            except ValueError:
                return Response({"error": "Status must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        if username_filter:
            user_ids = [user.id for user in User.objects(name__icontains=username_filter)]
            if not user_ids:
                return Response({
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "results": []
                })
            match_stage["$or"] = [
                {"user": {"$in": user_ids}},
                {"driver": {"$in": user_ids}}
            ]

        if match_stage:
            pipeline.append({"$match": match_stage})

        count_pipeline = pipeline + [{"$count": "total"}]
        count_result = list(db.request.aggregate(count_pipeline))
        total_count = count_result[0]["total"] if count_result else 0

        pipeline.extend([
            {"$sort": {"date": -1}},
            {"$skip": offset},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "route",
                    "localField": "routes",
                    "foreignField": "_id",
                    "as": "routes"
                }
            },
            {
                "$lookup": {
                    "from": "user",
                    "localField": "user",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "user",
                    "localField": "driver",
                    "foreignField": "_id",
                    "as": "driver_info"
                }
            },
            {"$unwind": {"path": "$driver_info", "preserveNullAndEmptyArrays": True}},
        ])

        data = list(db.request.aggregate(pipeline))

        results = []
        for item in data:
            formatted_item = {
                "id": str(item.pop("_id")),
                "date": item.get("date").strftime("%Y-%m-%d") if item.get("date") else None,
                "user": item.get("user_info", {}).get("name", "Unknown"),
                "driver": item.get("driver_info", {}).get("name", None),
                "status": item.get("status", 0),
                "status_text": dict(Request.STATUS_CHOICES).get(item.get("status", 0), "Unknown"),
                "comments": item.get("comments", ""),
                "routes": []
            }

            for route in item.get("routes", []):
                formatted_route = {
                    "id": str(route.pop("_id", "")),
                    "goal": route.get("goal"),
                    "departure": route.get("departure"),
                    "destination": route.get("destination"),
                    "departure_coordinates": route.get("departure_coordinates", []),
                    "destination_coordinates": route.get("destination_coordinates", []),
                    "time": route.get("time"),
                    "usage_count": route.get("usage_count", 0),
                }
                formatted_item["routes"].append(formatted_route)

            results.append(formatted_item)

        paginator = self.pagination_class()
        paginator.count = total_count
        paginator.limit = limit
        paginator.offset = offset
        paginator.request = request

        response_data = {
            "count": total_count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": results
        }

        return Response(response_data)


class RouteTimeUpdate(APIView):
    permission_classes = [IsAuthenticated]

    def get_route(self, request_id, route_id):
        try:
            request_obj = Request.objects.get(id=ObjectId(request_id))
            routes = Route.objects.get(id=ObjectId(route_id))
            return routes, request_obj
        except (DoesNotExist, ObjectId.InvalidId):
            return None, None

    def send_time_notification(self, request_obj, routes, action):
        title = f"Request {'started' if action == 'start' else 'completed'}"
        body = (
            f"Request for route {routes.departure} → {routes.destination} "
            f"{'started' if action == 'start' else 'completed'} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
        )

        user_token = DeviceToken.objects(user=request_obj.user).first()
        if user_token:
            send_push_notification_to_user(request_obj.user, title, body)

        if request_obj.driver and str(request_obj.driver.id) != str(request_obj.user.id):
            driver_token = DeviceToken.objects(user=request_obj.driver).first()
            if driver_token:
                driver_title = f"Request {'started' if action == 'start' else 'completed'}"
                driver_body = (
                    f"Your request for route {routes.departure} → {routes.destination} "
                    f"{'started' if action == 'start' else 'completed'} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
                )
                send_push_notification_to_user(request_obj.driver, driver_title, driver_body)

    @swagger_auto_schema(
        operation_description="Record time and odometer reading for a route in a request",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['start', 'end'],
                                         description='Action: start or end'),
                'time': openapi.Schema(type=openapi.TYPE_STRING, format='date-time',
                                       description='Time in ISO 8601 format'),
                'odometer': openapi.Schema(type=openapi.TYPE_NUMBER,
                                           description='Odometer reading in kilometers'),
            },
            required=['action', 'odometer']
        ),
        responses={
            200: RouteSerializer,
            400: "Invalid data",
            403: "No permission to edit",
            404: "Route or request not found"
        }
    )
    def post(self, request, request_id, route_id):
        routes, request_obj = self.get_route(request_id, route_id)
        if not routes or not request_obj:
            return Response({"error": "Route or Request not found."}, status=status.HTTP_404_NOT_FOUND)

        if request_obj.driver and str(request_obj.driver.id) != str(request.user.id):
            return Response({"error": "You do not have permission to update this route."},
                            status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ['start', 'end']:
            return Response({"error": "Invalid action. Must be 'start' or 'end'."},
                            status=status.HTTP_400_BAD_REQUEST)

        time_str = request.data.get('time')
        try:
            time = datetime.fromisoformat(time_str) if time_str else datetime.now()
        except (ValueError, TypeError):
            time = datetime.now()

        odometer = request.data.get('odometer')
        try:
            odometer = float(odometer)
            if odometer < 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({"error": "Invalid odometer reading. Must be a non-negative number."},
                            status=status.HTTP_400_BAD_REQUEST)

        car_user = Car_user.objects(user=request_obj.driver).first()
        if not car_user or not car_user.car:
            return Response({"error": "No car assigned to the driver."}, status=status.HTTP_400_BAD_REQUEST)

        odometer_reading = OdometerReading.objects(
            request=request_obj,
            routes=routes,
            driver=request_obj.driver,
            car=car_user.car
        ).first()

        if not odometer_reading:
            odometer_reading = OdometerReading(
                request=request_obj,
                routes=routes,
                driver=request_obj.driver,
                car=car_user.car,
                created_at=datetime.now()
            )

        if action == 'start':
            if routes.start_time:
                return Response({"error": "Start time already set."}, status=status.HTTP_400_BAD_REQUEST)
            if odometer_reading.start_odometer is not None:
                return Response({"error": "Start odometer already set."}, status=status.HTTP_400_BAD_REQUEST)
            routes.start_time = time
            odometer_reading.start_odometer = odometer
        else:
            if not routes.start_time:
                return Response({"error": "Cannot set end time before start time."},
                                status=status.HTTP_400_BAD_REQUEST)
            if routes.end_time:
                return Response({"error": "End time already set."}, status=status.HTTP_400_BAD_REQUEST)
            if odometer_reading.end_odometer is not None:
                return Response({"error": "End odometer already set."}, status=status.HTTP_400_BAD_REQUEST)
            if odometer_reading.start_odometer is not None and odometer < odometer_reading.start_odometer:
                return Response({"error": "End odometer cannot be less than start odometer."},
                                status=status.HTTP_400_BAD_REQUEST)
            routes.end_time = time
            odometer_reading.end_odometer = odometer

        request_obj.car = car_user.car
        request_obj.save()
        routes.save()
        odometer_reading.save()

        OdometerReading.calculate_no_goal_mileage(request_obj)

        self.send_time_notification(request_obj, routes, action)
        serializer = RouteSerializer(routes)
        return Response(serializer.data, status=status.HTTP_200_OK)
