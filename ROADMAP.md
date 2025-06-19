# Events Calendar Enhancement Plan

This document outlines a plan to enhance your Flask-based events calendar prototype, designed as a fast replacement for The Events Calendar Pro plugin. Your prototype already supports one-time and recurring events, daily and monthly views, event management (add/edit/delete), full-text search, and API endpoints with caching for performance. To make it a comprehensive alternative, this plan incorporates key features inspired by The Events Calendar Pro, adapted for your Flask application. Each feature is ranked by importance, with detailed descriptions and implementation guidance for offline development.

## Features to Add

### 1. Venue and Organizer Management
- **Description**: Enable users to create and manage venues (event locations) and organizers (individuals or organizations hosting events). Associate events with venues and organizers, and display their details on dedicated pages or sections.
- **Importance**: High (Rank: 1)
- **Why It's Important**: Complete event information includes where and who is hosting the event, enhancing professionalism and usability. This is critical for users seeking detailed event context.
- **Implementation Considerations**:
  - **Database**:
    - Create `Venue` model: `id` (primary key), `name`, `address`, `city`, `state`, `zip`, `country`, `latitude`, `longitude`.
    - Create `Organizer` model: `id` (primary key), `name`, `email`, `phone`, `website`.
    - Update `Event` model to include `venue_id` and `organizer_id` as foreign keys.
    - Use SQLAlchemy to define relationships (e.g., `Event.venue = relationship('Venue')`).
  - **UI**:
    - Add routes and templates for creating/editing venues (`/venues/new`, `/venues/<id>/edit`) and organizers (`/organizers/new`, `/organizers/<id>/edit`).
    - Include dropdowns or search fields in the event creation form (`event_form.html`) to select venues and organizers.
    - Create templates for venue and organizer pages (`/venues/<id>`, `/organizers/<id>`) to display details and associated events.
  - **API**:
    - Extend the `/events` endpoint to include venue and organizer details (e.g., `{"id": 1, "title": "Event", "venue": {"name": "Venue Name", "address": "123 Main St"}}`).
  - **Example Code**:
    ```python
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

    class Venue(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        address = db.Column(db.String(200))
        latitude = db.Column(db.Float)
        longitude = db.Column(db.Float)

    class Event(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(100), nullable=False)
        venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'))
        venue = db.relationship('Venue', backref='events')
    ```

### 2. Custom Event Fields
- **Description**: Allow users to add custom fields to events (e.g., event type, category, ticket price) to accommodate diverse event requirements.
- **Importance**: High (Rank: 2)
- **Why It's Important**: Custom fields provide flexibility, enabling users to tailor event information to their needs, such as adding dress codes or special instructions.
- **Implementation Considerations**:
  - **Database**:
    - Create a `CustomField` model: `id`, `event_id` (foreign key), `field_name`, `field_value`, `field_type` (e.g., text, number, dropdown).
    - Use a flexible schema to store multiple fields per event.
  - **UI**:
    - Add a dynamic section in `event_form.html` for users to add/edit custom fields (e.g., a button to add a new field with name and value).
    - Display custom fields on event details pages.
  - **API**:
    - Include custom fields in the `/events` endpoint response (e.g., `{"id": 1, "title": "Event", "custom_fields": [{"name": "Type", "value": "Workshop"}]}`).
  - **Example Code**:
    ```python
    class CustomField(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
        field_name = db.Column(db.String(50), nullable=False)
        field_value = db.Column(db.Text, nullable=False)
        event = db.relationship('Event', backref='custom_fields')
    ```

