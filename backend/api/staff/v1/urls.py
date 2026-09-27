from django.urls import path

from api.staff.v1.views import StaffIndexView


app_name = "api-staff-v1"

urlpatterns = [
    path("", StaffIndexView.as_view(), name="index"),
]
