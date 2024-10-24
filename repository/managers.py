from repository.restable import RESTManager
from repository import auth
from external_accounts.utils import get_giles_document_details
import requests

class RepositoryManager(RESTManager):
    def __init__(self, **kwargs):
        self.user = kwargs.get('user')
        self.repository = kwargs.get('repository')
        
        if self.user and self.repository:
            kwargs.update({'headers': auth.citesphere_auth(self.user, self.repository)})
        
        super(RepositoryManager, self).__init__(**kwargs)

    def get_raw(self, target, **params):
        headers = {}
        if self.user and self.repository:
            headers = auth.citesphere_auth(self.user, self.repository)
        return requests.get(target, headers=headers, params=params).content

    def groups(self):
        """Fetch Groups from the repository's endpoint"""
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()  # Return the groups data
        else:
            response.raise_for_status()

    def collections(self, groupId):
        """Fetch collections from the repository's endpoint"""
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/collections/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()  # Return the Collections data
        else:
            response.raise_for_status()
    
    def collection_items(self, groupId, collectionId):
        """Fetch collection items from the repository's endpoint"""
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/collections/{collectionId}/items/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def item_files(self, groupId, itemId):
        """
        Fetch individual item from repository's endpoint and list all associated files for import.

        Args:
            groupId: The group ID in the repository
            itemId: The item ID in the repository

        Returns:
            A dictionary containing a list of files with their respective details.
        """
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/items/{itemId}/"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            item_data = response.json()

            files = []
            
            # Extract Giles upload file details if available
            giles_uploads = item_data.get('item', {}).get('gilesUploads', [])

            if giles_uploads:
                for giles_upload in giles_uploads:
                    extracted_text = giles_upload.get('extractedText', {})
                    if extracted_text.get('content-type') == 'text/plain':
                        files.append({
                            'id': extracted_text.get('id'),
                            'filename': extracted_text.get('filename'),
                            'url': extracted_text.get('url')
                        })
                    
            return {
                "files": files,
            }
        else:
            response.raise_for_status()

    def item(self, groupId, itemId, fileId):
        """
        Fetch individual item from repository's endpoint and get Giles document details for documents of type 'text/plain'

        Args:
            groupId: The group ID in the repository
            itemId: The item ID in the repository

        Returns:
            A dictionary containing item details from repository, and Giles document details with extracted text
        """
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/items/{itemId}/"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            item_data = response.json()

            item_details = {
                'key': item_data.get('item', {}).get('key'),
                'title': item_data.get('item', {}).get('title'),
                'authors': item_data.get('item', {}).get('authors', []),
                'itemType': item_data.get('item', {}).get('itemType'),
                'addedOn': item_data.get('item', {}).get('dateAdded', 'Unknown date'),
                'url': item_data.get('item', {}).get('url')
            }

            # Extract Giles file data and pass it in the response
            text = get_giles_document_details(self.user, fileId)
            item_data['item']['text'] = text

            item_data['item']['details'] = item_details

            return item_data

        else:
            response.raise_for_status()