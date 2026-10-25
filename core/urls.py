from django.urls import path

from . import views

urlpatterns = [path("ui-kit/", views.ui_kit, name="ui_kit")]  # chỉ nên mở khi DEBUG