### 3. Filter and Search Enhancements
- **Description**: Enhance the existing full-text search to include advanced filtering options (e.g., by category, venue, organizer, date range, or custom fields).
- **Importance**: High (Rank: 3)
- **Why It's Important**: Advanced filtering improves user experience by helping users quickly find relevant events, especially in calendars with many events.
- **Implementation Considerations**:
  - **Database**:
    - Add a `category` field to the `Event` model or create a `Category` model with a many-to-many relationship.
    - Ensure indexes on `venue_id`, `organizer_id`, `category`, and `start_date` for efficient querying.
  - **UI**:
    - Add a filter bar above calendar views (e.g., in `day.html`, `month.html`) with dropdowns for categories, venues, organizers, and a date range picker.
    - Update the `/search` route to handle filter parameters.
  - **API**:
    - Modify the `/events` endpoint to accept query parameters (e.g., `?category=workshop&venue_id=1&start=2025-06-01&end=2025-06-30`).
  - **Example Code**:
    ```python
    @app.route('/events')
    def get_events():
        category = request.args.get('category')
        venue_id = request.args.get('venue_id')
        query = Event.query
        if category:
            query = query.filter(Event.category == category)
        if venue_id:
            query = query.filter(Event.venue_id == venue_id)
        events = query.all()
        return jsonify([event.to_dict() for event in events])
    ```

