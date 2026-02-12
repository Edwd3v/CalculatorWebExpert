from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("quotes/new/", views.new_quote, name="new_quote"),
    path("quotes/<int:quote_id>/", views.quote_result, name="quote_result"),
    path("quotes/history/", views.quote_history, name="quote_history"),
    path("control-panel/", views.admin_panel, name="admin_panel"),
    path("control-panel/tarifas/", views.admin_rates, name="admin_rates"),
    path("control-panel/usuarios/", views.admin_users, name="admin_users"),
    path("control-panel/historial/", views.admin_history, name="admin_history"),
]
