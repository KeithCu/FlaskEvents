from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import Select2Field
from wtforms import SelectMultipleField, TextAreaField, StringField, DateTimeField, BooleanField, SelectField
from wtforms.validators import DataRequired, Optional
from database import Category, Event, Venue, SessionLocal, engine
from cacheout import Cache
from sqlalchemy import text, func
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from flask import render_template, request, flash, redirect, url_for
import json

# Cache for most recently used categories (session-based)
mru_cache = Cache(maxsize=100, ttl=3600)  # 1 hour TTL

class DashboardView(BaseView):
    """Custom dashboard view with statistics"""
    
    @expose('/')
    def index(self):
        session = SessionLocal()
        try:
            # Get basic statistics
            total_events = session.query(Event).count()
            total_venues = session.query(Venue).count()
            total_categories = session.query(Category).count()
            
            # Get events by month (last 6 months)
            six_months_ago = datetime.now() - timedelta(days=180)
            monthly_events = session.query(
                func.strftime('%Y-%m', Event.start).label('month'),
                func.count(Event.id).label('count')
            ).filter(Event.start >= six_months_ago).group_by(
                func.strftime('%Y-%m', Event.start)
            ).order_by('month').all()
            
            # Get upcoming events (next 30 days) with venue loaded
            thirty_days_from_now = datetime.now() + timedelta(days=30)
            upcoming_events = session.query(Event).options(joinedload(Event.venue)).filter(
                Event.start >= datetime.now(),
                Event.start <= thirty_days_from_now
            ).order_by(Event.start).limit(10).all()
            
            # Get most popular venues
            popular_venues = session.query(
                Venue.name,
                func.count(Event.id).label('event_count')
            ).join(Event).group_by(Venue.id).order_by(
                func.count(Event.id).desc()
            ).limit(5).all()
            
            # Get most used categories
            popular_categories = session.query(
                Category.name,
                Category.usage_count
            ).filter(Category.is_active == True).order_by(
                Category.usage_count.desc()
            ).limit(10).all()
            
            # Get recent events (last 10) with venue loaded
            recent_events = session.query(Event).options(joinedload(Event.venue)).order_by(
                Event.start.desc()
            ).limit(10).all()
            
            return self.render('admin/dashboard.html',
                             total_events=total_events,
                             total_venues=total_venues,
                             total_categories=total_categories,
                             monthly_events=monthly_events,
                             upcoming_events=upcoming_events,
                             popular_venues=popular_venues,
                             popular_categories=popular_categories,
                             recent_events=recent_events)
        finally:
            session.close()

