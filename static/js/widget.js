document.addEventListener('DOMContentLoaded', function() {
    // Get initial date from URL if available
    const pathParts = window.location.pathname.split('/');
    let initialDate = new Date();
    
    // Check if we have a date parameter from URL
    if (pathParts.length >= 3 && pathParts[1] === 'day') {
        // Parse date from URL path
        initialDate = new Date(pathParts[2] + 'T00:00:00');
        console.log(`Using URL date: ${pathParts[2]}, initialDate: ${initialDate}`);
    } else {
        // Default to today
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        initialDate = new Date(`${year}-${month}-${day}T00:00:00`);
        console.log(`Using today's date: ${year}-${month}-${day}, initialDate: ${initialDate}`);
    }

    // Initialize calendar if the element exists
    const calendarEl = document.getElementById('events-calendar');
    let calendar; // Declare calendar variable in broader scope
    if (calendarEl) {
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            initialDate: initialDate,
            headerToolbar: {
                left: 'prev',
                center: 'title',
                right: 'next'
            },
            dateClick: function(info) {
                // Update the events list for the clicked date
                currentDate = new Date(info.dateStr);
                loadEvents(currentDate);
            },
            height: 'auto',
            dayMaxEvents: false,
            nowIndicator: true,
            firstDay: 1,
            locale: 'en',
            timeZone: 'local'  // Ensure we use local timezone
        });
        
        calendar.render();
        
        // Debug: Check what the calendar thinks "now" is
        console.log(`Calendar initial date: ${initialDate}`);
        console.log(`Calendar current date: ${calendar.getDate()}`);
        console.log(`JavaScript new Date(): ${new Date()}`);
        console.log(`JavaScript new Date().toDateString(): ${new Date().toDateString()}`);
    }

    // Initialize events list if the element exists
    const eventsListEl = document.getElementById('events-list');
    const selectedDateDisplayEl = document.getElementById('selected-date-display');
    const searchInput = document.getElementById('search-input');
    if (eventsListEl) {
        const prevDayBtn = document.getElementById('prev-day');
        const nextDayBtn = document.getElementById('next-day');
        let currentDate = initialDate;
        let searchTimeout;

        // Add search functionality
        searchInput.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                loadEvents(currentDate);
                return;
            }

            searchTimeout = setTimeout(() => {
                // Show loading state
                eventsListEl.innerHTML = '<div class="loading">Searching...</div>';
                
                fetch('/search?q=' + encodeURIComponent(query))
                .then(response => response.json())
                .then(events => {
                    if (events.length === 0) {
                        eventsListEl.innerHTML = '<p>No events found matching your search.</p>';
                    } else {
                        const eventsHtml = events.map(event => `
                            <div class="event-item">
                                <div class="event-time">${formatTime(event.start)}</div>
                                <div class="event-title">
                                    ${event.title}
                                    ${event.is_virtual ? '<span class="badge bg-primary ms-2">Virtual</span>' : ''}
                                    ${event.is_hybrid ? '<span class="badge bg-success ms-2">Hybrid</span>' : ''}
                                </div>
                                ${event.description ? `<div class="event-description">${event.description}</div>` : ''}
                                ${event.venue ? `<div class="event-venue">at ${event.venue}</div>` : ''}
                                ${event.url ? `
                                    <div class="mt-2">
                                        <a href="${event.url}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="fas fa-external-link-alt"></i> ${event.is_virtual || event.is_hybrid ? 'Join Event' : 'View Details'}
                                        </a>
                                    </div>
                                ` : ''}
                            </div>
                        `).join('');
                        eventsListEl.innerHTML = eventsHtml;
                    }
                })
                .catch(error => {
                    console.error('Error searching events:', error);
                    eventsListEl.innerHTML = '<p>Error searching events. Please try again.</p>';
                });
            }, 300); // Debounce search for 300ms
        });

        function loadEvents(date) {
            // Use local date formatting to avoid timezone issues
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            
            console.log(`Loading events for date: ${dateStr} (Date object: ${date})`);
            
            // Update the date display - use the Date object directly
            selectedDateDisplayEl.textContent = formatDateForDisplay(date);
            
            // Highlight the selected date in calendar
            highlightSelectedDate(date);
            
            // Create a placeholder with the same height as current content
            const placeholder = document.createElement('div');
            placeholder.style.height = eventsListEl.offsetHeight + 'px';
            placeholder.style.backgroundColor = '#f8f9fa';
            placeholder.style.borderRadius = '4px';
            eventsListEl.innerHTML = '';
            eventsListEl.appendChild(placeholder);

            fetch('/events?date=' + dateStr)
            .then(response => response.json())
            .then(events => {
                if (events.length === 0) {
                    eventsListEl.innerHTML = '<p>No events scheduled for this day.</p>';
                } else {
                    const eventsHtml = events.map(event => `
                        <div class="event-item">
                            <div class="event-time">${formatTime(event.start)}</div>
                            <div class="event-title">
                                ${event.title}
                                ${event.is_virtual ? '<span class="badge bg-primary ms-2">Virtual</span>' : ''}
                                ${event.is_hybrid ? '<span class="badge bg-success ms-2">Hybrid</span>' : ''}
                            </div>
                            ${event.description ? `<div class="event-description">${event.description}</div>` : ''}
                            ${event.venue ? `<div class="event-venue">at ${event.venue}</div>` : ''}
                            ${event.url ? `
                                <div class="mt-2">
                                    <a href="${event.url}" target="_blank" class="btn btn-sm btn-primary">
                                        <i class="fas fa-external-link-alt"></i> ${event.is_virtual || event.is_hybrid ? 'Join Event' : 'View Details'}
                                    </a>
                                </div>
                            ` : ''}
                        </div>
                    `).join('');
                    eventsListEl.innerHTML = eventsHtml;
                }
            })
            .catch(error => {
                console.error('Error loading events:', error);
                eventsListEl.innerHTML = '<p>Error loading events. Please try again.</p>';
            });
        }

        function formatTime(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
        }

        function formatDateForDisplay(date) {
            const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'long' });
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const year = String(date.getFullYear()).slice(-2);
            return `${dayOfWeek} (${month}-${day}-${year})`;
        }

        function highlightSelectedDate(date) {
            // Remove previous selection
            const prevSelected = document.querySelector('.fc-day.selected-date');
            if (prevSelected) {
                prevSelected.classList.remove('selected-date');
            }
            
            // Add selection to current date - use timezone-safe date formatting
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            
            // Try to find the day element with the exact date string
            const dayElement = document.querySelector(`[data-date="${dateStr}"]`);
            if (dayElement) {
                dayElement.classList.add('selected-date');
                console.log(`Highlighted date: ${dateStr}`);
            } else {
                console.log(`Could not find day element for date: ${dateStr}`);
            }
        }

        function goToPreviousDay() {
            currentDate.setDate(currentDate.getDate() - 1);
            loadEvents(currentDate);
            // Update calendar to show the new date
            if (calendar) {
                calendar.gotoDate(currentDate);
                // Highlight the selected date immediately
                highlightSelectedDate(currentDate);
            }
        }

        function goToNextDay() {
            currentDate.setDate(currentDate.getDate() + 1);
            loadEvents(currentDate);
            // Update calendar to show the new date
            if (calendar) {
                calendar.gotoDate(currentDate);
                // Highlight the selected date immediately
                highlightSelectedDate(currentDate);
            }
        }

        // Add event listeners
        prevDayBtn.addEventListener('click', goToPreviousDay);
        nextDayBtn.addEventListener('click', goToNextDay);

        // Load initial events
        loadEvents(currentDate);
    }
});