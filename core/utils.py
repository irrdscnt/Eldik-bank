import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from core.models import DeviceToken


if not firebase_admin._apps:
    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
    firebase_admin.initialize_app(cred)

def send_push_notification_to_user(user, title, body):
    tokens = DeviceToken.objects(user=user)
    for token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=token.fcm_token,
            )
            response = messaging.send(message)
            print(f"Notification sent to {token.fcm_token}: {response}")
        except Exception as e:
            print(f"Failed to send notification to {token.fcm_token}: {str(e)}")