class ConceptSearch {
    constructor() {
        this.resultsPerPage = 10;
        this.currentPage = 1;
        this.allResults = [];
        this.displayedResults = new Set();
        this.searchQuery = '';
        this.filteredWords = [];
    }

    initialize(searchQuery) {
        this.searchQuery = searchQuery;
        this.currentPage = 1;
        this.displayedResults.clear();
        
        // Split search query and filter words <= 3 characters
        const words = searchQuery.split(' ');
        this.filteredWords = words.filter(w => w.length > 3);
        
        // Get all results from the page
        this.allResults = Array.from(document.querySelectorAll('.concept-item'));
        
        // Sort results by match type
        this.allResults.sort((a, b) => {
            const aType = a.dataset.matchType;
            const bType = b.dataset.matchType;
            const typeOrder = { 'exact': 0, 'filtered': 1, 'partial': 2 };
            return typeOrder[aType] - typeOrder[bType];
        });
        
        this.displayResults();
    }

    displayResults() {
        const resultsContainer = document.getElementById('concept-search-results');
        const loadMoreBtn = document.getElementById('load-more-btn');
        
        // Hide all results first
        this.allResults.forEach(result => result.style.display = 'none');
        
        // Show results based on current page and match type
        let displayedCount = 0;
        let exactMatches = 0;
        let filteredMatches = 0;
        
        for (const result of this.allResults) {
            const matchType = result.dataset.matchType;
            
            // Count matches by type
            if (matchType === 'exact') exactMatches++;
            else if (matchType === 'filtered') filteredMatches++;
            
            // Display logic
            if (displayedCount < this.resultsPerPage) {
                if (matchType === 'exact' || 
                    (matchType === 'filtered' && exactMatches < 10) ||
                    (matchType === 'partial' && exactMatches < 10 && filteredMatches < 10)) {
                    result.style.display = 'block';
                    displayedCount++;
                    this.displayedResults.add(result);
                }
            }
        }
        
        // Show/hide load more button
        if (this.displayedResults.size < this.allResults.length) {
            loadMoreBtn.style.display = 'block';
        } else {
            loadMoreBtn.style.display = 'none';
        }
    }

    loadMore() {
        this.currentPage++;
        this.displayResults();
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.querySelector('form[action*="concept_search"]');
    const loadMoreBtn = document.getElementById('load-more-btn');
    const conceptSearch = new ConceptSearch();
    
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            const searchInput = searchForm.querySelector('input[name="search"]');
            if (searchInput.value.trim()) {
                // The form will submit normally, and the page will reload with results
                // The results will be initialized when the page loads
            }
        });
    }
    
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', (e) => {
            e.preventDefault();
            conceptSearch.loadMore();
        });
    }
    
    // Initialize with current search results if any
    const searchQuery = document.querySelector('input[name="search"]')?.value;
    if (searchQuery) {
        conceptSearch.initialize(searchQuery);
    }
}); 