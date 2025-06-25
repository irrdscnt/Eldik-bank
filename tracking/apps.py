from django.apps import AppConfig
import os

class TrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracking'
    path = os.path.dirname(os.path.abspath(__file__))  
