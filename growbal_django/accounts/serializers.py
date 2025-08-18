# from rest_framework import serializers
# from .models import ServiceProviderProfile

# class ServiceProviderProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ServiceProviderProfile
#         fields = '__all__'  # serialize all fields of the profile


from rest_framework import serializers
from .models import ServiceProviderProfile
from django.contrib.auth import get_user_model
# from services.models import Service

CustomUser = get_user_model()

class ServiceProviderProfileSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field='username', queryset=CustomUser.objects.all())
    # service = serializers.SlugRelatedField(slug_field='id', queryset=Service.objects.all(), allow_null=True)
    emails = serializers.ListField(
        child=serializers.EmailField(),
        allow_empty=True,     # accept [] as “no e-mails yet”
        required=False,       # omit in PATCH requests if unchanged
        )

    class Meta:
        model = ServiceProviderProfile
        fields = [
            'id',
            'user',
            # 'service',
            'provider_type',
            'country',
            'session_status',
            # 'tier',
            'name',
            'logo',
            'website',
            'linkedin',
            'facebook',
            'instagram',
            'telephones',
            'mobiles',
            'emails',
            'office_locations',
            'key_individuals'
        ]

