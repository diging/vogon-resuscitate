from django.conf import settings
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

    def group_items(self, groupId, page=1):
        """
        Fetch items from a specific group for a specific page.
        """
        headers = auth.citesphere_auth(self.user, self.repository)
        base_url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/items/"

        params = {
            'page': page,
        }

        group_response = requests.get(base_url, headers=headers, params=params)
        group_response.raise_for_status()

        response_data = group_response.json()
        group_data = response_data.get('group', {})
        items = response_data.get('items', [])
        total_items = group_data.get('numItems', 0)

        return {
            "group": group_data,
            "items": items,
            "total_items": total_items
        }
            
    def collections(self, groupId):
        """Fetch collections from the repository's endpoint"""
        headers = auth.citesphere_auth(self.user, self.repository)
        url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/collections/"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()  # Return the Collections data
        else:
            response.raise_for_status()

    def collection_items(self, groupId, collectionId, page=1):
        """
        Fetch items from a specific collection in a group for a specific page.

        Args:
            groupId: The ID of the group in the repository.
            collectionId: The ID of the collection within the group.
            page: The page number to retrieve.

        Returns:
            A dictionary containing:
                - "group": Details about the group.
                - "items": A list of items in the specified collection for the given page.
                - "total_items": The total number of items in the collection.
        """
        headers = auth.citesphere_auth(self.user, self.repository)
        
        items_url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/collections/{collectionId}/items/"
        collections_url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/collections/"

        # Fetch collection details to get total items
        collections_response = requests.get(collections_url, headers=headers)
        collections_response.raise_for_status()

        # Extract group and total items for the collection
        collections_data = collections_response.json().get('collections', [])
        group_info = collections_response.json().get('group', {})
        
        # TODO: Once there is a collection information endpoint,this will need to be updated
        total_items = next((c.get('numberOfItems', 0) for c in collections_data if c.get('key') == collectionId), 0)

        # Get items for the specific page
        response = requests.get(items_url, headers=headers, params={'page': page})
        response.raise_for_status()
        items = response.json().get('items', [])

        return {
            "group": group_info,
            "items": items,
            "total_items": total_items
        }


    def item(self, groupId, itemId, repository):
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
                    extracted_text_data = get_giles_document_details(self.user, extracted_text.get('id'), repository)
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
