from django.contrib import admin
from .models import Scrape
# from services.models import Service
# from accounts.models import ServiceProviderProfile

@admin.register(Scrape)
class ScrapeAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'provider', 'service', 'date_created', 'date_modified')
    search_fields = ('base_url', 'provider__name', 'service__service_title')
    # readonly_fields = ('date_created', 'date_modified')
