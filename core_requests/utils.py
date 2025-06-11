import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from core_requests.models import DeviceToken

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
    firebase_admin.initialize_app(cred)


def send_push_notification_to_user(user, title, body):
    device_token = DeviceToken.objects(user=user).first()
    if not device_token:
        print(f"No FCM token found for user {user.email}")
        return

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=device_token.fcm_token,
    )
    try:
        response = messaging.send(message)
        print(f"Notification sent to {device_token.fcm_token}: {response}")
    except Exception as e:
        print(f"Error sending notification to {user.email}: {str(e)}")
