from django.urls import path
from .views import *

urlpatterns = [
    path('users/', UserList.as_view(), name='user-list'),
    path('users/<str:pk>/', UserDetail.as_view(), name='user-detail'),
    path('register/', RegisterUser. as_view()),
    path('confirm/', ConfirmRegistration.as_view()),
    path('login/', LoginView.as_view()),
    path('requests/', RequestListView.as_view(), name='request-list'),
    path('requests/create/', RequestCreateView.as_view(), name='request-create'),
    # path('requests/<str:pk>/update-status/', RequestStatusUpdateView.as_view(), name='request-status-update'),
    path('requests/<str:pk>/', RequestDetail.as_view(), name='request-detail'),
    path('routes/', RouteList.as_view(), name='route-list'),
    path('routes/create/', CreateRouteWithRequestView.as_view(), name="create-route-with-request"),
    path('routes/frequent/', FrequentRoutesView.as_view(), name='frequent-routes'),
    path('routes/<str:pk>/', RouteDetail.as_view(), name='route-detail'),
    path('user/<str:user_id>/frequent-routes/', UserFrequentRoutes.as_view(), name='user-frequent-routes'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('report/', ReportView.as_view(), name='report'),
    path('report/csv/', ReportCSVDownloadView.as_view(), name='report-csv'),
    path('cars/', CarListCreateAPIView.as_view(), name='car-list-create'),
    path('cars/<str:pk>/', CarDetailAPIView.as_view(), name='car-detail'),
    path('drivers/', CarUserListCreateAPIView.as_view(), name='car-user-list-create'),
    path('drivers/<str:pk>/', CarUserDetailAPIView.as_view(), name='car-user-detail'),
    path('trips/', TripCreateAPIView.as_view(), name='trip-create'),
    path('trips/<str:pk>/', TripDetailAPIView.as_view(), name='trip-detail'),
]
