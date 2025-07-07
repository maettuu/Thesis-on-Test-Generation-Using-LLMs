from django.urls import path
from . import webhook

urlpatterns = [
    path('', webhook.github_webhook, name='github_webhook'),  # Matches /webhook-js/
]
