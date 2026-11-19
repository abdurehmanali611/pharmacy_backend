import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import UserProfile
from .passwords import TAKEN_MESSAGE, agent_password_taken, password_fingerprint, store_fingerprint
from .serializers import (
    BulkSalesAgentSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    UserSerializer,
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        pharmacy_tin = getattr(user.profile, "pharmacy_tin", "")
        return super().get_queryset().filter(profile__pharmacy_tin=pharmacy_tin)

    def perform_create(self, serializer):
        if self.request.user.is_authenticated and self.request.user.profile.role.lower() == "manager":
            serializer.save(pharmacy_tin=self.request.user.profile.pharmacy_tin)
        else:
            serializer.save()

    @action(detail=False, methods=["post"], url_path="bulk_create", permission_classes=[permissions.IsAuthenticated])
    def bulk_create(self, request):
        """Create sales agents (pharmacists) that all sign in with one shared username."""
        manager_profile = getattr(request.user, "profile", None)
        if not manager_profile or (manager_profile.role or "").lower() != "manager":
            raise PermissionDenied("Only a manager can create sales agents.")

        serializer = BulkSalesAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]
        typed = (serializer.validated_data.get("username") or "").strip()

        tin = manager_profile.pharmacy_tin
        existing = list(
            UserProfile.objects.filter(pharmacy_tin=tin, role__iexact="pharmacist").select_related("user")
        )

        # Once agents exist, their shared username is fixed for good.
        saved = next((p.login_name or p.user.username for p in existing), "")
        username = saved or typed
        if not username:
            raise ValidationError({"username": ["Enter the username your sales team will sign in with."]})
        if " " in username:
            raise ValidationError({"username": ["Username cannot contain spaces."]})
        if saved and typed and typed.lower() != saved.lower():
            raise ValidationError(
                {"username": [f"The sales username is already '{saved}'. Delete all sales agents to use a new one."]}
            )

        if not saved:
            clash = (
                User.objects.filter(username__iexact=username).exists()
                or UserProfile.objects.filter(login_name__iexact=username).exists()
            )
            if clash:
                raise ValidationError({"username": ["This username is already taken."]})

        # The password is what tells agents apart, so no two can share one.
        passwords = [item["password"] for item in items]
        if len(set(passwords)) != len(passwords):
            raise ValidationError({"items": ["Each sales agent needs a different password."]})
        # Unique across every pharmacy on the platform, not just this one.
        for pw in passwords:
            if agent_password_taken(pw):
                raise ValidationError({"items": [TAKEN_MESSAGE]})

        created = []
        with transaction.atomic():
            for item in items:
                user = User(username=f"{username}#{uuid.uuid4().hex[:8]}")
                user.set_password(item["password"])
                user.save()
                UserProfile.objects.create(
                    user=user,
                    full_name=item["full_name"],
                    login_name=username,
                    role="pharmacist",
                    pharmacy_name=manager_profile.pharmacy_name,
                    logoUrl=manager_profile.logoUrl,
                    pharmacy_tin=tin,
                    password_fingerprint=password_fingerprint(item["password"]),
                )
                created.append(user)
        return Response(UserSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        password = serializer.validated_data.get("password")
        instance = serializer.instance
        profile = getattr(instance, "profile", None)
        is_agent = bool(profile and (profile.role or "").lower() == "pharmacist")
        if password and is_agent and agent_password_taken(password, exclude_user=instance):
            raise ValidationError({"password": [TAKEN_MESSAGE]})
        serializer.save()
        if password and is_agent:
            store_fingerprint(instance, password)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(old_password):
            return Response(
                {"old_password": ["Old password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = getattr(user, "profile", None)
        is_agent = bool(profile and (profile.role or "").lower() == "pharmacist")
        if is_agent and agent_password_taken(new_password, exclude_user=user):
            return Response({"new_password": [TAKEN_MESSAGE]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        if is_agent:
            store_fingerprint(user, new_password)
        return Response({"detail": "Password updated successfully."})


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
