from external_accounts.giles import GilesAPI, get_giles_document_details, check_giles_upload_status_details
from repository import auth

from .exceptions import GilesUploadError, GilesTextExtractionError
from requests.exceptions import RequestException

import requests

class CitesphereAPIError(Exception):
    """Base exception class for Citesphere API errors"""
    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code 
        self.details = details
        super().__init__(self.message)

class CitesphereAPIv1:
    def __init__(self, user, repository):
        self.user = user
        self.repository = repository
        self.base_url = f"{repository.endpoint}/api/v1"

    def _get_headers(self):
        """Generate headers required for API requests."""
        try:
            return auth.citesphere_auth(self.user, self.repository)
        except Exception as e:
            raise CitesphereAPIError(message="Authentication failed, please try again.", error_code="AUTH_ERROR", details=str(e))

    def _make_request(self, endpoint, params=None):
        """Helper function to handle GET requests with optional parameters."""            
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            raise CitesphereAPIError(message="API request failed", error_code="REQUEST_ERROR", details=str(e))
        except ValueError as e:
            raise CitesphereAPIError(message="Invalid JSON response", error_code="RESPONSE_ERROR", details=str(e))

    def get_groups(self, params=None):
        """Fetch all groups with optional parameters."""
        return self._make_request("/groups/", params=params)
    
    def get_group_items(self, group_id, params=None):
        """Make a request to fetch group items."""
        return self._make_request(f"/groups/{group_id}/items/", params=params)

    def get_group_collections(self, group_id, params=None):
        """Fetch all collections within a group with optional parameters."""
        return self._make_request(f"/groups/{group_id}/collections/", params=params)

    def get_collection_items(self, group_id, collection_id, params=None):
        """Fetch items in a specific collection with optional parameters."""
        return self._make_request(f"/groups/{group_id}/collections/{collection_id}/items/", params=params)

    def get_item_details(self, group_id, item_id, params=None):
        """Fetch detailed information of an item with optional parameters."""
        return self._make_request(f"/groups/{group_id}/items/{item_id}/", params=params)


class RepositoryManager:
    def __init__(self, user, repository):
        """Initialize the manager with the user and repository."""
        self.api = CitesphereAPIv1(user, repository)
        self.user = user
        self.repository = repository

    def get_raw(self, target, **params):
        """Fetch raw data from any API target."""
        try:
            response = requests.get(target, headers=self.api._get_headers(), params=params)
            response.raise_for_status()
            return response.content
        except RequestException as e:
            raise CitesphereAPIError(message="Failed to fetch data", error_code="RAW_DATA_ERROR", details=str(e))

    def groups(self):
        """Fetch all groups from the repository."""
        return self.api.get_groups()

    def group_items(self, group_id, page=1):
        """
        Fetch items from a specific group for a specific page.

        Args:
            group_id: The ID of the group in the repository.
            page: The page number to retrieve.

        Returns:
            A dictionary containing:
                - "group": Details about the group.
                - "items": A list of items in the group for the specified page.
                - "total_items": The total number of items in the group.
                
        Raises:
            CitesphereAPIError
        """
        if not isinstance(page, int) or page < 1:
            raise CitesphereAPIError(message="Invalid page number", error_code="INVALID_PAGE", details="Page must be a positive integer")

        # Make the API call using CitesphereAPIv1
        response_data = self.api.get_group_items(group_id, params={'page': page})

        group_data = response_data.get('group', {})
        items = response_data.get('items', [])
        total_items = group_data.get('numItems', 0)

        return {
            "group": group_data,
            "items": items,
            "total_items": total_items
        }

    def collections(self, group_id):
        """Fetch all collections within a specific group."""
        return self.api.get_group_collections(group_id)

    def collection_items(self, group_id, collection_id, page=1):
        """
        Fetch items from a specific collection in a group for a specific page.

        Args:
            group_id: The ID of the group in the repository.
            collection_id: The ID of the collection within the group.
            page: The page number to retrieve.

        Returns:
            A dictionary containing:
                - "group": Details about the group.
                - "items": A list of items in the specified collection for the given page.
                - "total_items": The total number of items in the collection.
                
        Raises:
            CitesphereAPIError
        """
        if not isinstance(page, int) or page < 1:
            raise CitesphereAPIError(message="Invalid page number", error_code="INVALID_PAGE", details="Page must be a positive integer")

        try:
            collections_data = self.api.get_group_collections(group_id).get('collections', [])
            # TODO: Once there is a collection information endpoint,this will need to be updated
            total_items = next((c.get('numberOfItems', 0) for c in collections_data if c.get('key') == collection_id), 0)
            # Fetch paginated items for the collection
            items = self.api.get_collection_items(group_id, collection_id, params={'page': page}).get('items', [])

            return {
                "group": collections_data,
                "items": items,
                "total_items": total_items
            }
        
        # TODO: Once there is a collection information endpoint, this will no longer be needed, this will be an Exception error
        except StopIteration:
            raise CitesphereAPIError(message="Collection not found", error_code="COLLECTION_NOT_FOUND", details=f"Collection {collection_id} not found in group {group_id}")

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

            giles_uploads = item_data.get('item', {}).get('gilesUploads', [])

            if not giles_uploads:
                raise GilesUploadError("No Giles uploads available for this item.")
            
            extracted_text = giles_uploads[0].get('extractedText', {})

            if extracted_text and extracted_text.get('content-type') == 'text/plain':
                extracted_text_data = get_giles_document_details(self.user, extracted_text.get('id'), repository)
                item_data['item']['text'] = extracted_text_data
            else:
                # Check upload status and get extracted text if processing is complete
                giles_upload_progress_id = giles_uploads[0].get('progressId')
                if giles_upload_progress_id:
                    giles_processing_status = check_giles_upload_status_details(self.user, giles_upload_progress_id, repository)
                    
                    if giles_processing_status['status'] == 'complete':
                        item_data['item']['text'] = giles_processing_status['extracted_text']
                        return item_data
                    elif giles_processing_status['status'] == 'processing':
                        raise GilesUploadError(giles_processing_status['message'])
                    else:
                        raise GilesTextExtractionError(giles_processing_status['message'])
                    
                raise GilesTextExtractionError("No valid text/plain content found for this text!")

            item_data['item']['details'] = item_details

            return item_data
        else:
            response.raise_for_status()
