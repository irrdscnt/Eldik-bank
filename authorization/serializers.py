from rest_framework import serializers
from authorization.models import *
from bson import ObjectId
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class UserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    subdepartment = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=['user', 'admin', 'driver', 'dispetcher'], default='user')

    def validate(self, data):

        user_role = getattr(self.context['request'].user, 'role', 'user')
        if hasattr(user_role, 'value'):
            user_role = user_role.value

        if 'role' in data and user_role != 'admin':
            raise serializers.ValidationError({"role": "Only admins can change the role."})
        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return User.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.email = validated_data.get('email', instance.email)
        instance.number = validated_data.get('number', instance.number)
        instance.role = validated_data.get('role', instance.role)
        instance.subdepartment = validated_data.get('subdepartment', instance.subdepartment)

        if 'password' in validated_data:
            instance.password = make_password(validated_data['password'])

        if 'email' in validated_data and validated_data['email'] != instance.email:
            if User.objects(email=validated_data['email']).exclude(id=instance.id).first():
                raise serializers.ValidationError({"email": "This email is already in use."})

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['id'] = str(instance.id)
        data['role'] = instance.role.value if instance.role else 'user'
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = self.context['user']
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not check_password(old_password, user.password):
            raise serializers.ValidationError({"old_password": "Incorrect old password."})

        if len(new_password) < 8:
            raise serializers.ValidationError({"new_password": "New password must be at least 8 characters long."})

        if old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password must be different from the old password."})

        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ForgotPasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField()


class ResetPasswordResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
