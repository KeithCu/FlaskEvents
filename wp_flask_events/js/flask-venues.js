(function() {
    const config = typeof flaskEvents !== 'undefined' ? flaskEvents : {};
    const apiBase = (config.flaskUrl || '').replace(/\/$/, '');

    function apiUrl(path) {
        return apiBase + path;
    }

    function escapeHtml(text) {
        if (text == null) {
            return '';
        }
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function groupVenues(venues, groupBy) {
        const groups = {};
        const groupOrder = [];

        venues.forEach(function(venue) {
            let key = venue[groupBy];
            if (!key || !String(key).trim()) {
                key = 'Other';
            }
            if (!groups[key]) {
                groups[key] = [];
                groupOrder.push(key);
            }
            groups[key].push(venue);
        });

        groupOrder.sort(function(a, b) {
            if (a === 'Other') return 1;
            if (b === 'Other') return -1;
            return a.localeCompare(b);
        });

        return groupOrder.map(function(key) {
            return { label: key, venues: groups[key] };
        });
    }

    function renderVenueList(container, venues, groupBy) {
        if (venues.length === 0) {
            container.innerHTML = '<p class="flask-venues-empty">No venues found.</p>';
            return;
        }

        const groups = groupVenues(venues, groupBy);
        let html = '';

        groups.forEach(function(group) {
            html += '<div class="flask-venues-group">';
            html += '<h3 class="flask-venues-type">' + escapeHtml(group.label) + '</h3>';
            html += '<ul class="flask-venues-list">';
            group.venues.forEach(function(venue) {
                html += '<li class="listvenuelink">';
                html += '<a href="' + escapeHtml(apiUrl('/venues/' + venue.id)) + '" target="_blank" rel="noopener">';
                html += escapeHtml(venue.name);
                html += '</a></li>';
            });
            html += '</ul></div>';
        });

        container.innerHTML = html;
    }

    function loadVenueList(container) {
        const neighborhood = container.dataset.neighborhood;
        const groupBy = container.dataset.groupBy || 'venue_type';

        if (!neighborhood || !apiBase) {
            container.innerHTML = '<p class="flask-venues-empty">Venue list unavailable.</p>';
            return;
        }

        container.innerHTML = '<p class="flask-venues-loading">Loading venues...</p>';

        const params = new URLSearchParams({ neighborhood: neighborhood });
        fetch(apiUrl('/venues?' + params.toString()))
            .then(function(response) { return response.json(); })
            .then(function(venues) {
                renderVenueList(container, venues, groupBy);
            })
            .catch(function(error) {
                console.error('Error loading venues:', error);
                container.innerHTML = '<p class="flask-venues-empty">Error loading venues. Please try again.</p>';
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.flask-venues-wrap[data-neighborhood]').forEach(loadVenueList);
    });
})();
