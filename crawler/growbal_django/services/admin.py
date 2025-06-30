# from django.contrib import admin
# from .models import Service

# @admin.register(Service)
# class ServiceAdmin(admin.ModelAdmin):
#     list_display = ('name', 'country', 'website', 'ratings')
#     search_fields = ('name', 'country')


from django.contrib import admin
from .models import Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_title', 'profile', 'rating_score', 'rating_description', 'pricing', 'date_created', 'date_modified')
    search_fields = ('service_title', 'service_description', 'service_tags__name', 'rating_score', 'rating_description', 'pricing')
    # readonly_fields = ("id", "date_created", "date_modified")
