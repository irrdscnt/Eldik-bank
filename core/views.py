from bson.errors import InvalidId
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import *
from core.serializers import *
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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from bson import ObjectId
from core.models import User
from core.serializers import UserSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


class UserDetail(APIView):
    permission_classes = [IsAuthenticated]  # Enforce JWT authentication for all methods

    def get_object(self, pk):
        try:
            return User.objects.get(id=ObjectId(pk))
        except (User.DoesNotExist, ObjectId.InvalidId):
            return None

    @swagger_auto_schema(
        operation_description="Получить информацию о пользователе по ID",
        responses={
            200: UserSerializer,
            404: "Пользователь не найден"
        }
    )
    def get(self, request, pk):
        user = self.get_object(pk)
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Обновить данные пользователя по ID (только для самого пользователя или админа)",
        request_body=UserSerializer,
        responses={
            200: UserSerializer,
            400: "Неверные данные",
            403: "Нет прав на изменение",
            404: "Пользователь не найден"
        }
    )
    def put(self, request, pk):
        user = self.get_object(pk)
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if str(user.id) != str(request.user.id) and request.user.role != 'admin':
            return Response({"detail": "You do not have permission to update this user."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Частично обновить данные пользователя по ID (только для самого пользователя или админа)",
        request_body=UserSerializer,
        responses={
            200: UserSerializer,
            400: "Неверные данные",
            403: "Нет прав на изменение",
            404: "Пользователь не найден"
        }
    )
    def patch(self, request, pk):
        user = self.get_object(pk)
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if str(user.id) != str(request.user.id) and request.user.role != 'admin':
            return Response({"detail": "You do not have permission to update this user."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Удалить пользователя по ID (только для админа)",
        responses={
            204: "Пользователь успешно удален",
            403: "Нет прав на удаление",
            404: "Пользователь не найден"
        }
    )
    def delete(self, request, pk):
        if request.user.role != 'admin':
            return Response({"detail": "Only admins can delete users."}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(id=ObjectId(pk))
            user.delete()
            return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except (User.DoesNotExist, ObjectId.InvalidId):
            return Response({"detail": "User not found or invalid ID."}, status=status.HTTP_404_NOT_FOUND)


class UserList(APIView):
    @swagger_auto_schema(
        operation_description="Получает список всех пользователей.",
        responses={200: UserSerializer(many=True)}
    )
    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Создает нового пользователя оставим для админа",
        request_body=UserSerializer,
        responses={
            201: UserSerializer,
            400: 'Ошибка валидации данных'
        }
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from mongoengine import Document, StringField, BooleanField


class EmailVerification(Document):
    email = StringField(required=True)
    code = StringField(required=True)
    is_verified = BooleanField(default=False)

    # Храним временные данные регистрации
    name = StringField()
    number = StringField()
    password = StringField()
    is_reset = BooleanField(default=False)

    def generate_code(self):
        import random
        self.code = str(random.randint(100000, 999999))


class RegisterUser(APIView):
    @swagger_auto_schema(
        operation_description="Регистрирует нового пользователя. Отправляет код подтверждения на email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'name', 'number', 'password', 'role'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email'),
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'number': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format='password'),
                'role': openapi.Schema(type=openapi.TYPE_STRING, example='user'),
            },
        ),
        responses={200: 'Verification code sent to email', 400: 'Validation error'},
    )
    def post(self, request):
        data = request.data

        if data.get('role') != 'user':
            return Response({"detail": "Only 'user' can register this way."}, status=400)

        if '@' not in data.get('email', ''):
            return Response({"detail": "Invalid email address."}, status=400)

        if User.objects(email=data['email']).first():
            return Response({"detail": "User with this email already exists."}, status=400)

        verification = EmailVerification(
            email=data['email'],
            name=data['name'],
            number=data['number'],
            password=make_password(data['password'])
        )
        verification.generate_code()
        verification.save()

        send_mail(
            'Your verification code',
            f'Code: {verification.code}',
            'bishkekcinematica@gmail.com',
            [data['email']],
        )

        return Response({"detail": "Verification code sent to email."}, status=200)


class ConfirmRegistration(APIView):
    @swagger_auto_schema(
        operation_description="Подтверждает регистрацию по коду, отправленному на email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'code'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description="Email пользователя"),
                'code': openapi.Schema(type=openapi.TYPE_STRING, description="Код подтверждения"),
            }
        ),
        responses={
            200: openapi.Response(description="User registered successfully.", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                        'id': openapi.Schema(type=openapi.TYPE_STRING),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'role': openapi.Schema(type=openapi.TYPE_STRING),
                    })
                }
            )),
            400: openapi.Response(description="Invalid or already used code / Missing fields"),
        },
        operation_summary="Подтверждение регистрации путем получения кода на почту"
    )
    def post(self, request):
        code = request.data.get('code')
        email = request.data.get('email')

        if not all([code, email]):
            return Response({"detail": "Email and code are required."}, status=400)

        verification = EmailVerification.objects(email=email, code=code).first()
        if not verification or verification.is_verified:
            return Response({"detail": "Invalid or already used code."}, status=400)

        user = User(
            name=verification.name,
            email=email,
            number=verification.number,
            password=verification.password,
            role=Role.USER
        )
        user.save()

        verification.is_verified = True
        verification.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            'access': access_token,
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role.value
            }
        }, status=200)


