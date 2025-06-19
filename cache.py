from flask import render_template, request, jsonify

def register_cache_routes(app):
    """Register cache management routes with the Flask app"""
    
    @app.route('/cache-management')
    def cache_management():
        """Cache management and testing page"""
        return render_template('cache_management.html')

    @app.route('/api/cache/stats')
    def cache_stats():
        """Get cache statistics"""
        try:
            from events import day_events_cache, calendar_events_cache
            
            day_stats = {
                'maxsize': day_events_cache.maxsize,
                'ttl': day_events_cache.ttl,
                'size': len(day_events_cache),
                'keys': list(day_events_cache.keys())[:20]  # Show first 20 keys
            }
            
            calendar_stats = {
                'maxsize': calendar_events_cache.maxsize,
                'ttl': calendar_events_cache.ttl,
                'size': len(calendar_events_cache),
                'keys': list(calendar_events_cache.keys())[:20]  # Show first 20 keys
            }
            
            return jsonify({
                'day_events_cache': day_stats,
                'calendar_events_cache': calendar_stats,
                'total_cached_items': len(day_events_cache) + len(calendar_events_cache)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cache/test', methods=['POST'])
    def test_cache():
        """Test cache functionality"""
        try:
            from events import day_events_cache, calendar_events_cache
            
            data = request.get_json()
            test_key = data.get('key', 'test_key')
            test_value = data.get('value', ['test_value'])
            
            # Test setting and getting from day events cache
            day_events_cache.set(test_key, test_value)
            retrieved_value = day_events_cache.get(test_key)
            
            return jsonify({
                'success': True,
                'test_key': test_key,
                'test_value': test_value,
                'retrieved_value': retrieved_value,
                'cache_hit': retrieved_value is not None
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cache/clear', methods=['POST'])
    def clear_cache():
        """Clear all caches"""
        try:
            from events import day_events_cache, calendar_events_cache
            
            # Clear both caches directly
            day_events_cache.clear()
            calendar_events_cache.clear()
            
            return jsonify({
                'success': True,
                'message': 'All caches cleared successfully'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cache/get/<key>')
    def get_cache_value(key):
        """Get a specific cache value"""
        try:
            from events import day_events_cache, calendar_events_cache
            
            # Try both caches
            day_value = day_events_cache.get(key)
            calendar_value = calendar_events_cache.get(key)
            
            return jsonify({
                'key': key,
                'day_events_cache': day_value,
                'calendar_events_cache': calendar_value,
                'found_in_day': day_value is not None,
                'found_in_calendar': calendar_value is not None
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cache/set', methods=['POST'])
    def set_cache_value():
        """Set a cache value"""
        try:
            from events import day_events_cache, calendar_events_cache
            
            data = request.get_json()
            key = data.get('key')
            value = data.get('value')
            cache_type = data.get('cache_type', 'day')  # 'day' or 'calendar'
            
            if not key or value is None:
                return jsonify({'error': 'Key and value are required'}), 400
            
            if cache_type == 'day':
                day_events_cache.set(key, value)
            elif cache_type == 'calendar':
                calendar_events_cache.set(key, value)
            else:
                return jsonify({'error': 'Invalid cache type'}), 400
            
            return jsonify({
                'success': True,
                'message': f'Value set in {cache_type} cache',
                'key': key,
                'value': value
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500 