class DatabaseStatsView(BaseView):
    """Database statistics and maintenance view"""
    
    @expose('/')
    def index(self):
        session = SessionLocal()
        try:
            # Get database statistics
            with engine.connect() as conn:
                # Get table sizes
                table_sizes = conn.execute(text("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)).fetchall()
                
                # Get event distribution
                event_distribution = session.query(
                    func.strftime('%Y', Event.start).label('year'),
                    func.count(Event.id).label('count')
                ).group_by(func.strftime('%Y', Event.start)).all()
                
                # Get venue usage
                venue_usage = session.query(
                    Venue.name,
                    func.count(Event.id).label('event_count')
                ).outerjoin(Event).group_by(Venue.id).all()
                
                # Get category usage
                category_usage = session.query(
                    Category.name,
                    Category.usage_count,
                    Category.is_active
                ).order_by(Category.usage_count.desc()).all()
            
            return self.render('admin/database_stats.html',
                             table_sizes=table_sizes,
                             event_distribution=event_distribution,
                             venue_usage=venue_usage,
                             category_usage=category_usage)
        finally:
            session.close()

class CategoryModelView(ModelView):
    """Admin interface for managing categories"""
    
    column_list = ('name', 'usage_count', 'is_active')
    column_default_sort = ('usage_count', True)  # Sort by usage count descending
    column_searchable_list = ('name',)
    column_filters = ('is_active',)
    column_formatters = {
        'usage_count': lambda v, c, m, p: f"{m.usage_count:,}" if m.usage_count else "0"
    }
    
    form_columns = ('name', 'is_active')
    form_extra_fields = {
        'usage_count': SelectMultipleField('Usage Count', coerce=int)
    }
    
    def on_model_change(self, form, model, is_created):
        """Update usage count when category is modified"""
        if is_created:
            model.usage_count = 0
    
    def after_model_change(self, model, is_created):
        """Clear caches after category changes"""
        from events import clear_day_events_cache, clear_calendar_events_cache
        clear_day_events_cache()
        clear_calendar_events_cache()

class EventModelView(ModelView):
    """Admin interface for managing events"""
    
    column_list = ('title', 'start', 'end', 'venue', 'categories', 'is_recurring', 'is_virtual')
    column_searchable_list = ('title', 'description')
    column_filters = ('is_recurring', 'is_virtual', 'is_hybrid', 'start_date')
    column_formatters = {
        'start': lambda v, c, m, p: m.start.strftime('%Y-%m-%d %H:%M') if m.start else '',
        'end': lambda v, c, m, p: m.end.strftime('%Y-%m-%d %H:%M') if m.end else '',
        'categories': lambda v, c, m, p: m.categories[:50] + '...' if m.categories and len(m.categories) > 50 else m.categories or ''
    }
    
    form_columns = ('title', 'description', 'start', 'end', 'venue', 'categories', 
                   'rrule', 'recurring_until', 'is_virtual', 'is_hybrid', 'url', 'color', 'bg')
    
    form_extra_fields = {
        'description': TextAreaField('Description'),
        'categories': StringField('Categories (comma-separated)'),
        'url': StringField('URL'),
        'color': StringField('Color (hex)'),
        'bg': StringField('Background Color (hex)')
    }
    
    def on_model_change(self, form, model, is_created):
        """Update category usage counts when event is saved"""
        if model.categories:
            session = SessionLocal()
            try:
                # Parse categories and update usage counts
                category_names = [cat.strip() for cat in model.categories.split(',') if cat.strip()]
                for category_name in category_names:
                    category = session.query(Category).filter(Category.name == category_name).first()
                    if category:
                        category.usage_count += 1
                session.commit()
            finally:
                session.close()
    
    def after_model_change(self, model, is_created):
        """Clear caches after event changes"""
        from events import clear_day_events_cache, clear_calendar_events_cache
        clear_day_events_cache()
        clear_calendar_events_cache()

class VenueModelView(ModelView):
    """Admin interface for managing venues"""
    
    column_list = ('name', 'address', 'event_count')
    column_searchable_list = ('name', 'address')
    column_formatters = {
        'event_count': lambda v, c, m, p: len(m.events) if m.events else 0
    }
    
    form_columns = ('name', 'address')
    form_extra_fields = {
        'address': TextAreaField('Address')
    }
    
    def on_model_change(self, form, model, is_created):
        """Handle venue changes"""
        pass
    
    def after_model_change(self, model, is_created):
        """Clear caches after venue changes"""
        from events import clear_day_events_cache, clear_calendar_events_cache
        clear_day_events_cache()
        clear_calendar_events_cache()

class BulkOperationsView(BaseView):
    """Bulk operations for events"""
    
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if request.method == 'POST':
            operation = request.form.get('operation')
            event_ids = request.form.getlist('event_ids')
            
            if not event_ids:
                flash('No events selected', 'error')
                return redirect(url_for('bulkoperations.index'))
            
            session = SessionLocal()
            try:
                events = session.query(Event).filter(Event.id.in_(event_ids)).all()
                
                if operation == 'delete':
                    for event in events:
                        session.delete(event)
                    session.commit()
                    flash(f'Deleted {len(events)} events', 'success')
                
                elif operation == 'update_category':
                    category = request.form.get('category')
                    if category:
                        for event in events:
                            if event.categories:
                                categories = [cat.strip() for cat in event.categories.split(',')]
                                if category not in categories:
                                    categories.append(category)
                                    event.categories = ', '.join(categories)
                            else:
                                event.categories = category
                        session.commit()
                        flash(f'Updated categories for {len(events)} events', 'success')
                
                elif operation == 'mark_virtual':
                    for event in events:
                        event.is_virtual = True
                    session.commit()
                    flash(f'Marked {len(events)} events as virtual', 'success')
                
            except Exception as e:
                session.rollback()
                flash(f'Error: {str(e)}', 'error')
            finally:
                session.close()
            
            return redirect(url_for('bulkoperations.index'))
        
        # Get events for selection with venue relationship loaded
        session = SessionLocal()
        try:
            events = session.query(Event).options(joinedload(Event.venue)).order_by(Event.start.desc()).limit(100).all()
            categories = session.query(Category).filter(Category.is_active == True).all()
        finally:
            session.close()
        
        return self.render('admin/bulk_operations.html', events=events, categories=categories)

class EventManagementView(BaseView):
    """Custom event management view with advanced features"""
    
    @expose('/')
    def index(self):
        session = SessionLocal()
        try:
            # Get events with manual pagination and venue relationship loaded
            page = request.args.get('page', 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page
            
            # Get total count
            total_events = session.query(Event).count()
            
            # Get paginated events
            events = session.query(Event).options(joinedload(Event.venue)).order_by(Event.start.desc()).offset(offset).limit(per_page).all()
            
            # Calculate pagination info
            total_pages = (total_events + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            # Create a simple pagination object
            class Pagination:
                def __init__(self, items, page, per_page, total, total_pages, has_prev, has_next):
                    self.items = items
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = total_pages
                    self.has_prev = has_prev
                    self.has_next = has_next
                    self.prev_num = page - 1 if has_prev else None
                    self.next_num = page + 1 if has_next else None
                
                def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
                    last = 0
                    for num in range(1, self.pages + 1):
                        if (num <= left_edge or 
                            (num > self.page - left_current - 1 and 
                             num < self.page + right_current) or 
                            num > self.pages - right_edge):
                            if last + 1 != num:
                                yield None
                            yield num
                            last = num
            
            pagination = Pagination(events, page, per_page, total_events, total_pages, has_prev, has_next)
            
            # Get quick stats
            upcoming_events = session.query(Event).filter(Event.start >= datetime.now()).count()
            virtual_events = session.query(Event).filter(Event.is_virtual == True).count()
            recurring_events = session.query(Event).filter(Event.is_recurring == True).count()
            
            return self.render('admin/event_management.html',
                             events=pagination,
                             total_events=total_events,
                             upcoming_events=upcoming_events,
                             virtual_events=virtual_events,
                             recurring_events=recurring_events)
        finally:
            session.close()
    
    @expose('/duplicate/<int:event_id>')
    def duplicate_event(self, event_id):
        session = SessionLocal()
        try:
            original_event = session.query(Event).filter(Event.id == event_id).first()
            if not original_event:
                flash('Event not found', 'error')
                return redirect(url_for('eventmanagement.index'))
            
            # Create a copy of the event
            new_event = Event(
                title=f"{original_event.title} (Copy)",
                description=original_event.description,
                start=original_event.start + timedelta(days=7),  # Move to next week
                end=original_event.end + timedelta(days=7),
                venue_id=original_event.venue_id,
                categories=original_event.categories,
                color=original_event.color,
                bg=original_event.bg,
                is_virtual=original_event.is_virtual,
                is_hybrid=original_event.is_hybrid,
                url=original_event.url,
                rrule=original_event.rrule,
                recurring_until=original_event.recurring_until,
                is_recurring=original_event.is_recurring
            )
            
            session.add(new_event)
            session.commit()
            
            flash(f'Event "{original_event.title}" duplicated successfully', 'success')
            return redirect(url_for('eventmanagement.index'))
        except Exception as e:
            session.rollback()
            flash(f'Error duplicating event: {str(e)}', 'error')
            return redirect(url_for('eventmanagement.index'))
        finally:
            session.close()

def init_admin(app):
    """Initialize Flask-Admin with enhanced views"""
    admin = Admin(app, name='Events Calendar Admin', template_mode='bootstrap4')
    
    # Configure compact settings for all model views
    class CompactModelView(ModelView):
        """Base model view with compact settings"""
        page_size = 50  # More items per page
        can_view_details = False  # Remove view details button
        column_display_pk = False  # Hide primary key column
        column_display_all_relations = False  # Don't display all relations
        column_hide_backrefs = True  # Hide backrefs
        column_list_display_pk = False  # Hide PK in list
        column_default_sort = ('id', True)  # Default sort by ID descending
        can_export = True  # Enable export
        export_types = ['csv', 'xlsx']  # Export formats
        column_searchable_list = []  # Will be overridden in subclasses
        column_filters = []  # Will be overridden in subclasses
        
        # Additional compact settings
        can_create = True
        can_edit = True
        can_delete = True
    
    # Add custom views
    admin.add_view(DashboardView(name='Dashboard', endpoint='dashboard'))
    admin.add_view(DatabaseStatsView(name='Database Stats', endpoint='dbstats'))
    admin.add_view(BulkOperationsView(name='Bulk Operations', endpoint='bulkoperations'))
    admin.add_view(EventManagementView(name='Event Management', endpoint='eventmanagement'))
    
    # Add model views with compact settings
    class CompactCategoryModelView(CompactModelView, CategoryModelView):
        page_size = 100
        column_searchable_list = ('name',)
        column_filters = ('is_active',)
    
    class CompactEventModelView(CompactModelView, EventModelView):
        page_size = 50
        column_searchable_list = ('title', 'description')
        column_filters = ('is_recurring', 'is_virtual', 'is_hybrid', 'start_date')
    
    class CompactVenueModelView(CompactModelView, VenueModelView):
        page_size = 100
        column_searchable_list = ('name', 'address')
    
    admin.add_view(CompactCategoryModelView(Category, SessionLocal(), name='Categories', endpoint='categories'))
    admin.add_view(CompactEventModelView(Event, SessionLocal(), name='Events', endpoint='events'))
    admin.add_view(CompactVenueModelView(Venue, SessionLocal(), name='Venues', endpoint='venues'))
    
    return admin

def get_categories_by_usage():
    """Get categories ordered by usage count (most used first)"""
    session = SessionLocal()
    try:
        categories = session.query(Category).filter(
            Category.is_active == True
        ).order_by(Category.usage_count.desc(), Category.name).all()
        return categories
    finally:
        session.close()

def update_category_usage(category_ids):
    """Update usage count for categories"""
    if not category_ids:
        return
    
    session = SessionLocal()
    try:
        categories = session.query(Category).filter(Category.id.in_(category_ids)).all()
        for category in categories:
            category.usage_count += 1
        session.commit()
    finally:
        session.close()

def get_mru_categories(session_id, limit=5):
    """Get most recently used categories for a session"""
    return mru_cache.get(session_id, [])

def set_mru_categories(session_id, category_ids, limit=5):
    """Set most recently used categories for a session"""
    if category_ids:
        mru_cache.set(session_id, category_ids[:limit]) 