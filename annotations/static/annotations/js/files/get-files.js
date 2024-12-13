function fetchFiles(itemKey, repositoryId, groupId, csrfToken) {
    const fileListDiv = document.getElementById(`file-list-${itemKey}`);
    const fileRow = document.getElementById(`file-row-${itemKey}`);

    // Clear any existing file information
    fileListDiv.innerHTML = 'Loading files...';
    fileRow.style.display = 'table-row';

    const url = `/${window.config.APP_ROOT}repository/files/${repositoryId}/groups/${groupId}/items/${itemKey}/`;

    fetch(url, {
        method: 'GET',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {

        if (data.is_file_processing) {
            fileListDiv.innerHTML = '<div class="alert alert-info">Files are still being processed in Giles. Please check back later.</div>';
            return;
        }

        if (data.files && data.files.length > 0) {
            let fileListHtml = '<ul style="list-style-type: none; padding: 0;">';
            data.files.forEach(file => {
                fileListHtml += `
                <li style="display: flex; justify-content: space-between; align-items: center; padding: 10px; margin-bottom: 5px; border: 1px solid #ddd; border-radius: 4px;">
                    <span style="font-size: 14px;">${file.filename}</span>
                    <button class="btn btn-primary btn-sm" onclick="importFile('${itemKey}', '${file.id}', ${repositoryId}, ${groupId}, '${csrfToken}')">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style="vertical-align: middle;">
                            <path fill-rule="evenodd" d="M8 0a5.53 5.53 0 0 0-3.594 1.342c-.766.66-1.321 1.52-1.464 2.383C1.266 4.095 0 5.555 0 7.318 0 9.366 1.708 11 3.781 11H7.5V5.5a.5.5 0 0 1 1 0V11h4.188C14.502 11 16 9.57 16 7.773c0-1.636-1.242-2.969-2.834-3.194C12.923 1.999 10.69 0 8 0m-.354 15.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 14.293V11h-1v3.293l-2.146-2.147a.5.5 0 0 0-.708.708z"/>
                        </svg>
                    </button>
                </li>`;
            });
            fileListHtml += '</ul>';
            fileListDiv.innerHTML = fileListHtml;
        } else {
            fileListDiv.innerHTML = '<div class="alert alert-warning">No files available for this item.</div>';
        }
    })
    .catch(error => {
        console.error('Error fetching files:', error);
        fileListDiv.innerHTML = '<div class="alert alert-danger">Failed to load files. Please try again later!</div>';
    });
}
function importFile(itemKey, fileId, repositoryId, groupId, csrfToken) {
    // Get project ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id');

    const baseUrl = `/${window.config.APP_ROOT}repository/${repositoryId}/group/${groupId}/text/${itemKey}/file/${fileId}`;

    // If no project selected, redirect to projects lists page with return parameters
    if (!projectId) {
        const returnParams = new URLSearchParams({
            redirect_to_text_import: true,
            repository_id: repositoryId,
            group_id: groupId,
            text_key: itemKey,
            file_id: fileId
        });
        window.location.href = `/${window.config.APP_ROOT}project/?${returnParams.toString()}`;
        return;
    }

    // Add project ID to URL
    const url = `${baseUrl}/project/${projectId}/`;

    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Import failed. Please try again.');
        }
        return response.json();
    })
    .then(data => {
        if (data.success && data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            throw new Error('Failed to import file. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error importing file:', error);
    });
}
