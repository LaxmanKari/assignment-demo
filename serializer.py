from pathlib import Path

from django.contrib.auth import get_user_model
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import Document, QueryLog

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class FileTooLarge(APIException):
    status_code = 413
    default_detail = "File too large. Maximum size is 5 MB."
    default_code = "file_too_large"


def extract_text(file):
    """Read text out of an uploaded .txt/.md/.pdf file."""
    ext = Path(file.name).suffix.lower()
    try:
        if ext == ".pdf":
            reader = PdfReader(file)
            return "\n".join(
                (page.extract_text() or "") for page in reader.pages
            ).strip()
        return file.read().decode("utf-8", errors="ignore").strip()
    except PyPdfError:
        raise serializers.ValidationError({"file": "Could not read this PDF."})
    finally:
        file.seek(0)  # rewind so Django can still save the file


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "content", "uploaded_at", "owner"]
        read_only_fields = ["owner", "uploaded_at"]
        extra_kwargs = {
            "title": {"required": False},
            "content": {"required": False},
        }

    def validate(self, attrs):
        title = (attrs.get("title") or "").strip()
        content = (attrs.get("content") or "").strip()

        if not title:
            raise serializers.ValidationError({"title": "This field is required."})
        if not content:
            raise serializers.ValidationError({"content": "This field is required."})

        attrs["title"] = title
        attrs["content"] = content
        return attrs


class QueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryLog
        fields = ["id", "query_text", "result_summary", "created_at", "user"]
        read_only_fields = ["result_summary", "created_at", "user"]

    def validate_query_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("query_text cannot be empty.")
        return value
