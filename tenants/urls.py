from django.urls import path

from .tenant_ops_views import (
    RequestModuleChangeView,
    SendTenantFeedbackView,
    TenantFeedbackInboxView,
    TenantModulesMeView,
)
from .views import (
    BillingMeView,
    PublicPricingView,
    ResubmitSignupSetupPaymentView,
    SignupRegistrationStatusView,
    SubmitTenantPaymentView,
)

urlpatterns = [
    path("me/", BillingMeView.as_view(), name="billing-me"),
    path("pricing/", PublicPricingView.as_view(), name="billing-pricing"),
    path("submit-payment/", SubmitTenantPaymentView.as_view(), name="billing-submit"),
    path(
        "signup-status/",
        SignupRegistrationStatusView.as_view(),
        name="billing-signup-status",
    ),
    path(
        "resubmit-setup/",
        ResubmitSignupSetupPaymentView.as_view(),
        name="billing-resubmit-setup",
    ),
    path("modules/me/", TenantModulesMeView.as_view(), name="modules-me"),
    path("modules/request/", RequestModuleChangeView.as_view(), name="modules-request"),
    path("feedback/inbox/", TenantFeedbackInboxView.as_view(), name="feedback-inbox"),
    path("feedback/send/", SendTenantFeedbackView.as_view(), name="feedback-send"),
]
