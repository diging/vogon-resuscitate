from django.http import JsonResponse
from .models import CitesphereAccount
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings
import requests

class TokenRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request before passing it to the view
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                citesphere_account = CitesphereAccount.objects.get(user=request.user)
                if citesphere_account.is_token_expired():
                    self.refresh_access_token(citesphere_account)
            except CitesphereAccount.DoesNotExist:
                pass

    def refresh_access_token(self, citesphere_account):
        response = requests.post(settings.CITESPHERE_TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': citesphere_account.refresh_token,
            'client_id': settings.CITESPHERE_CLIENT_ID,
            'client_secret': settings.CITESPHERE_CLIENT_SECRET,
        }).json()

        new_access_token = response.get('access_token')
        new_refresh_token = response.get('refresh_token')
        expires_in = response.get('expires_in')
        expires_at = now() + timedelta(seconds=int(expires_in))

        citesphere_account.access_token = new_access_token
        citesphere_account.refresh_token = new_refresh_token
        citesphere_account.token_expires_at = expires_at
        citesphere_account.save()