class LoginView(APIView):
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(description="Successful login", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                        'id': openapi.Schema(type=openapi.TYPE_STRING),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'role': openapi.Schema(type=openapi.TYPE_STRING),
                    })
                }
            )),
            400: 'Bad Request',
            401: 'Unauthorized',
            404: 'Not Found'
        }
    )
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects(email=email).first()
        if not user:
            return Response({"detail": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if not check_password(password, user.password):
            return Response({"detail": "Incorrect password."}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            'access': access_token,
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role.value
            }
        }, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description="Refresh token")
            }
        ),
        responses={
            200: openapi.Response(description="Token refreshed", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )),
            400: 'Invalid token'
        }
    )
    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=400)

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            return Response({'access': access_token}, status=200)
        except TokenError as e:
            return Response({"detail": str(e)}, status=400)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description="Refresh token to blacklist")
            }
        ),
        responses={
            205: 'Successfully logged out',
            400: 'Invalid token'
        }
    )
    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=400)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            return Response({"detail": str(e)}, status=400)


class ForgotPasswordView(APIView):
    @swagger_auto_schema(
        request_body=ForgotPasswordSerializer,
        responses={200: ForgotPasswordResponseSerializer, 404: 'User not found', 400: 'Bad Request'}
    )
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"detail": "Email is required."}, status=400)

        user = User.objects(email=email).first()
        if not user:
            return Response({"detail": "User not found."}, status=404)

        verification = EmailVerification(email=email, is_reset=True)
        verification.generate_code()
        verification.save()

        send_mail(
            'Password reset code',
            f'Your code: {verification.code}',
            'bishkekcinematica@gmail.com',
            [email],
        )

        return Response({"detail": "Reset code sent to email."}, status=200)


class ResetPasswordView(APIView):
    @swagger_auto_schema(
        request_body=ResetPasswordSerializer,
        responses={200: ResetPasswordResponseSerializer, 400: 'Bad Request'},
        operation_summary="Сброс пароля"
    )
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        new_password = request.data.get('new_password')

        if not all([email, code, new_password]):
            return Response({"detail": "Email, code and new password are required."}, status=400)

        verification = EmailVerification.objects(email=email, code=code, is_reset=True, is_verified=False).first()
        if not verification:
            return Response({"detail": "Invalid or expired code."}, status=400)

        user = User.objects(email=email).first()
        if not user:
            return Response({"detail": "User not found."}, status=404)

        user.password = make_password(new_password)
        user.save()

        verification.is_verified = True
        verification.save()

        return Response({"detail": "Password reset successful."}, status=200)


# class RequestList(APIView):
#     def get(self, request):
#         requests = Request.objects.all()
#         serializer = RequestSerializer(requests, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         serializer = RequestSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestCreateView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                # 'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
                'date': openapi.Schema(type=openapi.TYPE_STRING, format='date', example="2025-05-01"),
                'user': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f"),
                'routes': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
                            'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                            'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                            # 'waiting_time': openapi.Schema(type=openapi.TYPE_INTEGER, example=15),
                            'time': openapi.Schema(type=openapi.TYPE_STRING, example="11:00"),
                        }
                    )
                ),
            },
            required=['user']
        ),
        responses={201: RequestCreateSerializer},
        operation_summary="Создание заявки с маршрутами",
        operation_description="Создает новую заявку с маршрутами. `comments` и `status` будут пустыми."
    )
    def post(self, request):
        serializer = RequestCreateSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(RequestCreateSerializer(instance).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class RequestListView(GenericAPIView):
#     serializer_class = RequestSerializer

#     def get(self, request):
#         requests = Request.objects.all()
#         serializer = self.get_serializer(requests, many=True)
#         return Response(serializer.data)

class RequestListView(GenericAPIView):
    serializer_class = RequestSerializer
    queryset = Request.objects.all()  # <== добавь это

    def get(self, request):
        requests = self.get_queryset()  # или Request.objects.all()
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)


