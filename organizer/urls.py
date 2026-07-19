from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("start/", views.start, name="start"),
    path("study/", views.study_home, name="study_home"),
    path("integrations/muele/", views.muele_connection, name="muele_connection"),
    path("profiles/", views.profiles_list, name="profiles_list"),
    path("profiles/new/", views.profile_wizard, name="profile_wizard"),
    path("profiles/new/makerere/", views.makerere_wizard, name="makerere_wizard"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="profile_edit"),
    path("profiles/<int:pk>/activate/", views.profile_activate, name="profile_activate"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
    path("settings/", views.settings_edit, name="settings_edit"),
    path("api/browse-folders/", views.browse_folders, name="browse_folders"),
    path("moves/<int:pk>/summarize/", views.move_summarize, name="move_summarize"),
    path("moves/<int:pk>/summary/", views.move_summary_view, name="move_summary_view"),
    path("moves/<int:pk>/summary.pdf", views.move_summary_pdf, name="move_summary_pdf"),
    path("profiles/<int:profile_pk>/courses/<str:code>/guide/generate/", views.course_guide_generate, name="course_guide_generate"),
    path("profiles/<int:profile_pk>/courses/<str:code>/guide/", views.course_guide_view, name="course_guide_view"),
    path("profiles/<int:profile_pk>/courses/<str:code>/guide.pdf", views.course_guide_pdf, name="course_guide_pdf"),
]
