document.addEventListener('DOMContentLoaded', function() {
    // Initialize calendar if the element exists
    const calendarEl = document.getElementById('events-calendar');
    if (calendarEl) {
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev',
                center: 'title',
                right: 'next'
            },
            dateClick: function(info) {
                // Redirect to the day view
                window.location.href = '/day/' + info.dateStr;
            },
            height: 'auto',
            dayMaxEvents: false,
            nowIndicator: true,
            firstDay: 1,
            locale: 'en'
        });
        
        calendar.render();
    }

    // Initialize events list if the element exists
    const eventsListEl = document.getElementById('events-list');
    if (eventsListEl) {
        const prevDayBtn = document.getElementById('prev-day');
        const nextDayBtn = document.getElementById('next-day');
        let currentDate = new Date();

        function loadEvents(date) {
            const dateStr = date.toISOString().split('T')[0];
            eventsListEl.innerHTML = '';  // Start with empty content

            fetch('/events?date=' + dateStr)
            .then(response => response.json())
            .then(events => {
                if (events.length === 0) {
                    eventsListEl.innerHTML = '<p>No events scheduled for this day.</p>';
                    return;
                }

                const eventsHtml = events.map(event => `
                    <div class="event-item">
                        <div class="event-time">${formatTime(event.start)}</div>
                        <div class="event-title">${event.title}</div>
                        ${event.description ? `<div class="event-description">${event.description}</div>` : ''}
                        ${event.venue_name ? `<div class="event-venue">at ${event.venue_name}</div>` : ''}
                    </div>
                `).join('');

                eventsListEl.innerHTML = eventsHtml;
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

        function goToPreviousDay() {
            currentDate.setDate(currentDate.getDate() - 1);
            loadEvents(currentDate);
        }

        function goToNextDay() {
            currentDate.setDate(currentDate.getDate() + 1);
            loadEvents(currentDate);
        }

        // Add event listeners
        prevDayBtn.addEventListener('click', goToPreviousDay);
        nextDayBtn.addEventListener('click', goToNextDay);

        // Load initial events
        loadEvents(currentDate);
    }
}); 