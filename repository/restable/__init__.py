from .util import *
from ..auth import *
from django.shortcuts import get_object_or_404
from django.conf import settings
import requests

from ..models import Repository

class RESTManager(object):
    """
    Simplified RESTManager for handling Citesphere groups, collections, and items.
    """

    def __init__(self, user=None, repository=None, headers=None):
        """
        Initialize the RESTManager with user authentication and base URL for Citesphere API.

        Parameters
        ----------
        user : User object
            The user for which authentication is handled.
        repository : Repository object
            The repository for which the RESTManager is handling requests.
        base_url : str
            The base URL for the Citesphere API.
        headers : dict
            Additional headers to be sent with the request.
        """
        self.user = user
        self.repository = repository
        self.base_url = repository.endpoint
        self.headers = headers or {}

    def _get_headers(self):
        if self.user and self.repository:
            auth_headers = citesphere_auth(self.user, self.repository)
            if auth_headers:
                self.headers.update(auth_headers)
            else:
                # Handle authentication failure appropriately
                raise Exception("Authentication required. Please authenticate with Citesphere.")
        return self.headers

    def get(self, endpoint, params=None):
        """
        Generic method for performing GET requests.

        Parameters
        ----------
        endpoint : str
            The endpoint to hit (appended to the base URL).
        params : dict
            Optional query parameters.

        Returns
        -------
        JSON response or raises an HTTPError if the request fails.
        """
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            return response.json()  # Parse JSON if successful
        else:
            response.raise_for_status()

    def groups(self):
        """
        Fetch groups from the Citesphere API.

        Returns
        -------
        JSON response containing the groups.
        """
        return self.get('v1/api/groups')

    def collections(self, group_id):
        """
        Fetch collections for a specific group from the Citesphere API.

        Parameters
        ----------
        group_id : int
            The ID of the group for which collections are to be fetched.

        Returns
        -------
        JSON response containing the collections.
        """
        return self.get(f'v1/api/groups/{group_id}/collections')

    def items(self, group_id, collection_id):
        """
        Fetch items for a specific collection within a group.

        Parameters
        ----------
        group_id : int
            The ID of the group.
        collection_id : int
            The ID of the collection.

        Returns
        -------
        JSON response containing the items.
        """
        return self.get(f'v1/api/groups/{group_id}/collections/{collection_id}/items')

