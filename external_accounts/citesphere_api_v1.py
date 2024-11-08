import requests
from repository import auth

class CitesphereAPIv1:
    def __init__(self, user, repository):
        self.user = user
        self.repository = repository
        self.base_url = f"{repository.endpoint}/api/v1"

    def _get_headers(self):
        """Generate headers required for API requests."""
        return auth.citesphere_auth(self.user, self.repository)

    def _make_request(self, endpoint, params=None):
        """Helper function to handle GET requests with optional parameters."""
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

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
