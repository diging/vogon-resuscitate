from django.conf import settings
from .models import CitesphereAccount

from repository.exceptions import GilesTextExtractionError

import requests

import logging
logger = logging.getLogger(__name__)


class GilesAPI:
    """Class to handle interactions with the Giles API"""
    
    def __init__(self, user, repository):
        self.repository = repository
        self.base_url = repository.giles_endpoint
        self.user = user
        self.access_token = self._get_access_token()
        
    def _get_access_token(self):
        """Get authentication token for user"""
        try:
            account = CitesphereAccount.objects.get(user=self.user, repository=self.repository)
            return account.access_token
        except CitesphereAccount.DoesNotExist:
            return None
        
    def get_file_content(self, file_id):
        """
        Get the content of a file from the Giles API.

        Args:
            file_id: ID of the file to retrieve content for

        Returns:
            String containing the file content

        Raises:
            ValueError: If user is not authenticated with Citesphere
            HTTPError: If API request fails
        """
        if not self.access_token:
            raise ValueError("User must authenticate with Citesphere before making API calls")
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/api/v2/resources/files/{file_id}/content/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        content = response.text
        if '\x00' in content:
            logger.error("Null character found in file content")
            raise GilesTextExtractionError("File content contains null characters")
        return content
    
# Returns the file content from Giles using the GilesAPI class, used in the repository manager in the item function
def get_giles_document_details(user, file_id, repository):
    """
    Retrieve detailed information about a document from Giles for a given user and document ID.

    Args:
        user: The user object
        file_id: The ID of the file to retrieve from Giles
        repository: The repository object containing Giles endpoint info

    Returns:
        A dictionary with the document details if successful, None otherwise.
    """
    try:
        giles = GilesAPI(user, repository)
        return giles.get_file_content(file_id)
        
    except requests.RequestException as e:
        logger.error(f"Failed to retrieve Giles document details: {e}")
        return None

