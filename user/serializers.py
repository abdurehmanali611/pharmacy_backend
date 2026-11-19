from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

from tenants.billing import (
    PAYMENT_CHANNELS,
    billing_snapshot,
    catalog_default_fees,
    create_payment_submission,
    resolve_login_access,
)
from tenants.models import TenantAccount
from tenants.services import ensure_tenant_account

from .models import UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(allow_blank=True, required=False, max_length=255)
    pharmacy_name = serializers.CharField(allow_blank=True, required=False)
    role = serializers.CharField(allow_blank=True, required=False)
    logoUrl = serializers.CharField(allow_blank=True, required=False)
    pharmacy_tin = serializers.CharField(allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    payment_channel = serializers.CharField(write_only=True, required=False, allow_blank=True)
    payment_transaction_ref = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    sales_agent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "full_name",
            "pharmacy_name",
            "role",
            "logoUrl",
            "pharmacy_tin",
            "payment_channel",
            "payment_transaction_ref",
            "sales_agent_id",
        ]

    def validate_username(self, value):
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Username is required.")

        # Sales agents share one username; it can be changed here and the view applies the
        # change to every agent of the pharmacy.
        if self.instance is not None:
            profile = getattr(self.instance, "profile", None)
            if profile and profile.login_name:
                if " " in username:
                    raise serializers.ValidationError("Username cannot contain spaces.")
                same_team = UserProfile.objects.filter(
                    pharmacy_tin=profile.pharmacy_tin, role__iexact="pharmacist"
                ).values_list("user_id", flat=True)
                clash = (
                    User.objects.filter(username__iexact=username).exclude(pk__in=same_team).exists()
                    or UserProfile.objects.filter(login_name__iexact=username).exclude(user_id__in=same_team).exists()
                )
                if clash:
                    raise serializers.ValidationError("This username is already taken.")
                return username

        qs = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")

        return username

    def validate(self, attrs):
        request = self.context.get("request")
        role = (attrs.get("role") or "").strip().lower()
        is_self_signup = not (request and getattr(request.user, "is_authenticated", False))

        if is_self_signup and role == "manager":
            channel = (attrs.get("payment_channel") or "").strip()
            ref = (attrs.get("payment_transaction_ref") or "").strip()
            setup_fee = int(catalog_default_fees().get("setup_fee_etb") or 0)
            if setup_fee > 0:
                if channel not in PAYMENT_CHANNELS:
                    raise serializers.ValidationError(
                        {"payment_channel": ["Select Telebirr or Commercial Bank of Ethiopia."]}
                    )
                if len(ref) < 4:
                    raise serializers.ValidationError(
                        {"payment_transaction_ref": ["Transfer ID must be at least 4 characters."]}
                    )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "profile", None)
        if profile and profile.login_name:
            data["username"] = profile.login_name
        if profile:
            data["full_name"] = profile.full_name
            data["pharmacy_name"] = profile.pharmacy_name
            data["role"] = profile.role
            data["logoUrl"] = profile.logoUrl
            data["pharmacy_tin"] = profile.pharmacy_tin
        else:
            data["full_name"] = ""
            data["pharmacy_name"] = ""
            data["role"] = ""
            data["logoUrl"] = ""
            data["pharmacy_tin"] = ""
        return data

    def create(self, validated_data):
        payment_channel = (validated_data.pop("payment_channel", "") or "").strip()
        payment_transaction_ref = (validated_data.pop("payment_transaction_ref", "") or "").strip()
        sales_agent_id = validated_data.pop("sales_agent_id", None)
        profile_data = {
            "full_name": (validated_data.pop("full_name", "") or "").strip(),
            "pharmacy_name": validated_data.pop("pharmacy_name", ""),
            "role": validated_data.pop("role", ""),
            "logoUrl": validated_data.pop("logoUrl", ""),
            "pharmacy_tin": validated_data.pop("pharmacy_tin", ""),
        }
        password = validated_data.pop("password", None)

        role = (profile_data.get("role") or "").strip().lower()
        pharmacy_tin = (profile_data.get("pharmacy_tin") or "").strip()
        if role == "manager" and pharmacy_tin:
            if TenantAccount.objects.filter(pharmacy_tin=pharmacy_tin).exists():
                raise serializers.ValidationError(
                    {"pharmacy_tin": ["A pharmacy with this TIN is already registered."]}
                )

        if role == "pharmacist" and password:
            from .passwords import TAKEN_MESSAGE, agent_password_taken

            if agent_password_taken(password):
                raise serializers.ValidationError({"password": [TAKEN_MESSAGE]})

        user = User(username=validated_data["username"])
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        profile = UserProfile.objects.create(user=user, **profile_data)
        if role == "pharmacist" and password:
            from .passwords import password_fingerprint

            profile.password_fingerprint = password_fingerprint(password)
            profile.save(update_fields=["password_fingerprint"])

        request = self.context.get("request")
        is_self_signup = not (request and getattr(request.user, "is_authenticated", False))

        if pharmacy_tin and role == "manager":
            from tenants.sales_agents import resolve_sales_agent

            agent = resolve_sales_agent(sales_agent_id) if is_self_signup else None
            tenant = ensure_tenant_account(
                pharmacy_tin=pharmacy_tin,
                pharmacy_name=profile_data.get("pharmacy_name", ""),
                logo_url=profile_data.get("logoUrl", ""),
                sales_agent=agent,
            )
            if tenant and is_self_signup and payment_channel and payment_transaction_ref:
                create_payment_submission(
                    tenant=tenant,
                    payment_kind="setup",
                    payment_channel=payment_channel,
                    transaction_ref=payment_transaction_ref,
                    submitted_by=user,
                )

        return user

    def update(self, instance, validated_data):
        validated_data.pop("payment_channel", None)
        validated_data.pop("payment_transaction_ref", None)
        validated_data.pop("sales_agent_id", None)
        profile_data = {
            "full_name": validated_data.pop("full_name", None),
            "pharmacy_name": validated_data.pop("pharmacy_name", None),
            "role": validated_data.pop("role", None),
            "logoUrl": validated_data.pop("logoUrl", None),
            "pharmacy_tin": validated_data.pop("pharmacy_tin", None),
        }
        password = validated_data.pop("password", None)

        existing_profile = getattr(instance, "profile", None)
        new_login = None
        if existing_profile and existing_profile.login_name:
            # Shared agent username: stored on the profile; the view copies it to the whole team.
            new_login = validated_data.get("username")
        else:
            instance.username = validated_data.get("username", instance.username)
        if password:
            instance.set_password(password)
        instance.save()

        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if new_login and new_login != profile.login_name:
            UserProfile.objects.filter(
                pharmacy_tin=profile.pharmacy_tin, role__iexact="pharmacist"
            ).exclude(login_name="").update(login_name=new_login)
            profile.login_name = new_login
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


class SalesAgentItemSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(min_length=2, write_only=True)

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name is required.")
        return value


class BulkSalesAgentSerializer(serializers.Serializer):
    # One username for the whole sales team; each agent's own password identifies them.
    username = serializers.CharField(max_length=120, required=False, allow_blank=True)
    items = SalesAgentItemSerializer(many=True, allow_empty=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


def resolve_shared_login(username, password):
    """Map a shared sales username + personal password to the one agent that owns that password."""
    username = (username or "").strip()
    if not username or not password:
        return None
    profiles = UserProfile.objects.filter(role__iexact="pharmacist").select_related("user")
    for profile in profiles:
        shown = profile.login_name or profile.user.username
        if shown.lower() == username.lower() and profile.user.is_active and profile.user.check_password(password):
            return profile.user
    return None


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        agent = resolve_shared_login(attrs.get("username"), attrs.get("password"))
        if agent is not None:
            attrs["username"] = agent.get_username()
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
