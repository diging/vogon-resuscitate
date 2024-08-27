from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from .models import CitesphereAccount, CitesphereGroup
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

# class GroupSyncMiddleware(MiddlewareMixin):
#     def process_view(self, request, view_func, view_args, view_kwargs):
#         slug = view_kwargs.get('slug')
#         if slug:
#             try:
#                 group = CitesphereGroup.objects.get(slug=slug)
#                 account = CitesphereAccount.objects.get(user=request.user)
#                 # Fetch the current sync status from the group API endpoint using the group ID
#                 response = requests.get(
#                     f'{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{group.group_id}/',
#                     headers={'Authorization': f'Bearer {account.access_token}'}
#                 )
#                 if response.status_code == 200:
#                     group_data = response.json()
#                     print(group_data)
#                     sync_status = group_data.get('syncInfo', {}).get('status', 'UNKNOWN')
#                     # Update the group's sync status in the database
#                     group.sync_status = sync_status
#                     group.save()

#                     if sync_status != 'DONE':
#                         # Return a response indicating that the group data is still syncing
#                         return JsonResponse({'warning': 'Group data is still syncing. Please wait until the process is completed.'}, status=202)
#                 else:
#                     return JsonResponse({'error': f"Failed to retrieve group sync status. Status code: {response.status_code}"}, status=response.status_code)
#             except CitesphereGroup.DoesNotExist:
#                 return JsonResponse({'error': "Group not found"}, status=404)
#             except CitesphereAccount.DoesNotExist:
#                 return JsonResponse({'error': "No Citesphere account associated with this user."}, status=404)
#             except requests.RequestException as e:
#                 return JsonResponse({'error': f"An error occurred while retrieving group sync status: {str(e)}"}, status=500)
#         return None