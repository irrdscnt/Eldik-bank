import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import tracking.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_rental_bank.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            tracking.routing.websocket_urlpatterns
        )
    ),
})
