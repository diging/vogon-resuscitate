from django.utils.timezone import now
from datetime import timedelta

from .models import CitesphereAccount
from repository.models import Repository

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
        # Only proceed if the user is authenticated and has Citesphere access
        if request.user.is_authenticated and request.session.get('citesphere_authenticated'):
            repository_id = request.session.get('repository_id')
            if repository_id:
                try:
                    # Get the Citesphere account associated with the user and the current repository
                    citesphere_account = CitesphereAccount.objects.get(
                        user=request.user,
                        repository_id=repository_id  # Ensure it's for the current repository
                    )
                    repository = Repository.objects.get(pk=repository_id)

                    # Refresh the token if it is expired
                    if citesphere_account.is_token_expired():
                        self.refresh_access_token(citesphere_account, repository, request)
                except (CitesphereAccount.DoesNotExist, Repository.DoesNotExist):
                    # Clear the session if no Citesphere account or repository is found
                    request.session['citesphere_authenticated'] = False

    def refresh_access_token(self, citesphere_account, repository, request):
        # Use the repository-specific credentials for refreshing the token
        response = requests.post(f"{repository.endpoint}/api/oauth/token", data={
            'grant_type': 'refresh_token',
            'refresh_token': citesphere_account.refresh_token,
            'client_id': repository.client_id,
            'client_secret': repository.client_secret,
        })

        if response.status_code == 200:
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            new_refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in')
            expires_at = now() + timedelta(seconds=int(expires_in))

            # Update the Citesphere account with the new tokens
            citesphere_account.access_token = new_access_token
            citesphere_account.refresh_token = new_refresh_token
            citesphere_account.token_expires_at = expires_at
            citesphere_account.save()

            # Mark the user as authenticated with Citesphere in the session
            request.session['citesphere_authenticated'] = True
            
        else:
            # If the token refresh fails, clear the authentication and remove the account
            request.session['citesphere_authenticated'] = False
            citesphere_account.delete()
