from django.urls import path

from .views import BillingMeView, SubmitTenantPaymentView

urlpatterns = [
    path("me/", BillingMeView.as_view(), name="billing-me"),
    path("submit-payment/", SubmitTenantPaymentView.as_view(), name="billing-submit"),
]
