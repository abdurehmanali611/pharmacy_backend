from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import MedicineViewSet

router = DefaultRouter()
router.register(r"", MedicineViewSet, basename="medicine")

urlpatterns = [
    path("", include(router.urls)),
]