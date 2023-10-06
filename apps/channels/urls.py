from django.urls import path

from . import views

app_name = "channels"

urlpatterns = [
    path("telegram/<uuid:channel_external_id>", views.new_telegram_message, name="new_telegram_message"),
    path("whatsapp/incoming_message", views.new_whatsapp_message, name="new_whatsapp_message"),
]
