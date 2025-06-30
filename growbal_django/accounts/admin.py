# from django.contrib import admin
# from .models import ServiceProviderProfile

# @admin.register(ServiceProviderProfile)
# class ServiceProviderProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'user_type', 'tier', 'location', 'session_status')
#     list_filter = ('user_type', 'tier')


# from django.contrib import admin
# from .models import CustomUser, ServiceProviderProfile, ServiceProviderMemberProfile

# @admin.register(CustomUser)
# class CustomUserAdmin(admin.ModelAdmin):
#     list_display = ('name', 'username', 'email', 'is_staff', 'is_superuser')
#     search_fields = ('name', 'email', 'username')

# @admin.register(ServiceProviderProfile)
# class ServiceProviderProfileAdmin(admin.ModelAdmin):
#     # list_display = ('user', 'provider_type', 'tier', 'country', 'session_status', 'service')
#     # list_filter = ('provider_type', 'tier', 'country', 'session_status')
#     list_display = ('name', 'provider_type', 'country', 'service', 'session_status')
#     list_filter = ('provider_type', 'country', 'session_status')
#     search_fields = ('user__email', 'user__username', 'country', 'provider_type', 'name')

# @admin.register(ServiceProviderMemberProfile)
# class ServiceProviderMemberProfileAdmin(admin.ModelAdmin):
#     list_display = ('name', 'company', 'role_description', 'email', 'mobile', 'telephone')
#     list_filter = ('company__provider_type',)
#     search_fields = ('user__email', 'user__username', 'role_description', 'email', 'company__name')



from django.contrib import admin
from django.db.models import Q
from .models import (
    CustomUser,
    ServiceProviderProfile,
    ServiceProviderMemberProfile,
)
from services.models import Service


# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("name", "username", "email", "is_staff", "is_superuser")
    search_fields = ("name", "email", "username")


# ------------------------------------------------------------------
# Services shown inline under each profile
# ------------------------------------------------------------------
class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0                     # no blank rows
    show_change_link = True       # make each row clickable
    fields = ("service_title", "service_description", "rating_score", "rating_description", "pricing")  # adjust as you like


# ------------------------------------------------------------------
# Service-provider profiles
# ------------------------------------------------------------------
@admin.register(ServiceProviderProfile)
class ServiceProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider_type",
        "country",
        "services_list",      # computed column
        "office_locations",
        "date_created",
        "date_modified",
    )
    list_filter = ("provider_type", "country")
    search_fields = (
        "name",
        "user__email",
        "user__username",
        "country",
        "services__service_title",        # for the automatic admin search
        "services__service_tags__name",    # tag names (works even without the override
        # "provider_type",
        # "services_list",
    )
    # readonly_fields = ("id", "date_created", "date_modified")

    inlines = [ServiceInline]

    # Prefetch services so the changelist doesn't run N+1 queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("services")

    @admin.display(description="Services")
    def services_list(self, obj):
        """
        Comma-separated list of related service titles.
        """
        titles = obj.services.values_list("service_title", flat=True)
        return ", ".join(titles) if titles else "—"

    @admin.display(description="Tags")
    def service_tags_list(self, obj):
        return ", ".join(obj.service_tags.values_list("name", flat=True))

    def get_search_results(self, request, queryset, search_term):
        # start with what search_fields already gives you
        qs, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        if search_term:
            # OR in extra matches that aren’t covered elsewhere
            qs |= self.model.objects.filter(
                Q(services__service_title__icontains=search_term) |
                Q(services__service_tags__name__icontains=search_term)
            )

        # any time you traverse an m2m/FK the queryset
        # can duplicate rows → DISTINCT ensures unique rows
        return qs.distinct(), True


# ------------------------------------------------------------------
# Individual member profiles
# ------------------------------------------------------------------
@admin.register(ServiceProviderMemberProfile)
class ServiceProviderMemberProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "role_description",
        "email",
        "mobile",
        "telephone",
    )
    list_filter = ("company__provider_type",)
    search_fields = (
        "user__email",
        "user__username",
        "role_description",
        "email",
        "company__name",
    )
