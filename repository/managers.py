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
        """Fetch Groups from the Citesphere API"""
        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/api/v1/groups/"
        response = requests.get(url, headers=headers)
        print(response.text)
        
        if response.status_code == 200:
            return response.json()  # Return the groups data
        else:
            response.raise_for_status()

    def collections(self, groupId):
        """Fetch collections from the Citesphere API"""
        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{groupId}/collections/"
        response = requests.get(url, headers=headers)
        print(response.text)
        
        if response.status_code == 200:
            return response.json()  # Return the Collections data
        else:
            response.raise_for_status()
    
    def collection_items(self, groupId, collectionId):
        """Fetch collection items from Citesphere API"""

        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{groupId}/collections/{collectionId}/items/"
        response = requests.get(url, headers=headers)
        print(response)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def item(self, groupId, collectionId, itemId):
        """Fetch individual item from Citesphere API"""

        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{groupId}/item/{itemId}/"
        response = requests.get(url, headers=headers)
        print(response)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()