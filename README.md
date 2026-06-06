# Flask Event Calendar

A simple event calendar application built with [Flask](https://flask.palletsprojects.com/) and [FullCalendar](https://fullcalendar.io/).

## Features

- Monthly, weekly, and daily calendar views
- Create, edit, and delete events
- Recurring events support using iCalendar RRULE format
- Venue management
- Custom event colors
- Virtual and hybrid events support
- Full-text search functionality
- WordPress integration via widgets
- Advanced caching system with management interface

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Configuration

**⚠️ IMPORTANT: Before running the application, you must configure the `config.yaml` file!**

The application requires a `config.yaml` file in the root directory with the following settings:

```yaml
# Flask Events Calendar Configuration

# Database Settings
database:
  path: "events.db"

# Timezone Settings
timezone:
  local: "America/New_York"

# CORS Settings for WordPress Integration
cors:
  enabled: true
  origins:
    - "https://your-wordpress-domain.com"
    - "http://localhost:3000"  # For local development
  methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allow_headers: ["Content-Type", "Authorization"]
```

### Critical Configuration Notes:

- **CORS Origins**: Must include your WordPress domain for integration to work
- **Timezone**: Set to your local timezone (e.g., "America/New_York", "America/Chicago")
- **Database Path**: Default is "events.db" in the application root

**Without proper CORS configuration, the WordPress integration will fail!** The application will exit with an error if the config.yaml file is missing or malformed.

## Usage

- Click on any date to view the daily view
- Click the "New Event" button to create an event
- Click on an existing event to edit it
- Use the navigation buttons to move between months
- Switch between month, week, and day views using the view buttons
- Use the search functionality to find specific events
- Manage venues through the Venues section

## Recurring Events

The application supports recurring events using the iCalendar RRULE format.

**Examples:**

- Weekly on Monday, Wednesday, Friday: `FREQ=WEEKLY;BYDAY=MO,WE,FR`
- Daily: `FREQ=DAILY`
- Monthly on the 15th: `FREQ=MONTHLY;BYMONTHDAY=15`
- Every other week: `FREQ=WEEKLY;INTERVAL=2`
- First Monday of every month: `FREQ=MONTHLY;BYDAY=1MO`

**How it works:**

- **Storage**: Each recurring event is stored as a single row with its RRULE in the `rrule` column, plus `is_recurring` and `recurring_until` fields for the series end.
- **Expansion**: When a calendar or day view is requested, the backend expands recurring events into individual instances for the requested date range using the `dateutil.rrule` library.
- **Query logic**: For each request, the backend fetches non-recurring events in the date range directly, fetches recurring events that could have instances in the range (via an index on `is_recurring` and `recurring_until`), and expands only those relevant to the requested range.
- **Editing**: The event form lets users specify or edit the recurrence rule and series end date; the backend updates the relevant fields accordingly.

## WordPress Integration

This Flask Events Calendar can be integrated with WordPress using the included WordPress plugin, displaying the calendar on any WordPress site while keeping event data on the Flask backend.

### Quick Setup Steps

For a typical setup with Flask on a subdomain (e.g., `flaskevents.example.com`) and WordPress on the main domain (e.g., `example.com`):

1. **Copy WordPress Plugin Files**
   ```bash
   cp -r wp_flask_events/ /path/to/wordpress/wp-content/plugins/
   ```

2. **Activate the Plugin**
   - Go to WordPress admin → Plugins → Installed Plugins
   - Find "Events Calendar" and click **Activate**

3. **Configure Flask App URL**
   - Edit `wp_flask_events/wp_flask_events.php`
   - Update the `FLASK_EVENTS_URL` constant:
   ```php
   define('FLASK_EVENTS_URL', 'https://flaskevents.example.com');
   ```

4. **Configure CORS**
   - Set your WordPress domain in `config.yaml` (see [Configuration](#configuration) above)

5. **Add Widgets to WordPress**
   - Go to Appearance → Widgets
   - Add "Events Calendar" and "Events List" widgets to your sidebar

**Key Points:**
- **SSL Required**: Both sites need HTTPS for CORS to work properly
- **CORS Configuration**: Flask app must allow requests from your WordPress domain (via `config.yaml`)
- **Two Widgets Available**: Calendar widget (monthly view) and Events List widget (daily events)
- **No Database Changes**: WordPress and Flask remain completely separate

### Available WordPress Widgets

#### 1. Events Calendar Widget
- Displays a compact monthly calendar for event navigation
- Click on any date to view events for that day
- Navigation between months; responsive design for sidebars

#### 2. Events List Widget
- Shows all events for the current day
- Navigation buttons to move between days
- Displays event time, title, description, venue, virtual/hybrid badges, and event URLs

### Adding Widgets to Your WordPress Site

1. Go to **Appearance** → **Widgets** (or **Customize** → **Widgets**)
2. Drag "Events Calendar" to your desired widget area; set a custom title (optional); click **Save**
3. Drag "Events List" to your desired widget area; set a custom title (optional); click **Save**

### WordPress Integration Architecture

The WordPress integration uses a client-side approach. WordPress handles content while Flask handles event data, keeping event queries off the WordPress database.

```
WordPress Site                    Flask Events Calendar
┌─────────────────┐              ┌─────────────────────┐
│                 │              │                     │
│  WordPress      │              │  Flask App          │
│  Frontend       │              │  (Python)           │
│                 │              │                     │
│  ┌─────────────┐│              │  ┌─────────────────┐│
│  │   Widget    ││              │  │   Database      ││
│  │   (HTML)    ││              │  │   (SQLite)      ││
│  └─────────────┘│              │  └─────────────────┘│
│                 │              │                     │
│  ┌─────────────┐│              │  ┌─────────────────┐│
│  │ JavaScript  ││◄─────────────┤  │   API Endpoints ││
│  │   (Widget)  ││              │  │   (/events,     ││
│  └─────────────┘│              │  │    /search)     ││
│                 │              │  └─────────────────┘│
└─────────────────┘              └─────────────────────┘
```

### Configuration Options

- **Flask App URL**: Set in the WordPress plugin (`FLASK_EVENTS_URL`)
- **CORS**: Configure in `config.yaml` (see [Configuration](#configuration))
- **Widget CSS**: Customize via `wp_flask_events/css/flask-events.css`

### Security Considerations

- **CORS**: Configure allowed origins in `config.yaml` — see [Configuration](#configuration)
- **Rate limiting**: Consider rate limiting for `/events` and `/search` endpoints in production
- **Input validation**: The Flask app validates inputs; ensure WordPress-side validation for any user-submitted data

### Troubleshooting WordPress Integration

1. **Widgets Not Loading** — Verify the Flask app URL, confirm the app is running, check browser console for JavaScript errors
2. **CORS Errors** — Ensure your WordPress domain is in `config.yaml` CORS origins
3. **Events Not Displaying** — Verify the `/events` endpoint works and events exist in the database; check browser network tab
4. **Styling Issues** — WordPress theme CSS may conflict with widget styles; test with a default theme

**Debug mode:** Add `define('FLASK_EVENTS_DEBUG', true);` to `wp_flask_events.php` for additional troubleshooting output.

### Advanced Integration

For custom shortcodes, REST API proxying, plugin hooks, and widget development, see the source in `wp_flask_events/` — particularly `wp_flask_events.php` and the classes in `includes/`.

### WordPress Plugin Structure

```
wp_flask_events/
├── wp_flask_events.php          # Main plugin file
├── includes/
│   ├── class-flask-events-calendar-widget.php
│   └── class-flask-events-list-widget.php
├── css/
│   └── flask-events.css
└── js/
    └── flask-events.js
```

### Performance Benefits in WordPress Context

When integrated with WordPress, this solution provides several advantages:

1. **Decoupled Architecture**: WordPress handles content management while Flask handles event data
2. **Scalability**: Event data doesn't impact WordPress performance
3. **Caching**: Flask's caching layer works independently of WordPress caching
4. **Database Efficiency**: SQLite with clustered indexing vs WordPress's MySQL queries
5. **Resource Isolation**: Event processing doesn't compete with WordPress resources

### Deployment Considerations

**Flask app:** Use a production WSGI server (Gunicorn, uWSGI), reverse proxy (Nginx, Apache), SSL, and process management (systemd, supervisor).

**WordPress integration:** Ensure HTTPS for both sites, configure CORS for production domains, and set up monitoring.

**Database:** SQLite works well for moderate loads; consider PostgreSQL or MySQL for high traffic. Implement backups.

**Performance optimization:**

1. **Flask App**
   - Enable response compression
   - Configure proper caching headers
   - Use database connection pooling
   - Implement request rate limiting

2. **WordPress Plugin**
   - Minimize JavaScript and CSS
   - Use WordPress transients for caching
   - Implement lazy loading for widgets
   - Optimize API request frequency

## Architecture & Performance

**This calendar application solves a critical performance problem that plagues [WordPress Events Calendar Pro](https://theeventscalendar.com/products/wordpress-events-calendar/):**

- WordPress Events Calendar Pro starts to slow down around 1,000 events
- At 5,000 events, most queries take 2+ seconds per request
- This design provides nearly instantaneous speed even with a million events
- **Most requests complete in under 0.02 seconds** *(for non-cached requests)*

The performance difference is achieved through a clustered index database design that optimizes for calendar-specific queries, combined with a comprehensive caching layer that serves most requests nearly instantly.

### Database Design

This application uses a clustered index design for event storage, which has been proven to be more efficient than conventional indexing for calendar-based queries.

1. **Composite Primary Key (start_date, id)**
   - Events are physically stored in order by date, then by ID
   - Events for the same date are stored together on disk
   - Reduces disk I/O when querying events for a specific date or date range

2. **Performance Benefits**
   - Single day queries: ~32% faster than conventional indexing
   - 3-day range queries: ~32% faster than conventional indexing
   - 7-day range queries: ~12% faster than conventional indexing
   - More consistent performance (lower standard deviation in query times)

3. **Why This Matters**
   - Calendar applications typically query events by date ranges
   - Most queries are for single days or small ranges (1-7 days)
   - The clustered design optimizes for these common use cases
   - Reduces disk seeks and improves cache efficiency

**Conventional vs clustered index comparison:**

| Conventional | Clustered |
|---|---|
| Simple auto-incrementing primary key | Composite primary key (start_date, id) |
| Separate index on start_date | Events physically ordered by date |
| Events stored in insertion order | No additional index lookups needed |
| Requires additional index lookups | Better cache utilization |

**Performance test results** (100,000 events, 200 queries each):

```
Single Day Queries:
- Clustered: 0.000645s mean, 0.000000s median
- Conventional: 0.000951s mean, 0.000000s median
- 32.12% faster with clustered index

3-Day Range Queries:
- Clustered: 0.001014s mean, 0.000000s median
- Conventional: 0.001497s mean, 0.001510s median
- 32.27% faster with clustered index

7-Day Range Queries:
- Clustered: 0.002587s mean, 0.002003s median
- Conventional: 0.002959s mean, 0.002488s median
- 12.56% faster with clustered index
```

**Event model:**

```python
class Event(Base):
    __tablename__ = 'event'
    start_date = Column(Date, nullable=False)
    id = Column(Integer, nullable=True)  # Nullable to allow ID generation after object creation
    __table_args__ = (
        PrimaryKeyConstraint('start_date', 'id'),
    )
```

**ID generation and nullability:**

- The `id` column is nullable to support a two-step object creation process:
  1. Create event object (initially with null ID)
  2. Generate and assign ID based on the date
- This is safe because:
  - `start_date` is always present (NOT NULL)
  - `id` is only null during object creation
  - Final database state never has null values in the composite key
- SQLite treats NULL values as distinct in composite keys
- Clustering still works effectively because:
  - Primary clustering is by `start_date` (always present)
  - Secondary clustering by `id` within each date
  - Temporary nullability doesn't affect query performance

**Query optimization:**

- Queries use the clustered index naturally
- No need for additional index hints
- Efficient for both exact date and range queries

**Why this design is better:**

1. **Disk I/O Efficiency** — Related events are stored together; reduces disk seeks; better cache utilization
2. **Query Performance** — Faster for common calendar queries; more consistent response times; better scalability with large datasets
3. **Maintenance** — No need for additional indexes; simpler query plans; less index maintenance overhead
4. **Real-world Benefits** — Faster calendar loading; better user experience; more efficient resource usage

### Caching

The application implements a multi-level caching system:

- **Day-Based Caching**: Complete day events (both non-recurring and expanded recurring events) are cached for 1 hour. Key format: `"2025-01-15"` → complete list of events for that day. Subsequent requests for the same date return cached results instantly, avoiding the computational overhead of database queries and recurrence rule expansion.

- **Calendar Range Caching**: Calendar widget requests (week/month views) cache the entire date range results. Key format: `"calendar_2025-01-01_2025-01-31"`. Particularly effective since users often navigate between adjacent weeks/months.

- **Cache Invalidation**: Cache is automatically cleared when events are created, modified, or deleted, ensuring data consistency.

- **Memory Efficiency**: Uses TTL (Time To Live) of 1 hour with maximum size limits (1,000 day entries, 100 calendar entries) to prevent memory bloat.

**Real-world performance impact**: In typical usage patterns, 80-90% of all event requests are served from cache, making them nearly instantaneous. The 0.02 seconds metric represents the worst-case scenario for non-cached requests, while cached requests typically complete in under 0.001 seconds. Database queries and recurrence expansion are only performed for the first request to a date; subsequent requests reduce computational load by an order of magnitude.

Manage the cache via the `/cache-management` admin page.

### Recurring Event Performance

To ensure the application remains fast even with a large number of events and recurring series:

- **Clustered Indexing**: The database uses a composite primary key `(start_date, id)` so that events for the same date are stored together on disk. This makes range and day queries extremely efficient for non-recurring events.
- **Targeted Recurring Queries**: Instead of expanding all recurring events, the backend only considers those whose recurrence could affect the requested date range, filtering on `start_date`, `is_recurring`, and `recurring_until` with proper indexes.
- **On-the-fly Expansion**: Recurring events are expanded in memory only for the relevant date range, avoiding the need to store every instance in the database and keeping storage requirements low.
- **Efficient Algorithms**: The `dateutil.rrule` library is a robust, well-tested implementation of the iCalendar RRULE standard. Instead of writing custom code to interpret recurrence rules — error-prone for edge cases like leap years, daylight saving time, or complex BYDAY/BYMONTH rules — `dateutil.rrule` handles this efficiently. It is written in C and Python, optimized for performance, and used in many production systems.
- **Indexing**: An additional index on `(is_recurring, recurring_until)` ensures that queries for recurring events are fast, even as the number of events grows.

These strategies ensure that the calendar remains highly performant, even with thousands of events and complex recurrence patterns.

## Development Roadmap

For information about planned features and enhancements, see **[ROADMAP.md](ROADMAP.md)**. The roadmap covers upcoming features, implementation details, priorities, and development guidance — including enhanced venue management, custom event fields, advanced filtering, map view, event duplication, API improvements, and video conferencing integrations.

## HTML Templates

All templates extend `base.html` (Bootstrap 5, FullCalendar 6, navigation, flash messages).

```
base.html (foundation)
├── widget_test.html (main interface - home & day views)
├── month.html (monthly calendar view)
├── event_form.html (event creation/editing)
├── venue_form.html (venue creation/editing)
├── venues.html (venue management list)
└── cache_management.html (cache administration)
```

| Template | Purpose | Routes |
|----------|---------|--------|
| `base.html` | Layout, nav, shared assets | Extended by all templates |
| `widget_test.html` | Home page and day view with search + calendar | `/`, `/day/<date>`, `/widget-test` |
| `month.html` | Compact monthly calendar | `/month/<year>/<month>` |
| `event_form.html` | Create/edit events | `/event/new`, `/event/<id>/edit` |
| `venue_form.html` | Create/edit venues | `/venue/new`, `/venue/<id>/edit` |
| `venues.html` | Venue list | `/venues` |
| `cache_management.html` | Cache stats and admin | `/cache-management` |

### Performance Considerations

- **widget_test.html** is the most complex template, handling both home and day views
- **month.html** uses aggressive CSS optimization for compact display
- **cache_management.html** provides real-time monitoring of the caching system
- All templates use Bootstrap for consistent, responsive design
- JavaScript is loaded at the end of the page for optimal loading performance
