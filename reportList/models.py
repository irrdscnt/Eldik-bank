from django.db import models
from django.shortcuts import render
from django.http import HttpResponse
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime, timezone


class DocumentNumber(Document):
    document_number = StringField(max_length=10, unique=True, required=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    meta = {'collection': 'document_numbers'}
