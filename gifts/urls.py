from django.urls import path
from . import views

urlpatterns = [
    path('', views.gift_index_view, name='gift-index'),
    path('<slug:slug>/', views.gift_list_view, name='gift-list'),
    path('<slug:slug>/count/', views.gift_count_json, name='gift-count-json'),
]
