# from django.db import models

# class Service(models.Model):
#     name = models.CharField(max_length=255)
#     logo = models.ImageField(upload_to='logos/', blank=True, null=True)  # Company logo image
#     country = models.CharField(max_length=100, blank=True)
#     website = models.URLField(blank=True, null=True)
#     linkedin = models.URLField(blank=True, null=True)
#     facebook = models.URLField(blank=True, null=True)
#     instagram = models.URLField(blank=True, null=True)
#     services_offered = models.TextField(blank=True)      # description or list of services
#     contact_numbers = models.TextField(blank=True)       # phone numbers (possibly multiple)
#     emails = models.TextField(blank=True)                # contact emails (possibly multiple)
#     office_locations = models.TextField(blank=True)      # addresses (possibly multiple)
#     ratings = models.CharField(max_length=50, blank=True)  # e.g. "4.5/5" or other rating info
#     key_individuals = models.TextField(blank=True)       # names of key people
#     pricing = models.TextField(blank=True)               # pricing information
#     service_description = models.TextField(blank=True)   # descriptions of services or company

#     def __str__(self):
#         return self.name


from django.db import models
from taggit.managers import TaggableManager
from taggit.models import Tag
from accounts.models import ServiceProviderProfile


class Service(models.Model):
    profile = models.ForeignKey(
    ServiceProviderProfile,
    on_delete=models.CASCADE,
    related_name="services",
    null=True,
    blank=True,
    )
    service_title = models.CharField(max_length=255, blank=True, null=True, default=None)
    service_description = models.TextField(blank=True, null=True, default=None)
    # specific_service_description = models.TextField(blank=True, null=True, default=None)
    general_service_description = models.TextField(blank=True, null=True, default=None)
    service_tags = TaggableManager(blank=True)
    rating_score = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, default=None)
    rating_description = models.TextField(blank=True, null=True, default=None)
    pricing = models.TextField(blank=True, null=True, default=None)
    date_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def delete(self, *args, **kwargs):
        tag_ids = list(self.service_tags.values_list('id', flat=True))
        super().delete(*args, **kwargs)
        for tag_id in tag_ids:
            if not Tag.objects.get(id=tag_id).taggit_taggeditem_items.exists():
                Tag.objects.filter(id=tag_id).delete()

    def __str__(self):
        return self.service_title
