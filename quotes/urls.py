from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("quotes/new/", views.new_quote, name="new_quote"),
    path("quotes/<int:quote_id>/", views.quote_result, name="quote_result"),
    path("quotes/history/", views.quote_history, name="quote_history"),
    path("control-panel/", views.admin_panel, name="admin_panel"),
]
