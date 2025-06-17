from bson.errors import InvalidId
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from authorization.models import *
from authorization.serializers import *
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
from django.shortcuts import render
from mongoengine import Document, StringField, BooleanField


class UnlimitedPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None


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
                'subdepartment': openapi.Schema(type=openapi.TYPE_STRING, description="Subdepartment of the user"),
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
            password=make_password(data['password']),
            subdepartment=data.get('subdepartment')
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


class EmailVerification(Document):
    email = StringField(required=True)
    code = StringField(required=True)
    is_verified = BooleanField(default=False)

    name = StringField()
    number = StringField()
    password = StringField()
    subdepartment = StringField()
    is_reset = BooleanField(default=False)

    def generate_code(self):
        import random
        self.code = str(random.randint(100000, 999999))


class ConfirmRegistration(APIView):
    @swagger_auto_schema(
        operation_description="Подтверждает регистрацию по коду, отправленному на email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'code'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email'),
                'code': openapi.Schema(type=openapi.TYPE_STRING),
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
                        'subdepartment': openapi.Schema(type=openapi.TYPE_STRING),
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
        print(f"✅ Получено подтверждение: email={email}, code={code}", flush=True)

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
            role=Role.USER,
            subdepartment=verification.subdepartment
        )
        user.save()
        print(f" Пользователь создан: {user.email}, subdepartment={user.subdepartment}", flush=True)

        verification.is_verified = True
        verification.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role.value,
                'subdepartment': user.subdepartment
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
                        'subdepartment': openapi.Schema(type=openapi.TYPE_STRING),
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

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role.value,
                'subdepartment': user.subdepartment
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


class UserList(APIView):
    pagination_class = UnlimitedPagination
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получает список всех пользователей (исключая администраторов).",
        manual_parameters=[
            openapi.Parameter('limit', openapi.IN_QUERY,
                              description="Количество элементов на странице",
                              type=openapi.TYPE_INTEGER),
            openapi.Parameter('offset', openapi.IN_QUERY,
                              description="Смещение от начала списка",
                              type=openapi.TYPE_INTEGER),
            openapi.Parameter('name', openapi.IN_QUERY,
                              description="Фильтрация по имени (регистронезависимый поиск)",
                              type=openapi.TYPE_STRING),
            openapi.Parameter('email', openapi.IN_QUERY,
                              description="Фильтрация по email (регистронезависимый поиск)",
                              type=openapi.TYPE_STRING),
            openapi.Parameter('role', openapi.IN_QUERY,
                              description="Фильтрация по роли",
                              type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Пагинированный список пользователей",
                schema=UserSerializer(many=True)
            ),
            400: "Неверные параметры пагинации"
        }
    )
    def get(self, request):
        users = User.objects.filter(role__ne=Role.ADMIN)

        name = request.query_params.get('name')
        if name:
            users = users.filter(name__icontains=name)

        email = request.query_params.get('email')
        if email:
            users = users.filter(email__icontains=email)

        role = request.query_params.get('role')
        if role:
            users = users.filter(role=role)

        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(users, request)
        serializer = UserSerializer(result_page, many=True)

        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Создает нового пользователя (только для админа).",
        request_body=UserSerializer,
        responses={
            201: UserSerializer,
            400: 'Ошибка валидации данных'
        }
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetail(APIView):
    permission_classes = [IsAuthenticated]

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

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if str(user.id) != str(request.user.id) and user_role != 'admin':
            return Response({"detail": "You do not have permission to update this user."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(user, data=request.data, context={'request': request})
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

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if str(user.id) != str(request.user.id) and user_role != 'admin':
            return Response({"detail": "You do not have permission to update this user."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
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

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if user_role != 'admin':
            return Response({"detail": "Only admins can delete users."}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(id=ObjectId(pk))
            user.delete()
            return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except (User.DoesNotExist, ObjectId.InvalidId):
            return Response({"detail": "User not found or invalid ID."}, status=status.HTTP_404_NOT_FOUND)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Сменить пароль пользователя по ID (только для самого пользователя)",
        request_body=ChangePasswordSerializer,
        responses={
            200: openapi.Response("Пароль успешно изменён"),
            400: "Неверные данные или старый пароль",
            403: "Нет прав на изменение",
            404: "Пользователь не найден"
        }
    )
    def post(self, request, pk):
        try:
            user = User.objects.get(id=ObjectId(pk))
        except (User.DoesNotExist, ObjectId.InvalidId):
            return Response({"detail": "User not found or invalid ID."}, status=status.HTTP_404_NOT_FOUND)

        if str(user.id) != str(request.user.id):
            return Response({"detail": "You do not have permission to change this user's password."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = ChangePasswordSerializer(data=request.data, context={'user': user})
        if serializer.is_valid():
            user.password = make_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
