(function() {
    const config = typeof flaskEvents !== 'undefined' ? flaskEvents : {};
    const apiBase = (config.flaskUrl || '').replace(/\/$/, '');
    const DEBUG_EVENT_URL_FALLBACK = config.fallbackEventUrl || 'https://thedetroitilove.com';

    window.EVENT_LINK_ARROW = config.eventLinkArrow || '→';

    function apiUrl(path) {
        return apiBase + path;
    }

    function getEventArrowUrl(event) {
        return event.url || DEBUG_EVENT_URL_FALLBACK;
    }

    function escapeHtml(text) {
        if (text == null) {
            return '';
        }
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatVenueHtml(event) {
        const venueName = event.venue || 'No venue';
        if (event.venue_id && apiBase) {
            return `<a href="${apiUrl('/venues/' + event.venue_id)}" class="venue-link" target="_blank" rel="noopener"><strong>${escapeHtml(venueName)}</strong></a>`;
        }
        return `<strong>${escapeHtml(venueName)}</strong>`;
    }

    function getRecurrenceSuffix(event) {
        let recurrenceSuffix = '';
        if (!event.is_recurring || !event.rrule) {
            return recurrenceSuffix;
        }

        const rrule = event.rrule.toUpperCase();

        let interval = '';
        const intervalMatch = rrule.match(/INTERVAL=(\d+)/);
        if (intervalMatch && intervalMatch[1] !== '1') {
            interval = `Every ${intervalMatch[1]} `;
        }

        let endDateStr = '';
        if (event.recurring_until) {
            const endDate = new Date(event.recurring_until);
            endDateStr = endDate.toLocaleDateString('en-US', {
                month: 'numeric',
                day: 'numeric',
                year: 'numeric'
            });
        }

        const bydayMatch = rrule.match(/BYDAY=([^;]+)/);
        if (bydayMatch) {
            const byday = bydayMatch[1];
            const ordinalMatch = byday.match(/(\d+)(MO|TU|WE|TH|FR|SA|SU)/);
            if (ordinalMatch) {
                const ordinal = ordinalMatch[1];
                const day = ordinalMatch[2];
                const dayNames = { 'MO': 'Monday', 'TU': 'Tuesday', 'WE': 'Wednesday', 'TH': 'Thursday', 'FR': 'Friday', 'SA': 'Saturday', 'SU': 'Sunday' };
                const ordinalNames = { '1': '1st', '2': '2nd', '3': '3rd', '4': '4th', '5': '5th' };

                if (rrule.includes('FREQ=MONTHLY') || rrule.includes('FREQ=YEARLY')) {
                    const baseText = `${ordinalNames[ordinal] || ordinal} ${dayNames[day]}`;
                    recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                }
            } else {
                const days = byday.split(',').map(d => {
                    const dayNames = { 'MO': 'Mon', 'TU': 'Tue', 'WE': 'Wed', 'TH': 'Thu', 'FR': 'Fri', 'SA': 'Sat', 'SU': 'Sun' };
                    return dayNames[d] || d;
                });

                if (rrule.includes('FREQ=WEEKLY')) {
                    const baseText = days.length === 1 ? days[0] : days.join(', ');
                    recurrenceSuffix = endDateStr ? ` <i>(${baseText} until ${endDateStr})</i>` : ` <i>(${baseText})</i>`;
                }
            }
        }

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

        return recurrenceSuffix;
    }

    function createEventHtml(event) {
        const arrowSymbol = window.EVENT_LINK_ARROW || '→';
        const eventTitle = escapeHtml(event.title);
        const venueHtml = formatVenueHtml(event);
        const startTime = formatTime(event.start);
        const endTime = formatTime(event.end);
        const descriptionText = event.description ? escapeHtml(event.description) : '';
        const recurrenceSuffix = getRecurrenceSuffix(event);
        const arrowUrl = getEventArrowUrl(event);

        let html = '<div class="event-line">';
        html += `<a href="${escapeHtml(arrowUrl)}" target="_blank" rel="noopener" class="event-arrow-link" title="Event link">`;
        html += `<span class="event-arrow">${arrowSymbol}</span>`;
        html += '</a>';
        html += '<span class="event-text">';
        html += `${eventTitle} : ${venueHtml} : ${startTime} - ${endTime}`;
        if (descriptionText || recurrenceSuffix) {
            html += ` : ${descriptionText}${recurrenceSuffix}`;
        }
        html += '</span>';

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

    function renderEventsList(events, eventsListEl, viewingDate) {
        if (events.length === 0) {
            eventsListEl.innerHTML = '<p>No events scheduled for this day.</p>';
            return;
        }

        const ongoingEvents = [];
        const newEvents = [];

        events.forEach(event => {
            const eventStart = new Date(event.start);
            const eventEnd = new Date(event.end);
            const previousDay = new Date(viewingDate);
            previousDay.setDate(previousDay.getDate() - 1);
            const startOfCurrentDay = new Date(viewingDate);
            startOfCurrentDay.setHours(0, 0, 0, 0);

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

        if (ongoingEvents.length > 0) {
            eventsHtml += '<div class="time-group ongoing-section">';
            eventsHtml += '<div class="time-header">ONGOING</div>';
            ongoingEvents.forEach(event => {
                eventsHtml += createEventHtml(event);
            });
            eventsHtml += '</div>';
        }

        const timeGroups = {};
        newEvents.forEach(event => {
            const timeKey = formatTime(event.start);
            if (!timeGroups[timeKey]) {
                timeGroups[timeKey] = [];
            }
            timeGroups[timeKey].push(event);
        });

        Object.keys(timeGroups).sort((a, b) => {
            const timeA = new Date(`2000-01-01 ${a}`);
            const timeB = new Date(`2000-01-01 ${b}`);
            return timeA - timeB;
        }).forEach(timeKey => {
            eventsHtml += '<div class="time-group">';
            eventsHtml += `<div class="time-header">${timeKey}</div>`;
            timeGroups[timeKey].forEach(event => {
                eventsHtml += createEventHtml(event);
            });
            eventsHtml += '</div>';
        });

        eventsListEl.innerHTML = eventsHtml;
    }

    document.addEventListener('DOMContentLoaded', function() {
        const today = new Date();
        const initialDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

        const calendarEl = document.getElementById('events-calendar');
        let calendar;
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
                    const eventsListEl = document.getElementById('events-list');
                    if (eventsListEl && typeof window.flaskEventsLoadDay === 'function') {
                        window.flaskEventsLoadDay(new Date(info.dateStr + 'T00:00:00'));
                    } else if (apiBase) {
                        window.location.href = apiUrl('/day/' + info.dateStr);
                    }
                },
                height: 'auto',
                dayMaxEvents: false,
                nowIndicator: true,
                firstDay: 1,
                locale: 'en',
                timeZone: 'local'
            });

            calendar.render();
        }

        const eventsListEl = document.getElementById('events-list');
        const selectedDateDisplayEl = document.getElementById('selected-date-display');

        if (!eventsListEl || !apiBase) {
            return;
        }

        const prevDayBtn = document.getElementById('prev-day');
        const nextDayBtn = document.getElementById('next-day');
        const prevDayBottomBtn = document.getElementById('prev-day-bottom');
        const nextDayBottomBtn = document.getElementById('next-day-bottom');
        let currentDate = initialDate;

        function highlightSelectedDate(date) {
            const prevSelected = document.querySelector('.flask-events-wrap .fc-day.selected-date');
            if (prevSelected) {
                prevSelected.classList.remove('selected-date');
            }

            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            const dayElement = document.querySelector(`.flask-events-wrap [data-date="${dateStr}"]`);
            if (dayElement) {
                dayElement.classList.add('selected-date');
            }
        }

        function beginListUpdate() {
            const scrollX = window.scrollX;
            const scrollY = window.scrollY;
            const listHeight = Math.max(eventsListEl.offsetHeight, 200);
            eventsListEl.style.minHeight = listHeight + 'px';
            eventsListEl.innerHTML = '<div class="loading">Loading...</div>';
            return { scrollX, scrollY };
        }

        function finishListUpdate(scrollX, scrollY) {
            eventsListEl.style.minHeight = '';
            requestAnimationFrame(() => {
                window.scrollTo(scrollX, scrollY);
            });
        }

        function loadEvents(date) {
            currentDate = new Date(date);
            const year = currentDate.getFullYear();
            const month = String(currentDate.getMonth() + 1).padStart(2, '0');
            const day = String(currentDate.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;

            if (selectedDateDisplayEl) {
                selectedDateDisplayEl.textContent = formatDateForDisplay(currentDate);
            }

            highlightSelectedDate(currentDate);
            const scrollPos = beginListUpdate();

            fetch(apiUrl((config.eventsEndpoint || '/events') + '?date=' + dateStr))
                .then(response => response.json())
                .then(events => {
                    renderEventsList(events, eventsListEl, currentDate);
                    finishListUpdate(scrollPos.scrollX, scrollPos.scrollY);
                })
                .catch(error => {
                    console.error('Error loading events:', error);
                    eventsListEl.innerHTML = '<p>Error loading events. Please try again.</p>';
                    finishListUpdate(scrollPos.scrollX, scrollPos.scrollY);
                });
        }

        window.flaskEventsLoadDay = loadEvents;

        function goToPreviousDay(e) {
            if (e) e.preventDefault();
            currentDate.setDate(currentDate.getDate() - 1);
            loadEvents(currentDate);
            if (calendar) {
                calendar.gotoDate(currentDate);
            }
        }

        function goToNextDay(e) {
            if (e) e.preventDefault();
            currentDate.setDate(currentDate.getDate() + 1);
            loadEvents(currentDate);
            if (calendar) {
                calendar.gotoDate(currentDate);
            }
        }

        if (prevDayBtn) prevDayBtn.addEventListener('click', goToPreviousDay);
        if (nextDayBtn) nextDayBtn.addEventListener('click', goToNextDay);
        if (prevDayBottomBtn) prevDayBottomBtn.addEventListener('click', goToPreviousDay);
        if (nextDayBottomBtn) nextDayBottomBtn.addEventListener('click', goToNextDay);

        loadEvents(currentDate);
    });
})();