### 4. Map View
- **Description**: Add a map view to display events on a geographical map, showing their locations based on venue coordinates.
- **Importance**: Medium to High (Rank: 4)
- **Why It's Important**: For events with physical locations, a map view helps users visualize event locations, improving accessibility and engagement.
- **Implementation Considerations**:
  - **Frontend**:
    - Use Leaflet.js ([Leaflet](https://leafletjs.com/)) for a lightweight, open-source mapping library.
    - Add a `/map` route and `map.html` template to render the map view.
  - **Database**:
    - Ensure the `Venue` model includes `latitude` and `longitude` fields.
  - **API**:
    - Create an endpoint like `/events/map` to return events with venue coordinates (e.g., `{"id": 1, "title": "Event", "venue": {"latitude": 40.7128, "longitude": -74.0060}}`).
  - **Example Code**:
    ```html
    <!-- map.html -->
    <div id="map" style="height: 500px;"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([40.7128, -74.0060], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        fetch('/events/map')
            .then(response => response.json())
            .then(events => {
                events.forEach(event => {
                    L.marker([event.venue.latitude, event.venue.longitude])
                        .addTo(map)
                        .bindPopup(event.title);
                });
            });
    </script>
    ```

### 5. Virtual and Hybrid Events Support - DONE!

### 6. Duplicate Events Feature
- **Description**: Allow users to duplicate existing events, creating a new event with the same details but editable fields (e.g., date).
- **Importance**: Medium (Rank: 6)
- **Why It's Important**: Duplicating events saves time for users creating similar events, improving efficiency.
- **Implementation Considerations**:
  - **Backend**:
    - Create a route like `/event/<id>/duplicate` that copies an event's details to a new event.
  - **UI**:
    - Add a "Duplicate" button on the event details page or in the event list.
  - **API**:
    - Optionally, add an endpoint like `/events/<id>/duplicate`.
  - **Example Code**:
    ```python
    @app.route('/event/<int:id>/duplicate', methods=['POST'])
    def duplicate_event(id):
        event = Event.query.get_or_404(id)
        new_event = Event(
            title=event.title,
            description=event.description,
            venue_id=event.venue_id
        )
        db.session.add(new_event)
        db.session.commit()
        return redirect(url_for('edit_event', id=new_event.id))
    ```

### 7. API for Embedding
- **Description**: Provide robust API endpoints to embed the calendar or event lists into other parts of the site or external applications.
- **Importance**: High (Rank: 7)
- **Why It's Important**: Flexible embedding options allow the calendar to be integrated into various contexts, similar to WordPress shortcodes.
- **Implementation Considerations**:
  - **API**:
    - Enhance the `/events` endpoint to support flexible queries (e.g., by date range, category, venue).
    - Provide a JavaScript widget for embedding (e.g., a script that fetches events and renders them with FullCalendar).
  - **Frontend**:
    - Create a sample embeddable widget in `static/js/calendar_widget.js`.
  - **Example Code**:
    ```javascript
    // static/js/calendar_widget.js
    fetch('/events?start=2025-06-01&end=2025-06-30')
        .then(response => response.json())
        .then(events => {
            var calendar = new FullCalendar.Calendar(document.getElementById('calendar'), {
                events: events
            });
            calendar.render();
        });
    ```

### 8. Integrations with Video Conferencing Tools
- **Description**: Support automatic generation or embedding of video conferencing links (e.g., Zoom, Google Meet) for virtual events.
- **Importance**: Medium to High (Rank: 8)
- **Why It's Important**: Simplifies the management of virtual events by integrating with popular platforms.
- **Implementation Considerations**:
  - **Database**:
    - Store video conferencing details in the `Event` model (e.g., `meeting_platform`, `meeting_id`, `join_url`).
  - **UI**:
    - Add fields for video conferencing details in `event_form.html`.
    - Display a "Join Meeting" button on event pages.
  - **API**:
    - Include video conferencing details in the `/events` endpoint.
  - **Example Code**:
    ```python
    class Event(db.Model):
        meeting_platform = db.Column(db.String(50))  # e.g., Zoom, Google Meet
        join_url = db.Column(db.String(200))
    ```

### 9. Live-stream Embed
- **Description**: Allow embedding of live streams from platforms like YouTube or Facebook on event pages.
- **Importance**: Medium (Rank: 9)
- **Why It's Important**: Enhances virtual event pages by allowing attendees to watch streams without leaving the site.
- **Implementation Considerations**:
  - **Database**:
    - Use the `live_stream_url` field in the `Event` model.
  - **UI**:
    - Embed the stream in the event details page using an iframe.
  - **Example Code**:
    ```html
    <!-- event_details.html -->
    {% if event.live_stream_url %}
        <iframe src="{{ event.live_stream_url }}" width="560" height="315"></iframe>
    {% endif %}
    ```

### 10. Alternative Calendar Views
- **Description**: Add additional calendar views, such as week view, photo view, or summary view.
- **Importance**: Low to Medium (Rank: 10)
- **Why It's Important**: Different views cater to varied user preferences, enhancing the calendar's versatility.
- **Implementation Considerations**:
  - **Week View**:
    - Use FullCalendar's week view (`timeGridWeek`) in `month.html`.
  - **Photo View**:
    - Add a `featured_image` field to the `Event` model.
    - Create a `/photo` route and `photo.html` template to display events as a gallery.
  - **Summary View**:
    - Create a `/summary` route to display a condensed event list.
  - **Example Code**:
    ```javascript
    // month.html (for week view)
    var calendar = new FullCalendar.Calendar(document.getElementById('calendar'), {
        initialView: 'timeGridWeek',
        events: '/events'
    });
    ```

## Development Roadmap
1. **Phase 1: Core Enhancements**
   - Implement Venue and Organizer Management.
   - Add Custom Event Fields.
   - Enhance Filter and Search functionality.
2. **Phase 2: Visual and Modern Features**
   - Add Map View.
   - Implement Virtual and Hybrid Events Support.
3. **Phase 3: Usability and Integration**
   - Add Duplicate Events Feature.
   - Enhance API for Embedding.
   - Integrate Video Conferencing Tools and Live-stream Embed.
4. **Phase 4: Additional Views**
   - Implement Alternative Calendar Views (week, photo, summary).

## Performance Considerations
- **Caching**: Extend your existing caching (using `cacheout`) to include venue, organizer, and map data to maintain performance.
- **Database**: Add indexes for new fields (e.g., `venue_id`, `category`) to ensure fast queries.
- **Frontend**: Use lazy loading for map and photo views to reduce initial load times.

## Conclusion
This plan prioritizes features that enhance functionality and user experience while aligning with your goal of a fast, efficient events calendar. Start with high-priority features (Venue and Organizer Management, Custom Event Fields, Filter Enhancements) to build a robust foundation, then add modern features like Map View and Virtual Events Support. The provided code snippets and implementation details should guide development without requiring external resources.