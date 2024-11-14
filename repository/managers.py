from external_accounts.utils import get_giles_document_details
from repository import auth
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

        response_data = self.api._make_request(f"/groups/{group_id}/items/", params={'page': page})
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

    def item(self, group_id, item_id):
        """
        Fetch individual item details from the repository and extract Giles document text.

        Args:
            group_id: The group ID from which the item is fetched.
            item_id: The item ID to fetch.

        Returns:
            A dictionary containing item details and Giles document text.
            
        Raises:
            CitesphereAPIError
        """
        # Fetch item details using CitesphereAPIv1
        item_data = self.api.get_item_details(group_id, item_id)
        
        if not item_data or 'item' not in item_data:
            raise CitesphereAPIError(message="Invalid item data", error_code="INVALID_ITEM_DATA", details="Response missing item data")

        # Extract core item details
        item = item_data.get('item', {})
        item_details = {
            'key': item.get('key'),
            'title': item.get('title'),
            'authors': item.get('authors', []),
            'itemType': item.get('itemType'),
            'addedOn': item.get('dateAdded', 'Unknown date'),
            'url': item.get('url')
        }

        # Extract Giles uploads and their text if available
        giles_uploads = item.get('gilesUploads', [])
        item_data['item']['text'] = self._fetch_giles_text(giles_uploads)
        item_data['item']['details'] = item_details

        return item_data

    def _fetch_giles_text(self, giles_uploads):
        """
        Extract text from Giles uploads.
        
        Args:
            giles_uploads: List of Giles upload objects
            
        Returns:
            str: Extracted text content or error message
            
        Raises:
            CitesphereAPIError
        """
        if not giles_uploads:
            return "No Giles uploads available."

        try:
            upload = giles_uploads[0]
            text_content = ""

            # Extract plain text if available
            extracted_text = upload.get('extractedText', {})
            if extracted_text and extracted_text.get('content-type') == 'text/plain':
                text_content = get_giles_document_details(self.user, extracted_text['id'])
                if text_content is None:
                    raise CitesphereAPIError(message="Failed to fetch document text from Giles, please try again later.", error_code="GILES_TEXT_ERROR", details="Failed to fetch document text from Giles")

            # Fallback to extracting text from pages
            elif 'pages' in upload:
                for page in upload['pages']:
                    text_data = page.get('text')
                    if text_data and text_data.get('content-type') == 'text/plain':
                        page_text = get_giles_document_details(self.user, text_data['id'])
                        if page_text is not None:
                            text_content += page_text
                        else:
                            raise CitesphereAPIError(message="Failed to fetch document text from Giles, please try again later.", error_code="GILES_PAGE_ERROR", details=f"Failed to fetch text for page {page.get('number', 'unknown')}")

            return text_content or "No valid text/plain content found."
            
        except Exception as e:
            # If the exception is already a CitesphereAPIError, re-raise it directly to preserve the original error details.
            if isinstance(e, CitesphereAPIError):
                raise
            raise CitesphereAPIError(message="Giles text extraction has failed", error_code="GILES_EXTRACTION_ERROR", details=str(e))
