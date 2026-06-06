document.addEventListener('DOMContentLoaded', function() {
    const apiBase = (typeof flaskEvents !== 'undefined' && flaskEvents.flaskUrl)
        ? flaskEvents.flaskUrl.replace(/\/$/, '')
        : '';
    const eventsPath = (typeof flaskEvents !== 'undefined' && flaskEvents.eventsEndpoint)
        ? flaskEvents.eventsEndpoint
        : '/events';
    const eventsUrl = apiBase + eventsPath;

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
                if (apiBase) {
                    window.location.href = apiBase + '/day/' + info.dateStr;
                }
            },
            height: 'auto',
            dayMaxEvents: false,
            nowIndicator: true,
            firstDay: 1,
            locale: 'en'
        });

        calendar.render();
    }

    const eventsListEl = document.getElementById('events-list');
    if (eventsListEl) {
        const prevDayBtn = document.getElementById('prev-day');
        const nextDayBtn = document.getElementById('next-day');
        let currentDate = new Date();

        function loadEvents(date) {
            const dateStr = date.toISOString().split('T')[0];
            eventsListEl.innerHTML = '';

            fetch(eventsUrl + '?date=' + dateStr)
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

        if (prevDayBtn) {
            prevDayBtn.addEventListener('click', goToPreviousDay);
        }
        if (nextDayBtn) {
            nextDayBtn.addEventListener('click', goToNextDay);
        }

        loadEvents(currentDate);
    }
});
