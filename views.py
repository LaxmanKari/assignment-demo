from datetime import datetime, timezone

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Document, QueryLog, UserSession
from .pagination import StandardPagination
from .serializers import (
    DocumentSerializer,
    LoginSerializer,
    LogoutSerializer,
    QueryLogSerializer,
    RegisterSerializer,
)

@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(RegisterSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not user:
            return Response(
                {"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        UserSession.objects.create(
            user=user,
            token=refresh["jti"],
            expires_at=datetime.fromtimestamp(refresh["exp"], tz=timezone.utc),
        )
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
            UserSession.objects.filter(token=token["jti"], user=request.user).delete()
        except TokenError:
            return Response(
                {"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class DocumentListCreateView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        queryset = Document.objects.filter(owner=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = DocumentSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = DocumentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    def get(self, request, pk):
        # 404 if it doesn't exist OR belongs to someone else
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        return Response(DocumentSerializer(document, context={"request": request}).data)

    def delete(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if document.owner_id != request.user.id:
            return Response(
                {"detail": "You do not own this document."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if document.file:
            document.file.delete(save=False)  # remove the file from disk too
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QueryView(APIView):
    def post(self, request):
        serializer = QueryLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["query_text"]

        matches = Document.objects.filter(owner=request.user).filter(
            Q(title__icontains=text) | Q(content__icontains=text)
        )
        count = matches.count()
        if count:
            titles = ", ".join(f"'{t}'" for t in matches.values_list("title", flat=True)[:5])
            summary = f"Found {count} matching document(s): {titles}"
        else:
            summary = "No matching documents found."

        serializer.save(user=request.user, result_summary=summary)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QueryHistoryView(APIView):
    def get(self, request):
        queryset = QueryLog.objects.filter(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(QueryLogSerializer(page, many=True).data)