class RequestDetail(APIView):
    def get_object(self, pk):
        try:
            return Request.objects.get(pk=pk)
        except Request.DoesNotExist:
            return None

    def get(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestSerializer(request_obj)
        return Response(serializer.data)

    def put(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestSerializer(request_obj, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestSerializer(request_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RouteList(APIView):
    def get(self, request):
        routes = Route.objects.all()
        serializer = RouteSerializer(routes, many=True)
        return Response(serializer.data)


class CreateRouteWithRequestView(APIView):
    @swagger_auto_schema(
        operation_summary="Создать маршрут с привязкой к заявке (с подсчётом usage_count)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['goal', ' departure', 'destination', 'request'],
            properties={
                'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
                'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                # 'waiting_time': openapi.Schema(type=openapi.TYPE_INTEGER, example=15),
                'time': openapi.Schema(type=openapi.TYPE_STRING, example="11:00"),
                'request': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f")
            }
        ),
        responses={201: RouteSerializer}
    )
    def post(self, request):
        data = request.data
        departure = data.get("departure")
        destination = data.get("destination")

        # Найти все маршруты с таким же departure + destination
        existing_routes = Route.objects(departure=departure, destination=destination)

        usage_count = existing_routes.count() + 1  # сколько раз уже использовался этот маршрут

        # Преобразовать request id
        request_id = data.get("request")
        if request_id:
            data["request"] = str(request_id)

        serializer = RouteSerializer(data=data)
        if serializer.is_valid():
            route = serializer.save()
            route.usage_count = usage_count
            route.save()
            return Response(RouteSerializer(route).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RouteDetail(APIView):
    def get_object(self, pk):
        try:
            return Route.objects.get(pk=pk)
        except Route.DoesNotExist:
            return None

    def get(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route)
        return Response(serializer.data)

    def put(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RouteSerializer(route, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        route = self.get_object(pk)
        if route is None:
            return Response({"detail": "Route not found."}, status=status.HTTP_404_NOT_FOUND)

        if route.request:
            try:
                req = route.request
                if route in req.routes:
                    req.routes.remove(route)
                    req.save()
            except Exception as e:
                pass

        route.delete()
        return Response({"detail": "Route deleted."}, status=status.HTTP_204_NO_CONTENT)


from collections import Counter, defaultdict


class UserFrequentRoutes(APIView):
    def get(self, request, user_id):
        if not ObjectId.is_valid(user_id):
            return Response({"detail": "Invalid user ID format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=ObjectId(user_id))
            requests = Request.objects(user=user)

            all_routes = []
            for req in requests:
                all_routes.extend(req.routes)

            route_groups = defaultdict(list)
            for route in all_routes:
                key = (route.departure.strip() if route.departure else "",
                       route.destination.strip() if route.destination else "")
                route_groups[key].append(route)

            count_map = {k: len(v) for k, v in route_groups.items()}

            top_routes = []
            seen_keys = set()
            for key, _ in sorted(count_map.items(), key=lambda x: x[1], reverse=True):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                route = route_groups[key][0]
                route.is_frequent = True
                top_routes.append(route)
                if len(top_routes) == 5:
                    break

            serializer = RouteSerializer(top_routes, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.permissions import IsAuthenticated
from datetime import datetime


class ReportView(APIView):
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


import csv
from collections import defaultdict
from datetime import datetime
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


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

        # Получаем данные
        requests_in_range = Request.objects(date__gte=start, date__lte=end)
        request_ids = [req.id for req in requests_in_range]
        routes = Route.objects(request__in=request_ids)

        trips = Trip.objects(end_time__gte=start, end_time__lte=end)
        driver_trip_counts = defaultdict(int)
        for trip in trips:
            if trip.car_user and trip.car_user.user:
                driver_trip_counts[str(trip.car_user.user.id)] += 1

        # Создаём CSV
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


class FrequentRoutesView(APIView):
    def get(self, request):
        routes = Route.objects(usage_count__gt=5).order_by('-usage_count')
        serializer = RouteSerializer(routes, many=True)
        return Response(serializer.data)


class CarListCreateAPIView(APIView):
    @swagger_auto_schema(
        request_body=CarSerializer,
        responses={201: CarSerializer()}
    )
    def post(self, request):
        serializer = CarSerializer(data=request.data)
        if serializer.is_valid():
            car = serializer.save()
            return Response(CarSerializer(car).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={200: CarSerializer(many=True)}
    )
    def get(self, request):
        cars = Car.objects.all()
        serializer = CarSerializer(cars, many=True)
        return Response(serializer.data)


class CarDetailAPIView(APIView):
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
    @swagger_auto_schema(
        request_body=CarUserSerializer,
        responses={201: CarUserSerializer()}
    )
    def post(self, request):
        serializer = CarUserSerializer(data=request.data)
        if serializer.is_valid():
            car_user = serializer.save()
            return Response(CarUserSerializer(car_user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(responses={200: CarUserSerializer(many=True)})
    def get(self, request):
        car_users = Car_user.objects.all()
        serializer = CarUserSerializer(car_users, many=True)
        return Response(serializer.data)


class CarUserDetailAPIView(APIView):
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


class TripCreateAPIView(APIView):
    @swagger_auto_schema(
        request_body=TripSerializer,
        responses={201: TripSerializer()}
    )
    def post(self, request):
        serializer = TripSerializer(data=request.data)
        if serializer.is_valid():
            trip = serializer.save()
            return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(responses={200: TripSerializer(many=True)})
    def get(self, request):
        trips = Trip.objects.all()
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TripDetailAPIView(APIView):
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


import pandas as pd
from django.http import HttpResponse


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
