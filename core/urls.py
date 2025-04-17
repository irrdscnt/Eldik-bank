from django.urls import path
from .views import *

urlpatterns = [
    path('users/', UserList.as_view(), name='user-list'),
    path('users/<str:pk>/', UserDetail.as_view(), name='user-detail'),
    path('requests/',RequestList.as_view(),name='request-list'),
    path('requests/<str:pk>/', RequestDetail.as_view(), name='request-detail'),

]
