from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from ..exceptions import PayloadTooLarge
from ..models import Document
from ..utils import extract_text


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Document
        fields = ["id", "title", "content", "file", "uploaded_at", "owner"]
        read_only_fields = ["id", "owner", "uploaded_at"]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "content": {"required": False, "allow_blank": True},
        }

    def validate_file(self, f):
        ext = Path(f.name).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise serializers.ValidationError(f"Unsupported file type. Allowed: {allowed}")

        if f.size > settings.MAX_UPLOAD_SIZE:
            raise PayloadTooLarge(
                f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit."
            )

        head = f.read(4)
        f.seek(0)
        if ext == ".pdf" and head != b"%PDF":
            raise serializers.ValidationError("File is not a valid PDF.")
        if ext == ".docx" and head[:2] != b"PK":
            raise serializers.ValidationError("File is not a valid DOCX.")
        return f

    def validate(self, attrs):
        f = attrs.get("file")
        title = (attrs.get("title") or "").strip()
        content = (attrs.get("content") or "").strip()

        if not f and not content:
            raise serializers.ValidationError("Provide either a file or content.")

        if not title:
            if f:
                title = Path(f.name).name[:255]  # default to the filename
            else:
                raise serializers.ValidationError({"title": "This field is required."})

        if not content and f:
            content = extract_text(f)  # default to the file's text

        attrs["title"] = title
        attrs["content"] = content
        return attrs

    def create(self, validated_data):
        validated_data.pop("file", None)  # only the text is stored
        return super().create(validated_data)