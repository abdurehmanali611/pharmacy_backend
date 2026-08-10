from django.urls import path

from .views import (
    BillingMeView,
    ResubmitSignupSetupPaymentView,
    SignupRegistrationStatusView,
    SubmitTenantPaymentView,
)

urlpatterns = [
    path("me/", BillingMeView.as_view(), name="billing-me"),
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
]
