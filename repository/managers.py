from external_accounts.citesphere_api_v1 import CitesphereAPIv1
from external_accounts.utils import get_giles_document_details
import requests

class RepositoryManager:
    def __init__(self, user, repository):
        """Initialize the manager with the user and repository."""
        self.api = CitesphereAPIv1(user, repository)
        self.user = user

    def get_raw(self, target, **params):
        """Fetch raw data from any API target."""
        response = requests.get(target, headers=self.api._get_headers(), params=params)
        response.raise_for_status()
        return response.content

    def groups(self):
        """Fetch all groups from the repository."""
        return self.api.get_groups()

    def collections(self, group_id):
        """Fetch all collections within a specific group."""
        return self.api.get_group_collections(group_id)

    def collection_items(self, group_id, collection_id):
        """Fetch items from a specific collection."""
        return self.api.get_collection_items(group_id, collection_id)
    
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