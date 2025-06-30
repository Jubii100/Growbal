from django.db import models
from accounts.models import ServiceProviderProfile
from services.models import Service


class Scrape(models.Model):
    provider = models.ForeignKey(
        ServiceProviderProfile,
        on_delete=models.CASCADE,
        related_name="scrapes",
        null=True,            # optional
        blank=True,
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="scrapes",
        null=True,            # optional
        blank=True,
    )
    base_url = models.CharField(max_length=255, blank=True, null=True, default=None)
    cleaned_html = models.TextField(blank=True, null=True, default=None)
    date_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.base_url
    
    @classmethod
    def check_similar_base_url(cls, base_url: str):
        """
        Retrieve an existing Scrape with a base_url similar to the given one (>= 80% prefix match),
        or create a new Scrape if no such entry exists.
        """
        # Ensure base_url is not null or empty (assumed non-null by problem statement)
        if not base_url:
            raise ValueError("base_url must be provided for similarity check")

        # 1. Check for an exact match first to avoid unnecessary processing
        existing = cls.objects.filter(base_url=base_url).first()
        if existing:
            return True  # Exact match found, return it

        # 2. Iterate over existing Scrape entries to find a sufficiently similar base_url
        for scrape in cls.objects.all():
            existing_url = scrape.base_url
            # Calculate common prefix length between the new URL and this existing URL
            common_prefix_length = 0
            for ch_new, ch_existing in zip(base_url, existing_url):
                if ch_new == ch_existing:
                    common_prefix_length += 1
                else:
                    break  # stop at the first non-matching character
            
            # Calculate the ratio of the common prefix to the new URL's length
            prefix_ratio = common_prefix_length / len(base_url)
            if prefix_ratio >= 0.7:
                # Found an existing URL with a prefix similarity >= 80%
                return True

        # 3. If no similar URL found, create a new Scrape instance
        return False

    # @classmethod
    # def get_or_create_similar(cls, base_url: str):
    #     """
    #     Retrieve an existing Scrape with a base_url similar to the given one (>= 80% prefix match),
    #     or create a new Scrape if no such entry exists.
    #     """
    #     # Ensure base_url is not null or empty (assumed non-null by problem statement)
    #     if not base_url:
    #         raise ValueError("base_url must be provided for similarity check")

    #     # 1. Check for an exact match first to avoid unnecessary processing
    #     existing = cls.objects.filter(base_url=base_url).first()
    #     if existing:
    #         return existing  # Exact match found, return it

    #     # 2. Iterate over existing Scrape entries to find a sufficiently similar base_url
    #     for scrape in cls.objects.all():
    #         existing_url = scrape.base_url
    #         # Calculate common prefix length between the new URL and this existing URL
    #         common_prefix_length = 0
    #         for ch_new, ch_existing in zip(base_url, existing_url):
    #             if ch_new == ch_existing:
    #                 common_prefix_length += 1
    #             else:
    #                 break  # stop at the first non-matching character
            
    #         # Calculate the ratio of the common prefix to the new URL's length
    #         prefix_ratio = common_prefix_length / len(base_url)
    #         if prefix_ratio >= 0.8:
    #             # Found an existing URL with a prefix similarity >= 80%
    #             return scrape

    #     # 3. If no similar URL found, create a new Scrape instance
    #     return cls.objects.create(base_url=base_url)