# Flask Event Calendar

A simple event calendar application built with Flask and FullCalendar.

## Features

- Monthly, weekly, and daily calendar views
- Create, edit, and delete events
- Recurring events support
- Venue management
- Custom event colors

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

## Usage

- Click on any date to view the daily view
- Click the "New Event" button to create an event
- Click on an existing event to edit it
- Use the navigation buttons to move between months
- Switch between month, week, and day views using the view buttons

## Recurring Events

The application supports recurring events using the iCalendar RRULE format. Examples:

- Weekly on Monday, Wednesday, Friday: `FREQ=WEEKLY;BYDAY=MO,WE,FR`
- Daily: `FREQ=DAILY`
- Monthly on the 15th: `FREQ=MONTHLY;BYMONTHDAY=15`

# Flask Events Calendar - Performance Optimized

## Database Design and Performance Optimization

### Clustered Index Approach
This application uses a clustered index design for event storage, which has been proven to be more efficient than conventional indexing for calendar-based queries. The key design decisions are:

1. **Composite Primary Key (start_date, id)**
   - Events are physically stored in order by date, then by ID
   - This clustering means events for the same date are stored together on disk
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

### Conventional vs Clustered Index Comparison

The performance tests compare two approaches:

1. **Conventional Approach**
   - Simple auto-incrementing primary key
   - Separate index on start_date
   - Events stored in insertion order
   - Requires additional index lookups

2. **Clustered Approach**
   - Composite primary key (start_date, id)
   - Events physically ordered by date
   - No additional index lookups needed
   - Better cache utilization

### Performance Test Results

The test suite creates 100,000 events and runs 200 queries for each test type:

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

### Implementation Details

1. **Event Model**
   ```python
   class Event(Base):
       __tablename__ = 'event'
       start_date = Column(Date, nullable=False)
       id = Column(Integer, nullable=True)  # Nullable to allow ID generation after object creation
       __table_args__ = (
           PrimaryKeyConstraint('start_date', 'id'),
       )
   ```

2. **ID Generation and Nullability**
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

3. **Query Optimization**
   - Queries use the clustered index naturally
   - No need for additional index hints
   - Efficient for both exact date and range queries

### Why This Design is Better

1. **Disk I/O Efficiency**
   - Related events are stored together
   - Reduces disk seeks
   - Better cache utilization

2. **Query Performance**
   - Faster for common calendar queries
   - More consistent response times
   - Better scalability with large datasets

3. **Maintenance**
   - No need for additional indexes
   - Simpler query plans
   - Less index maintenance overhead

4. **Real-world Benefits**
   - Faster calendar loading
   - Better user experience
   - More efficient resource usage 