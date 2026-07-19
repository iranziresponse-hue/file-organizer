from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profiles/", views.profiles_list, name="profiles_list"),
    path("profiles/new/", views.profile_wizard, name="profile_wizard"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="profile_edit"),
    path("profiles/<int:pk>/activate/", views.profile_activate, name="profile_activate"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
]
