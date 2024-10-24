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

    def group_items(self, groupId):
        """
        Fetch all items from a specific group.

        This function retrieves all items from the specified group in the repository.
        It gathers all pages of items, combines them into a single JSON object, and includes the group details.

        Args:
            groupId: The ID of the group in the repository.

        Returns:
            A dictionary containing:
                - "group": Details about the group.
                - "items": A list of all items in the specified group.
        """
        headers = auth.citesphere_auth(self.user, self.repository)
        base_url = f"{self.repository.endpoint}/api/v1/groups/{groupId}/items/"

        # Fetch the group details to determine the total number of items
        group_response = requests.get(base_url, headers=headers)
        if group_response.status_code != 200:
            group_response.raise_for_status()

        # Parse the response to get the number of items in the group
        group_data = group_response.json().get('group', {})
        group_num_items = group_data.get('numItems', 0)

        # Get total pages required to fetch all items (By default citesphere return50 items per page)
        items_per_page = getattr(settings, 'CITESPHERE_ITEM_PAGE', 50)
        total_pages = (group_num_items // items_per_page) + (1 if group_num_items % items_per_page else 0)

        final_result = {
            "group": group_data,
            "items": []
        }

        response = requests.get(f"{base_url}?page=1", headers=headers)
        if response.status_code != 200:
            response.raise_for_status()

        # Add the items from the first page to the final result
        first_page_data = response.json()
        final_result["items"].extend(first_page_data.get('items', []))

        # Fetch subsequent pages if there are more than one
        for page in range(2, total_pages + 1):
            paginated_response = requests.get(f"{base_url}?page={page}", headers=headers)
            if paginated_response.status_code == 200:
                page_data = paginated_response.json()
                # Add items from the current page to the final result
                final_result["items"].extend(page_data.get('items', []))
            else:
                paginated_response.raise_for_status()

        return final_result

            
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
