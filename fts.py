from sqlalchemy import text
import time
from database import engine, Event

def search_events(query, session):
    """Search for events using FTS"""
    try:
        # Use FTS for full-text search through the session
        fts_results = session.execute(text("""
            SELECT id FROM event_fts 
            WHERE event_fts MATCH :query 
            ORDER BY rank
            LIMIT 50
        """), {"query": query}).fetchall()
        
        if not fts_results:
            return []
        
        # Get the actual event objects
        event_ids = [row[0] for row in fts_results]
        events = session.query(Event).filter(Event.id.in_(event_ids)).all()
        
        return events
    except Exception as e:
        print(f"Error in search_events: {e}")
        # Fallback to simple LIKE search
        return session.query(Event).filter(
            Event.title.ilike(f'%{query}%') | 
            Event.description.ilike(f'%{query}%')
        ).limit(50).all()


def setup_fts_triggers():
    """Set up triggers to keep FTS table in sync with main table"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            with engine.begin() as conn:  # Use begin() for transaction
                # First, check if we can access the event table
                event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
                print(f"Found {event_count} events in main table")
                
                # Drop existing FTS table and triggers if they exist
                conn.execute(text('DROP TABLE IF EXISTS event_fts'))
                conn.execute(text('DROP TRIGGER IF EXISTS event_ai'))
                conn.execute(text('DROP TRIGGER IF EXISTS event_au'))
                conn.execute(text('DROP TRIGGER IF EXISTS event_ad'))
                
                # Create FTS5 table with proper structure
                conn.execute(text('''
                    CREATE VIRTUAL TABLE event_fts USING fts5(
                        id UNINDEXED,
                        title,
                        description
                    )
                '''))
                
                # Create triggers for insert
                conn.execute(text('''
                    CREATE TRIGGER event_ai AFTER INSERT ON event BEGIN
                        INSERT INTO event_fts(id, title, description)
                        VALUES (new.id, new.title, new.description);
                    END
                '''))
                
                # Create triggers for update
                conn.execute(text('''
                    CREATE TRIGGER event_au AFTER UPDATE ON event BEGIN
                        UPDATE event_fts SET
                            title = new.title,
                            description = new.description
                        WHERE id = old.id;
                    END
                '''))
                
                # Create triggers for delete
                conn.execute(text('''
                    CREATE TRIGGER event_ad AFTER DELETE ON event BEGIN
                        DELETE FROM event_fts WHERE id = old.id;
                    END
                '''))
                
                # Populate FTS table with existing data in batches
                batch_size = 1000
                offset = 0
                while True:
                    # Get a batch of events
                    events = conn.execute(text("""
                        SELECT id, title, description 
                        FROM event 
                        LIMIT :limit OFFSET :offset
                    """), {"limit": batch_size, "offset": offset}).fetchall()
                    
                    if not events:
                        break
                    
                    # Insert batch into FTS
                    for event in events:
                        conn.execute(text("""
                            INSERT INTO event_fts(id, title, description)
                            VALUES (:id, :title, :description)
                        """), {
                            "id": event[0],
                            "title": event[1] or "",
                            "description": event[2] or ""
                        })
                    
                    offset += batch_size
                    print(f"Processed {offset} events for FTS")
                
                # Verify setup
                verify_fts_setup()
                
                # Optimize FTS table
                conn.execute(text('INSERT INTO event_fts(event_fts) VALUES("optimize")'))
                
                print("FTS setup completed successfully")
                return  # Success, exit the retry loop
                
        except Exception as e:
            print(f"Error setting up FTS (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("FTS setup failed after all retries. Continuing without FTS...")
                return


def ensure_fts_setup():
    """Ensure FTS is set up, initialize if needed"""
    try:
        with engine.connect() as conn:
            # Check if FTS table exists and has data
            fts_count = conn.execute(text("SELECT COUNT(*) FROM event_fts")).scalar()
            event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            
            if fts_count == 0 and event_count > 0:
                print("FTS table is empty but events exist, setting up FTS...")
                setup_fts_triggers()
                print("FTS setup completed")
            elif fts_count != event_count:
                print(f"FTS count ({fts_count}) doesn't match event count ({event_count}), reinitializing FTS...")
                setup_fts_triggers()
                print("FTS reinitialization completed")
    except Exception as e:
        print(f"Error checking FTS setup: {e}")
        # If FTS table doesn't exist, set it up
        try:
            print("Setting up FTS table...")
            setup_fts_triggers()
            print("FTS setup completed")
        except Exception as setup_error:
            print(f"FTS setup failed: {setup_error}")


def verify_fts_setup():
    """Verify that FTS table and triggers are properly set up"""
    try:
        with engine.connect() as conn:
            # Check if FTS table exists
            fts_exists = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='event_fts'
            """)).scalar()
            print(f"FTS table exists: {fts_exists is not None}")
            
            if not fts_exists:
                print("FTS table does not exist")
                return
            
            # Check trigger count
            trigger_count = conn.execute(text("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='trigger' AND name LIKE 'event_a%'
            """)).scalar()
            print(f"Number of triggers: {trigger_count}")
            
            # Check FTS table content
            fts_count = conn.execute(text("SELECT COUNT(*) FROM event_fts")).scalar()
            event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            print(f"FTS table rows: {fts_count}")
            print(f"Event table rows: {event_count}")
            
            if fts_count != event_count:
                print("WARNING: FTS table count doesn't match event table count!")
            
            # Check sample content
            sample = conn.execute(text("""
                SELECT e.id, e.title, f.title as fts_title 
                FROM event e 
                LEFT JOIN event_fts f ON e.id = f.id 
                LIMIT 1
            """)).fetchone()
            if sample:
                print(f"Sample content - Event ID: {sample[0]}")
                print(f"Event title: {sample[1]}")
                print(f"FTS title: {sample[2]}")
            
            # Test FTS search with proper syntax
            test_query = "test"
            test_results = conn.execute(text("""
                SELECT * FROM event_fts 
                WHERE event_fts MATCH :query 
                LIMIT 1
            """), {"query": test_query}).fetchall()
            print(f"Test search returned {len(test_results)} results")
            
    except Exception as e:
        print(f"Error verifying FTS setup: {e}")
        print("FTS verification failed, but continuing...")
