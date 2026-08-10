from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

from tenants.billing import billing_snapshot, resolve_login_access
from tenants.models import TenantAccount
from tenants.services import ensure_tenant_account

from .models import UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.CharField(allow_blank=True, required=False)
    role = serializers.CharField(allow_blank=True, required=False)
    logoUrl = serializers.CharField(allow_blank=True, required=False)
    pharmacy_tin = serializers.CharField(allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "pharmacy_name",
            "role",
            "logoUrl",
            "pharmacy_tin",
        ]

    def validate_username(self, value):
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Username is required.")

        qs = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")

        return username

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "profile", None)
        if profile:
            data["pharmacy_name"] = profile.pharmacy_name
            data["role"] = profile.role
            data["logoUrl"] = profile.logoUrl
            data["pharmacy_tin"] = profile.pharmacy_tin
        else:
            data["pharmacy_name"] = ""
            data["role"] = ""
            data["logoUrl"] = ""
            data["pharmacy_tin"] = ""
        return data

    def create(self, validated_data):
        profile_data = {
            "pharmacy_name": validated_data.pop("pharmacy_name", ""),
            "role": validated_data.pop("role", ""),
            "logoUrl": validated_data.pop("logoUrl", ""),
            "pharmacy_tin": validated_data.pop("pharmacy_tin", ""),
        }
        password = validated_data.pop("password", None)

        role = (profile_data.get("role") or "").strip().lower()
        pharmacy_tin = (profile_data.get("pharmacy_tin") or "").strip()
        if role == "pharmacist" and pharmacy_tin:
            existing_pharmacist = UserProfile.objects.filter(
                pharmacy_tin=pharmacy_tin,
                role__iexact="pharmacist",
            ).exists()
            if existing_pharmacist:
                raise serializers.ValidationError(
                    {
                        "role": [
                            "Only one pharmacist account is allowed per pharmacy. Delete the existing pharmacist to create a new one."
                        ]
                    }
                )

        user = User(username=validated_data["username"])
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        UserProfile.objects.create(user=user, **profile_data)

        if pharmacy_tin and role == "manager":
            ensure_tenant_account(
                pharmacy_tin=pharmacy_tin,
                pharmacy_name=profile_data.get("pharmacy_name", ""),
                logo_url=profile_data.get("logoUrl", ""),
            )

        return user

    def update(self, instance, validated_data):
        profile_data = {
            "pharmacy_name": validated_data.pop("pharmacy_name", None),
            "role": validated_data.pop("role", None),
            "logoUrl": validated_data.pop("logoUrl", None),
            "pharmacy_tin": validated_data.pop("pharmacy_tin", None),
        }
        password = validated_data.pop("password", None)

        instance.username = validated_data.get("username", instance.username)
        if password:
            instance.set_password(password)
        instance.save()

        profile, _ = UserProfile.objects.get_or_create(user=instance)
        for attr, value in profile_data.items():
            if value is not None:
                setattr(profile, attr, value)
        profile.save()

        if profile.pharmacy_tin and (profile.role or "").strip().lower() == "manager":
            ensure_tenant_account(
                pharmacy_tin=profile.pharmacy_tin,
                pharmacy_name=profile.pharmacy_name,
                logo_url=profile.logoUrl,
            )

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        profile = getattr(self.user, "profile", None)
        tin = getattr(profile, "pharmacy_tin", "") if profile else ""
        role = getattr(profile, "role", "") if profile else ""

        access_mode = "full"
        payment_kind = None
        period_status = "active"
        billing = None

        if tin:
            tenant = TenantAccount.objects.filter(pharmacy_tin=tin).first()
            if tenant is None:
                tenant = ensure_tenant_account(
                    pharmacy_tin=tin,
                    pharmacy_name=getattr(profile, "pharmacy_name", ""),
                    logo_url=getattr(profile, "logoUrl", ""),
                )

            if tenant is not None:
                if tenant.account_status == TenantAccount.STATUS_SUSPENDED:
                    raise AuthenticationFailed(
                        "This pharmacy account is suspended. Contact Apex support."
                    )
                if tenant.account_status == TenantAccount.STATUS_BANNED:
                    raise AuthenticationFailed(
                        "This pharmacy account is banned. Contact Apex support."
                    )
                if tenant.account_status == TenantAccount.STATUS_DELETED:
                    raise AuthenticationFailed(
                        "This pharmacy account is no longer available."
                    )

                decision = resolve_login_access(tenant, role=role)
                access_mode = decision.access_mode
                payment_kind = decision.payment_kind
                period_status = decision.period_status
                billing = billing_snapshot(tenant)

                if decision.access_mode == "denied":
                    raise AuthenticationFailed(decision.detail or "Access denied.")

        data["user"] = UserSerializer(self.user).data
        data["access_mode"] = access_mode
        data["payment_kind"] = payment_kind
        data["period_status"] = period_status
        data["billing"] = billing
        return data
