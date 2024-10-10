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

    def group_items(self, groupId):
        """Fetch items in a particular Group from the repository's endpoint"""
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/items/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
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

    def item(self, groupId, itemId):
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

            # Extract Giles upload details if available
            giles_uploads = item_data.get('item', {}).get('gilesUploads', [])

            if giles_uploads:
                giles_details = []
                extracted_text = giles_uploads[0].get('extractedText', {})

                if extracted_text and extracted_text.get('content-type') == 'text/plain':
                    extracted_text_data = get_giles_document_details(self.user, extracted_text.get('id'))
                    item_data['item']['text'] = extracted_text_data
                elif giles_uploads[0].get('pages'):
                    pages = giles_uploads[0].get('pages')
                    text = ""
                    for page in pages:
                        if page.get('text') and page.get('text').get('content-type') == 'text/plain':
                            data = get_giles_document_details(self.user, page.get('text').get('id'))
                            text += data
                    item_data['item']['text'] = text
                else:
                    item_data['item']['text'] = "No valid text/plain content found."
            else:
                print("No Giles uploads available")
                item_data['item']['text'] = "No Giles uploads available."

            item_data['item']['details'] = item_details

            return item_data

        else:
            response.raise_for_status()
