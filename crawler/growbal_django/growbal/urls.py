from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # Enable login/logout views
    path('api/', include('api.urls')),  # (We'll set up API routes in a separate urls module)
]
