# from rest_framework import serializers
# from .models import Service

# class ServiceSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Service
#         fields = '__all__'  # serialize all fields of the service data


from rest_framework import serializers
from taggit.serializers import TagListSerializerField, TaggitSerializer
from .models import Service
from accounts.models import ServiceProviderProfile

class ServiceSerializer(TaggitSerializer, serializers.ModelSerializer):
    service_tags = TagListSerializerField()
    # profile = serializers.SlugRelatedField(slug_field='name', queryset=ServiceProviderProfile.objects.all())
    profile = serializers.PrimaryKeyRelatedField(
        queryset=ServiceProviderProfile.objects.all()
    )

    class Meta:
        model = Service
        fields = ['id', 'profile', 'service_title', 'service_description', 'general_service_description', 'service_tags', 'rating_score', 'rating_description', 'pricing']
        read_only_fields = ['id']
