from repository.restable import RESTManager
from repository import auth
from django.conf import settings

from external_accounts.utils import get_giles_document_details

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

    def item(self, groupId, itemId):
        """
        Fetch individual item from Citesphere API and get Giles document details for documents of type 'text/plain'

        Args:
            groupId: The group ID in Citesphere
            itemId: The item ID in Citesphere

        Returns:
            A dictionary containing item details from Citesphere, and Giles document details with extracted text
        """
        headers = auth.citesphere_auth(self.user)
        url = f"{settings.CITESPHERE_ENDPOINT}/api/v1/groups/{groupId}/items/{itemId}/"
        response = requests.get(url, headers=headers)
        
        print(response)  # Printing response for debugging
        
        if response.status_code == 200:
            item_data = response.json()
            print(item_data)
            
            item_details = {
                'key': item_data.get('item', {}).get('key'),
                'title': item_data.get('item', {}).get('title'),
                'authors': item_data.get('item', {}).get('authors', []),
                'itemType': item_data.get('item', {}).get('itemType'),
                'url': item_data.get('item', {}).get('url')
            }
            
            # Extract Giles upload details if available
            giles_uploads = item_data.get('item', {}).get('gilesUploads', [])
            giles_details = []
            for upload in giles_uploads:
                document_id = upload.get('documentId')
                if document_id:
                    details = get_giles_document_details(self.user, document_id)
                    # Check if the content-type of the extracted text is 'text/plain'
                    if details and details.get('extractedText', {}).get('content-type') == 'text/plain':
                        giles_details.append({
                            'documentId': document_id,
                            'extractedText': details['extractedText'],
                            'url': details.get('extractedText', {}).get('url')
                        })
            
            if giles_details:
                item_data['item']['gilesDetails'] = giles_details

            # Append specific item details
            item_data['item']['details'] = item_details
            
            return item_data
        else:
            response.raise_for_status()