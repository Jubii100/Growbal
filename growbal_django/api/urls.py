from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views import ServiceProviderProfileViewSet
from services.views import ServiceViewSet
from rest_framework.authtoken import views as authtoken_views

router = DefaultRouter()
router.register(r'profiles', ServiceProviderProfileViewSet, basename='profiles')
router.register(r'services', ServiceViewSet, basename='services')

urlpatterns = [
    path('', include(router.urls)),  # includes /profiles/ and /services/ endpoints
    path('api-token-auth/', authtoken_views.obtain_auth_token, name='api-token-auth'),
]
