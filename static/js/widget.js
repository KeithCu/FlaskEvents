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
                        // Group search results by time
                        const timeGroups = {};
                        events.forEach(event => {
                            const timeKey = formatTime(event.start);
                            if (!timeGroups[timeKey]) {
                                timeGroups[timeKey] = [];
                            }
                            timeGroups[timeKey].push(event);
                        });
                        
                        let eventsHtml = '';
                        
                        // Sort time groups and create HTML
                        Object.keys(timeGroups).sort((a, b) => {
                            const timeA = new Date(`2000-01-01 ${a}`);
                            const timeB = new Date(`2000-01-01 ${b}`);
                            return timeA - timeB;
                        }).forEach(timeKey => {
                            eventsHtml += '<div class="time-group">';
                            eventsHtml += `<div class="time-header">${timeKey}</div>`;
                            timeGroups[timeKey].forEach(event => {
                                eventsHtml += createEventHtml(event, false);
                            });
                            eventsHtml += '</div>';
                        });
                        
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
                    // Separate ongoing events from new events
                    const ongoingEvents = [];
                    const newEvents = [];
                    const currentTime = new Date();
                    
                    events.forEach(event => {
                        const eventStart = new Date(event.start);
                        const eventEnd = new Date(event.end);
                        
                        // Check if event started the previous day and is still ongoing
                        const previousDay = new Date(date);
                        previousDay.setDate(previousDay.getDate() - 1);
                        const startOfCurrentDay = new Date(date);
                        startOfCurrentDay.setHours(0, 0, 0, 0);
                        
                        // Event is ongoing if it started on the previous day and ends after the start of current day
                        if (eventStart.getDate() === previousDay.getDate() && 
                            eventStart.getMonth() === previousDay.getMonth() && 
                            eventStart.getFullYear() === previousDay.getFullYear() &&
                            eventEnd > startOfCurrentDay) {
                            ongoingEvents.push(event);
                        } else {
                            newEvents.push(event);
                        }
                    });
                    
                    let eventsHtml = '';
                    
                    // Add ongoing section if there are ongoing events
                    if (ongoingEvents.length > 0) {
                        eventsHtml += '<div class="time-group ongoing-section">';
                        eventsHtml += '<div class="time-header">ONGOING</div>';
                        ongoingEvents.forEach(event => {
                            eventsHtml += createEventHtml(event, true);
                        });
                        eventsHtml += '</div>';
                    }
                    
                    // Group new events by time
                    const timeGroups = {};
                    newEvents.forEach(event => {
                        const timeKey = formatTime(event.start);
                        if (!timeGroups[timeKey]) {
                            timeGroups[timeKey] = [];
                        }
                        timeGroups[timeKey].push(event);
                    });
                    
                    // Sort time groups and create HTML
                    Object.keys(timeGroups).sort((a, b) => {
                        const timeA = new Date(`2000-01-01 ${a}`);
                        const timeB = new Date(`2000-01-01 ${b}`);
                        return timeA - timeB;
                    }).forEach(timeKey => {
                        eventsHtml += '<div class="time-group">';
                        eventsHtml += `<div class="time-header">${timeKey}</div>`;
                        timeGroups[timeKey].forEach(event => {
                            eventsHtml += createEventHtml(event, false);
                        });
                        eventsHtml += '</div>';
                    });
                    
                    eventsListEl.innerHTML = eventsHtml;
                }
            })
            .catch(error => {
                console.error('Error loading events:', error);
                eventsListEl.innerHTML = '<p>Error loading events. Please try again.</p>';
            });
        }

        function createEventHtml(event, isOngoing) {
            const arrowSymbol = '→';
            const eventTitle = event.title;
            const venueText = event.venue ? event.venue : 'No venue';
            const startTime = formatTime(event.start);
            const endTime = formatTime(event.end);
            const descriptionText = event.description ? event.description : '';
            
            // Get recurrence type for display
            let recurrenceSuffix = '';
            if (event.is_recurring && event.rrule) {
                const rrule = event.rrule.toUpperCase();
                
                // Check for interval (e.g., every 2 weeks)
                let interval = '';
                const intervalMatch = rrule.match(/INTERVAL=(\d+)/);
                if (intervalMatch && intervalMatch[1] !== '1') {
                    interval = `Every ${intervalMatch[1]} `;
                }
                
                // Get end date if available
                let endDateStr = '';
                if (event.recurring_until) {
                    const endDate = new Date(event.recurring_until);
                    endDateStr = endDate.toLocaleDateString('en-US', { 
                        month: 'numeric', 
                        day: 'numeric',
                        year: 'numeric'
                    });
                }
                
                // Check for day of week patterns
                const bydayMatch = rrule.match(/BYDAY=([^;]+)/);
                if (bydayMatch) {
                    const byday = bydayMatch[1];
                    
                    // Check for ordinal day patterns (1MO = 1st Monday, 2TU = 2nd Tuesday, etc.)
                    const ordinalMatch = byday.match(/(\d+)(MO|TU|WE|TH|FR|SA|SU)/);
                    if (ordinalMatch) {
                        const ordinal = ordinalMatch[1];
                        const day = ordinalMatch[2];
                        const dayNames = { 'MO': 'Monday', 'TU': 'Tuesday', 'WE': 'Wednesday', 'TH': 'Thursday', 'FR': 'Friday', 'SA': 'Saturday', 'SU': 'Sunday' };
                        const ordinalNames = { '1': '1st', '2': '2nd', '3': '3rd', '4': '4th', '5': '5th' };
                        
                        if (rrule.includes('FREQ=MONTHLY')) {
                            const baseText = `${ordinalNames[ordinal] || ordinal} ${dayNames[day]}`;
                            recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                        } else if (rrule.includes('FREQ=YEARLY')) {
                            const baseText = `${ordinalNames[ordinal] || ordinal} ${dayNames[day]}`;
                            recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                        }
                    } else {
                        // Regular day of week
                        const days = byday.split(',').map(d => {
                            const dayNames = { 'MO': 'Mon', 'TU': 'Tue', 'WE': 'Wed', 'TH': 'Thu', 'FR': 'Fri', 'SA': 'Sat', 'SU': 'Sun' };
                            return dayNames[d] || d;
                        });
                        
                        if (rrule.includes('FREQ=WEEKLY')) {
                            if (days.length === 1) {
                                const baseText = days[0];
                                recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                            } else {
                                const baseText = days.join(', ');
                                recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                            }
                        }
                    }
                }
                
                // If no specific pattern found, use basic frequency
                if (!recurrenceSuffix) {
                    if (rrule.includes('FREQ=DAILY')) {
                        const baseText = `${interval}Daily`;
                        recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                    } else if (rrule.includes('FREQ=WEEKLY')) {
                        const baseText = `${interval}Weekly`;
                        recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                    } else if (rrule.includes('FREQ=MONTHLY')) {
                        const baseText = `${interval}Monthly`;
                        recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                    } else if (rrule.includes('FREQ=YEARLY')) {
                        const baseText = `${interval}Yearly`;
                        recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                    } else {
                        const baseText = 'Recurring';
                        recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                    }
                }
            }
            
            const fullText = `${eventTitle} : ${venueText} : ${startTime} - ${endTime} : ${descriptionText}${recurrenceSuffix}`;
            
            let html = '<div class="event-line">';
            
            if (event.url) {
                html += `<a href="${event.url}" target="_blank" class="event-link">`;
                html += `<span class="event-arrow">${arrowSymbol}</span>`;
                html += `<span class="event-text">${fullText}</span>`;
                html += '</a>';
            } else {
                html += `<span class="event-arrow">${arrowSymbol}</span>`;
                html += `<span class="event-text">${fullText}</span>`;
            }
            
            // Add badges for virtual/hybrid events
            if (event.is_virtual) {
                html += '<span class="badge bg-primary ms-2">Virtual</span>';
            }
            if (event.is_hybrid) {
                html += '<span class="badge bg-success ms-2">Hybrid</span>';
            }
            
            html += '</div>';
            return html;
        }

        function formatTime(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            }).replace(/\s/g, '');
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