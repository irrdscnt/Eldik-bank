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
    path('fast-requests/', FastRequestListView.as_view(), name='fast-request-list'),
    path('save-fcm-token/', SaveFCMTokenView.as_view(), name='save-fcm-token'),

    path('trips/export/', trip_report_export, name='trip-report-export'),
    path('trips/', TripCreateAPIView.as_view(), name='trip-create'),
    path('trips/<str:pk>/', TripDetailAPIView.as_view(), name='trip-detail'),
    path('users/<str:user_id>/trips/', UserTripsView.as_view(), name='user-trips'),

    path('routes/', RouteList.as_view(), name='route-list'),
    path('routes/create/', CreateRouteWithRequestView.as_view(), name="create-route-with-request"),
    path('routes/frequent/', FrequentRoutesView.as_view(), name='frequent-routes'),
    path('routes/<str:pk>/', RouteDetail.as_view(), name='route-detail'),
    path('user/<str:user_id>/frequent-routes/', UserFrequentRoutes.as_view(), name='user-frequent-routes'),

    path('requests/<str:pk>/assign-driver/', AssignDriverToRequestView.as_view(), name='assign-driver'),
    path('requests/user/<user_id>/', UserRequestListView.as_view(), name='user-request-list'),
    path('requests/create/', RequestCreateView.as_view(), name='request-create'),
    path('requests/<str:pk>/', RequestDetail.as_view(), name='request-detail'),
    path('requests/<str:request_id>/routes/<str:route_id>/time', RouteTimeUpdate.as_view(), name='route-time-update'),
]
