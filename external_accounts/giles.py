from django.conf import settings
from .models import CitesphereAccount

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
        return response.text

    def check_upload_progress(self, progress_id):
        """
        Check the status of an upload using its progress ID
        
        Args:
            progress_id: Progress ID of the upload to check
            
        Returns:
            str|None: The upload ID if available, otherwise None
        """
        if not self.access_token:
            raise ValueError("User must authenticate with Citesphere before making API calls")
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/api/v2/files/upload/check/{progress_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json().get('uploadId')

    def get_upload_details(self, upload_id):
        """
        Get details about an upload from Giles API
        
        Args:
            upload_id: ID of the upload to get details for
            
        Returns:
            Dictionary containing upload details including:
            - Document ID and status
            - Upload ID and date
            - Access level
            - Original uploaded file info
            - Extracted text file info 
            - Page images and text
            
        Note: If upload is still being processed, returned data may be incomplete
        """
        if not self.access_token:
            raise ValueError("User must authenticate with Citesphere before making API calls")
            
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}/api/v2/resources/files/upload/{upload_id}"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()[0] # API returns list with single item
    

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


def check_giles_upload_status_details(user, progress_id, repository):
    """
    Check if a Giles upload has completed processing and has extracted text available.

    Args:
        user: The user object
        progress_id: The progress ID to check status for
        repository: The repository object containing Giles endpoint info

    Returns:
        Dictionary with extracted text details if processing complete, 
        or status message if still processing
    """
    try:
        giles = GilesAPI(user, repository)
        upload_id = giles.check_upload_progress(progress_id)

        if not upload_id:
            return {"status": "error", "message": "No upload found for this text!"}

        upload_info = giles.get_upload_details(upload_id)  # API returns list with single item
        
        if upload_info.get("documentStatus") != "COMPLETE":
            return {"status": "processing", "message": "Files are still being processed in Giles, Please check back later!"}

        extracted_text = upload_info.get("extractedText")
        if extracted_text:
            return {
                "status": "complete",
                "extracted_text": extracted_text
            }
        else:
            return {"status": "error", "message": "No extracted text available"}

    except requests.RequestException as e:
        logger.error(f"Failed to check Giles upload status: {e}")
        return {"status": "error", "message": str(e)}
