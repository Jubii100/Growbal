from rest_framework import serializers
from services.models import Service
from accounts.models import ServiceProviderProfile
from .models import Scrape

class ScrapeSerializer(serializers.ModelSerializer):
    provider = serializers.PrimaryKeyRelatedField(
        queryset=ServiceProviderProfile.objects.all()
    )
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all()
    )

    class Meta:
        model = Scrape
        fields = ['id', 'provider', 'service', 'base_url', 'cleaned_html']
        read_only_fields = ['id']
