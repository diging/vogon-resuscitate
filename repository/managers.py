from external_accounts.citesphere_api_v1 import CitesphereAPIv1
from external_accounts.utils import get_giles_document_details
import requests

class RepositoryManager:
    def __init__(self, user, repository):
        """Initialize the manager with the user and repository."""
        self.api = CitesphereAPIv1(user, repository)
        self.user = user
        self.repository = repository

    def get_raw(self, target, **params):
        """Fetch raw data from any API target."""
        response = requests.get(target, headers=self.api._get_headers(), params=params)
        response.raise_for_status()
        return response.content

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
        """
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
        """
        # Fetch collection details to get total items count
        collections_data = self.api.get_group_collections(group_id).get('collections', [])
        total_items = next((c.get('numberOfItems', 0) for c in collections_data if c.get('key') == collection_id), 0)

        # Fetch paginated items for the collection
        items = self.api.get_collection_items(group_id, collection_id, params={'page': page}).get('items', [])

        return {
            "group": collections_data,
            "items": items,
            "total_items": total_items
        }

    def item(self, group_id, item_id):
        """
        Fetch individual item details from the repository and extract Giles document text.

        Args:
            group_id: The group ID from which the item is fetched.
            item_id: The item ID to fetch.

        Returns:
            A dictionary containing item details and Giles document text.
        """
        # Fetch item details using CitesphereAPIv1
        item_data = self.api.get_item_details(group_id, item_id)

        # Extract core item details
        item_details = {
            'key': item_data.get('item', {}).get('key'),
            'title': item_data.get('item', {}).get('title'),
            'authors': item_data.get('item', {}).get('authors', []),
            'itemType': item_data.get('item', {}).get('itemType'),
            'addedOn': item_data.get('item', {}).get('dateAdded', 'Unknown date'),
            'url': item_data.get('item', {}).get('url')
        }

        # Extract Giles uploads and their text if available
        giles_uploads = item_data.get('item', {}).get('gilesUploads', [])
        item_data['item']['text'] = self._fetch_giles_text(giles_uploads)
        item_data['item']['details'] = item_details

        return item_data

    def _fetch_giles_text(self, giles_uploads):
        """Extract text from Giles uploads."""
        if not giles_uploads:
            return "No Giles uploads available."

        upload = giles_uploads[0]
        text_content = ""

        # Extract plain text if available
        extracted_text = upload.get('extractedText', {})
        if extracted_text and extracted_text.get('content-type') == 'text/plain':
            text_content = get_giles_document_details(self.user, extracted_text['id'])

        # Fallback to extracting text from pages
        elif 'pages' in upload:
            for page in upload['pages']:
                text_data = page.get('text')
                if text_data and text_data.get('content-type') == 'text/plain':
                    text_content += get_giles_document_details(self.user, text_data['id'])

        return text_content or "No valid text/plain content found."
