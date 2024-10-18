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
        """Helper function to handle GET requests."""
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def get_groups(self):
        """Fetch all groups."""
        return self._make_request("/groups/")

    def get_group_collections(self, group_id):
        """Fetch all collections within a group."""
        return self._make_request(f"/groups/{group_id}/collections/")

    def get_collection_items(self, group_id, collection_id):
        """Fetch items in a specific collection."""
        return self._make_request(f"/groups/{group_id}/collections/{collection_id}/items/")

    def get_item_details(self, group_id, item_id):
        """Fetch detailed information of an item."""
        return self._make_request(f"/groups/{group_id}/items/{item_id}/")