from rest_framework import viewsets, permissions
from .models import ServiceProviderProfile
from .serializers import ServiceProviderProfileSerializer

class ServiceProviderProfileViewSet(viewsets.ModelViewSet):
    queryset = ServiceProviderProfile.objects.all()
    serializer_class = ServiceProviderProfileSerializer
    permission_classes = [permissions.IsAuthenticated]  # require auth for all actions
