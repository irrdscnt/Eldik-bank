from django.urls import path
from .views import *

urlpatterns = [
    path('users/', UserList.as_view(), name='user-list'),
    path('users/<str:pk>/', UserDetail.as_view(), name='user-detail'),
    path('register/', RegisterUser. as_view()),
    path('confirm/', ConfirmRegistration.as_view()),
    path('login/', LoginView.as_view()),
    path('requests/',RequestList.as_view(),name='request-list'),
    path('requests/<str:pk>/', RequestDetail.as_view(), name='request-detail'),
    path('routes/', RouteList.as_view(), name='route-list'),
    path('routes/<str:pk>/', RouteDetail.as_view(), name='route-detail'),
    path('user/<str:user_id>/frequent-routes/', UserFrequentRoutes.as_view(), name='user-frequent-routes'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('report/', ReportView.as_view(), name='report'),
    path('report/csv/', ReportCSVDownloadView.as_view(), name='report-csv'),
]
