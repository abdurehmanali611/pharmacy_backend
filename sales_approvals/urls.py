from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalRequiredMedicineViewSet,
    PendingSaleViewSet,
    QuantitySaleRuleViewSet,
)

router = DefaultRouter()
router.register(r"quantity-rules", QuantitySaleRuleViewSet, basename="quantity-sale-rule")
router.register(
    r"approval-required",
    ApprovalRequiredMedicineViewSet,
    basename="approval-required-medicine",
)
router.register(r"pending-sales", PendingSaleViewSet, basename="pending-sale")

urlpatterns = [
    path("", include(router.urls)),
]
