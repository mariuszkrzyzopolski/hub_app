from django.urls import path
from . import views

urlpatterns = [
    path('', views.event_index_view, name='event-index'),
    path('<slug:slug>/', views.event_roles_view, name='event-roles'),
    path('<slug:slug>/count/', views.event_count_json, name='event-count-json'),
]
