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
from rest_framework.generics import GenericAPIView,ListAPIView


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



class UserDetail(APIView):
    def get_object(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        user = self.get_object(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, pk):
        user = self.get_object(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        user = self.get_object(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            user = User.objects.get(id=ObjectId(pk))
            user.delete()
            return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except (User.DoesNotExist, InvalidId):
            return Response({"detail": "User not found or invalid ID."}, status=status.HTTP_404_NOT_FOUND)


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
            200: openapi.Response(description="User registered successfully."),
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

        return Response({"detail": "User registered successfully."})

class LoginView(APIView):
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: LoginResponseSerializer, 400: 'Bad Request', 401: 'Unauthorized', 404: 'Not Found'}
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

        return Response({
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role.value
        }, status=status.HTTP_200_OK)


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
            'goal': openapi.Schema(type=openapi.TYPE_STRING, example="В командировку в Бишкек"),
            'date': openapi.Schema(type=openapi.TYPE_STRING, format='date', example="2025-05-01"),
            'user': openapi.Schema(type=openapi.TYPE_STRING, example="6616df89148ebd7980e22f9f"),
            'routes': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                        'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                        'waiting_time': openapi.Schema(type=openapi.TYPE_INTEGER, example=15),
                        'time': openapi.Schema(type=openapi.TYPE_INTEGER, example=40),
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

class RequestListView(GenericAPIView):
    serializer_class = RequestSerializer

    def get(self, request):
        requests = Request.objects.all()
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
            required=['departure', 'destination', 'request'],
            properties={
                'departure': openapi.Schema(type=openapi.TYPE_STRING, example="Офис"),
                'destination': openapi.Schema(type=openapi.TYPE_STRING, example="Аэропорт"),
                'waiting_time': openapi.Schema(type=openapi.TYPE_INTEGER, example=15),
                'time': openapi.Schema(type=openapi.TYPE_INTEGER, example=40),
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