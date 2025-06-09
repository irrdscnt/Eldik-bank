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
from core.utils import send_push_notification_to_user
from rest_framework.pagination import LimitOffsetPagination


class UnlimitedPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None


class UserList(APIView):
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получает список всех пользователей (исключая администраторов).",
        manual_parameters=[
            openapi.Parameter('limit', openapi.IN_QUERY,
                              description="Количество элементов на странице",
                              type=openapi.TYPE_INTEGER),
            openapi.Parameter('offset', openapi.IN_QUERY,
                              description="Смещение от начала списка",
                              type=openapi.TYPE_INTEGER),
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
        print(f"Checking permissions: user_id={request.user.id}, role={user_role}, target_user_id={pk}")

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
        print(f"Checking permissions: user_id={request.user.id}, role={user_role}, target_user_id={pk}")

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
        print(f"Checking permissions for delete: user_id={request.user.id}, role={user_role}")

        if user_role != 'admin':
            return Response({"detail": "Only admins can delete users."}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(id=ObjectId(pk))
            user.delete()
            return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except (User.DoesNotExist, ObjectId.InvalidId):
            return Response({"detail": "User not found or invalid ID."}, status=status.HTTP_404_NOT_FOUND)


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


from mongoengine import Document, StringField, BooleanField


class EmailVerification(Document):
    email = StringField(required=True)
    code = StringField(required=True)
    is_verified = BooleanField(default=False)

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


class RequestCreateView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={

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


class RequestListView(GenericAPIView):
    serializer_class = RequestSerializer
    queryset = Request.objects.all()
    pagination_class = UnlimitedPagination

    @swagger_auto_schema(
        operation_description="Получить список всех заявок с пагинацией",
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
                description="Пагинированный список заявок",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Общее количество заявок"),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу"),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу"),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT, description="Данные заявки")
                        )
                    }
                )
            )
        }
    )
    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RequestDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Request.objects.get(id=ObjectId(pk))
        except (Request.DoesNotExist, ObjectId.InvalidId):
            return None

    def send_status_notification(self, request_obj, new_status):
        status_choices = dict(Request.STATUS_CHOICES)
        status_text = status_choices.get(new_status, "Unknown")

        if new_status == 2:
            title = "Заявка одобрена"
            body = f"Ваша заявка от {request_obj.date} была одобрена."
        elif new_status == 3:
            title = "Заявка отклонена"
            body = f"Ваша заявка от {request_obj.date} была отклонена. Причина: {request_obj.comments or 'Не указана'}."
        else:
            return

        send_push_notification_to_user(request_obj.user, title, body)

    @swagger_auto_schema(
        operation_description="Получить информацию о заявке по ID",
        responses={
            200: RequestSerializer,
            404: "Заявка не найдена"
        }
    )
    def get(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestSerializer(request_obj)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Полностью обновить заявку по ID (диспетчеры могут менять только статус и комментарии, админы — все поля)",
        request_body=RequestSerializer,
        responses={
            200: RequestSerializer,
            400: "Неверные данные",
            403: "Нет прав на изменение",
            404: "Заявка не найдена"
        }
    )
    def put(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value
        print(f"Checking permissions: user_id={request.user.id}, role={user_role}, request_id={pk}")

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
        operation_description="Частично обновить заявку по ID (диспетчеры могут менять только статус и комментарии, админы — все поля)",
        request_body=RequestSerializer,
        responses={
            200: RequestSerializer,
            400: "Неверные данные",
            403: "Нет прав на изменение",
            404: "Заявка не найдена"
        }
    )
    def patch(self, request, pk):
        request_obj = self.get_object(pk)
        if request_obj is None:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)

        user_role = getattr(request.user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value
        print(f"Checking permissions: user_id={request.user.id}, role={user_role}, request_id={pk}")

        if user_role not in ['dispetcher', 'admin'] and str(request_obj.user.id) != str(request.user.id):
            return Response({"detail": "You do not have permission to update this request."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = RequestSerializer(request_obj, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            if 'status' in request.data:
                self.send_status_notification(request_obj, request.data['status'])
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RouteList(APIView):
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
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'next': openapi.Schema(type=openapi.TYPE_STRING),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(
                                type=openapi.TYPE_OBJECT,

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

        if page is not None:
            serializer = RouteSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

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

        existing_routes = Route.objects(departure=departure, destination=destination)

        usage_count = existing_routes.count() + 1

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
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'next': openapi.Schema(type=openapi.TYPE_STRING),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING),
                                    'departure': openapi.Schema(type=openapi.TYPE_STRING),
                                    'destination': openapi.Schema(type=openapi.TYPE_STRING),
                                    'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'is_frequent': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                }
                            )
                        )
                    }
                )
            ),
            400: "Неверный формат ID пользователя",
            404: "Пользователь не найден",
            500: "Внутренняя ошибка сервера"
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


class FrequentRoutesView(APIView):
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
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description="Ссылка на следующую страницу"),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING,
                                                   description="Ссылка на предыдущую страницу"),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_STRING),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'usage_count': openapi.Schema(type=openapi.TYPE_INTEGER),

                                }
                            )
                        )
                    }
                )
            ),
            400: "Неверные параметры запроса"
        }
    )
    def get(self, request):
        min_usage = int(request.query_params.get('min_usage', 5))

        routes = Route.objects(usage_count__gt=min_usage).order_by('-usage_count')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(routes, request)

        if page is not None:
            serializer = RouteSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = RouteSerializer(routes, many=True)
        return Response(serializer.data)


class CarListCreateAPIView(APIView):
    pagination_class = UnlimitedPagination

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


class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Сохранить FCM-токен для пуш-уведомлений",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['fcm_token'],
            properties={
                'fcm_token': openapi.Schema(type=openapi.TYPE_STRING, description="FCM Device Token"),
            }
        ),
        responses={
            200: openapi.Response(description="FCM token saved successfully"),
            400: "Invalid data",
        }
    )
    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response({"detail": "FCM token is required."}, status=status.HTTP_400_BAD_REQUEST)

        DeviceToken.objects.create(user=request.user, fcm_token=fcm_token)
        return Response({"detail": "FCM token saved successfully."}, status=status.HTTP_200_OK)
