from repository.restable import RESTManager
from repository import auth
from django.conf import settings

import requests

class RepositoryManager(RESTManager):
    def __init__(self, **kwargs):
        self.user = kwargs.get('user')
        if self.user:
            kwargs.update({'headers': auth.citesphere_auth(self.user)})
        super(RepositoryManager, self).__init__(**kwargs)

    def get_raw(self, target, **params):
        import requests
        headers = {}
        if self.user:
            headers = auth.citesphere_auth(self.user)
        return requests.get(target, headers=headers, params=params).content

    def groups(self):
        """Fetch collections from the Citesphere API"""
        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/v1/api/groups/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()  # Return the groups data
        else:
            response.raise_for_status()