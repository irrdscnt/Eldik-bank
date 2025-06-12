from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from bson import ObjectId  # Import bson
from core_requests.models import *
from rest_framework_simplejwt.settings import api_settings


class MongoJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
            user = User.objects.get(id=ObjectId(user_id))
            return user
        except (User.DoesNotExist, ObjectId.InvalidId):
            raise InvalidToken("User not found or invalid user ID.")
