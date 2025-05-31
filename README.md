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