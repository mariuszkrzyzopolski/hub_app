from django.contrib import admin
from django.urls import path, include
from . import views
from . import admin_dashboard
from . import contribution_heatmap

urlpatterns = [
    # Custom admin views must come BEFORE admin.site.urls catch-all
    path('admin/usage-statistics/', admin_dashboard.usage_statistics, name='usage-statistics'),
    path('admin/contribution-heatmap/', contribution_heatmap.contribution_heatmap, name='contribution-heatmap'),
    path('admin/', admin.site.urls),
    path('gifts/', include('gifts.urls')),
    path('events/', include('events.urls')),
    path('change-name/', views.change_name, name='change-name'),
    path('', views.HomeView.as_view(), name='home'),
]
