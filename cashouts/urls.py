from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CashoutViewSet

router = DefaultRouter()
router.register(r"", CashoutViewSet, basename="cashout")

urlpatterns = [
    path("", include(router.urls)),
]

