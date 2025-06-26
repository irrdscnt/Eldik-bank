from django.urls import path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from .views import *
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

schema_view = get_schema_view(
    openapi.Info(
        title="Car Rental API",
        default_version='v1',
        description="API для аренды автомобилей",
    ),
    public=True,
)

urlpatterns = [
    path('register/', RegisterUser.as_view()),
    path('confirm/', ConfirmRegistration.as_view()),
    path('login/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('users/', UserList.as_view(), name='user-list'),
    path('users/<str:pk>/', UserDetail.as_view(), name='user-detail'),
    path('users/<str:pk>/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
