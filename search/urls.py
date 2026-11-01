from django.urls import path

from . import views

urlpatterns = [
    path('tim-kiem/', views.tim_kiem, name='search'),   # name='search' khớp menu trong core/navigation.py
]
