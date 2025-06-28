from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from wtforms import SelectMultipleField
from wtforms.validators import DataRequired
from database import Category, Event, Venue, SessionLocal
from cacheout import Cache

# Cache for most recently used categories (session-based)
mru_cache = Cache(maxsize=100, ttl=3600)  # 1 hour TTL

class CategoryModelView(ModelView):
    """Admin interface for managing categories"""
    
    column_list = ('name', 'usage_count', 'is_active')
    column_default_sort = ('usage_count', True)  # Sort by usage count descending
    column_searchable_list = ('name',)
    column_filters = ('is_active',)
    
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
    
    form_columns = ('title', 'description', 'start', 'end', 'venue', 'categories', 
                   'rrule', 'recurring_until', 'is_virtual', 'is_hybrid', 'url', 'color', 'bg')
    
    def on_model_change(self, form, model, is_created):
        """Update category usage counts when event is saved"""
        if model.categories:
            session = SessionLocal()
            try:
                for category in model.categories:
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
    
    form_columns = ('name', 'address')
    
    def on_model_change(self, form, model, is_created):
        """Handle venue changes"""
        pass
    
    def after_model_change(self, model, is_created):
        """Clear caches after venue changes"""
        from events import clear_day_events_cache, clear_calendar_events_cache
        clear_day_events_cache()
        clear_calendar_events_cache()

def init_admin(app):
    """Initialize Flask-Admin"""
    admin = Admin(app, name='Events Calendar Admin', template_mode='bootstrap4')
    
    # Add model views
    admin.add_view(CategoryModelView(Category, SessionLocal(), name='Categories'))
    admin.add_view(EventModelView(Event, SessionLocal(), name='Events'))
    admin.add_view(VenueModelView(Venue, SessionLocal(), name='Venues'))
    
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