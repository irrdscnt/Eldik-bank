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
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('test-location/', test_location_view, name='test_location'),

    path('report/', ReportView.as_view(), name='report'),
    path('report/csv/', ReportCSVDownloadView.as_view(), name='report-csv'),

    path('cars/', CarListCreateAPIView.as_view(), name='car-list-create'),
    path('cars/<str:pk>/', CarDetailAPIView.as_view(), name='car-detail'),

    path('drivers/', CarUserListCreateAPIView.as_view(), name='car-user-list-create'),
    path('drivers/<str:pk>/', CarUserDetailAPIView.as_view(), name='car-user-detail'),

    path('export-requests-excel/', ExportExcelAPIView.as_view(), name='export-requests-excel'),
    path('export-user-activity-excel/', DownloadUserActivityReport.as_view(), name='export-user-activity-excel'),
]
