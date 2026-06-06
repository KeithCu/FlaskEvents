<?php
/**
 * Plugin Name: Events Calendar
 * Description: A simple events calendar with day view
 * Version: 0.1.0
 * Author: KeithCu
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Configuration - Update this URL to point to your Flask app
define('FLASK_EVENTS_URL', 'http://localhost:5000');

require_once plugin_dir_path(__FILE__) . 'includes/class-flask-events-calendar-widget.php';
require_once plugin_dir_path(__FILE__) . 'includes/class-flask-events-list-widget.php';

// Register widgets
add_action('widgets_init', 'register_events_widgets');

function register_events_widgets() {
    register_widget('Events_Calendar_Widget');
    register_widget('Events_List_Widget');
}

// Enqueue scripts and styles
add_action('wp_enqueue_scripts', 'events_calendar_scripts');

function events_calendar_scripts() {
    // Only load if widgets are active
    if (is_active_widget(false, false, 'events_calendar_widget') || 
        is_active_widget(false, false, 'events_list_widget')) {
        
        wp_enqueue_script(
            'fullcalendar',
            'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.17/index.global.min.js',
            array(),
            '6.1.17',
            true
        );
        
        wp_enqueue_style(
            'flask-events-style',
            plugins_url('css/flask-events.css', __FILE__),
            array(),
            '1.0.0'
        );
        
        wp_enqueue_script(
            'flask-events-js',
            plugins_url('js/flask-events.js', __FILE__),
            array('fullcalendar'),
            '1.0.0',
            true
        );
        
        // Localize script with Flask app URL instead of WordPress REST API
        wp_localize_script('flask-events-js', 'eventsCalendar', array(
            'flaskUrl' => FLASK_EVENTS_URL,
            'eventsEndpoint' => '/events',
            'searchEndpoint' => '/search'
        ));
    }
} 