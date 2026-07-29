from django.urls import path

from api.v1.views import api_index

app_name = "api-v1"

urlpatterns = [
    path("", api_index, name="index"),
]
