<?php
/**
 * Plugin Name: Events Calendar
 * Description: A simple events calendar with day view
 * Version: 1.0.0
 * Author: Your Name
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Register activation hook
register_activation_hook(__FILE__, 'events_calendar_activate');

function events_calendar_activate() {
    global $wpdb;
    
    $charset_collate = $wpdb->get_charset_collate();
    
    // Create venues table
    $sql_venues = "CREATE TABLE IF NOT EXISTS {$wpdb->prefix}event_venues (
        id bigint(20) NOT NULL AUTO_INCREMENT,
        name varchar(255) NOT NULL,
        address text,
        created_at datetime DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id)
    ) $charset_collate;";
    
    // Create events table
    $sql_events = "CREATE TABLE IF NOT EXISTS {$wpdb->prefix}events (
        id bigint(20) NOT NULL AUTO_INCREMENT,
        title varchar(255) NOT NULL,
        description text,
        start datetime NOT NULL,
        end datetime NOT NULL,
        venue_id bigint(20),
        color varchar(7) DEFAULT '#3788d8',
        bg varchar(7) DEFAULT '#3788d8',
        rrule text,
        created_at datetime DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        FOREIGN KEY (venue_id) REFERENCES {$wpdb->prefix}event_venues(id)
    ) $charset_collate;";
    
    require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
    dbDelta($sql_venues);
    dbDelta($sql_events);
}

// Register REST API endpoints
add_action('rest_api_init', 'register_events_endpoints');

function register_events_endpoints() {
    register_rest_route('events/v1', '/day-events', array(
        'methods' => 'GET',
        'callback' => 'get_day_events',
        'permission_callback' => '__return_true'
    ));
}

function get_day_events($request) {
    global $wpdb;
    
    $date = $request->get_param('date');
    if (!$date) {
        $date = date('Y-m-d');
    }
    
    $start = $date . ' 00:00:00';
    $end = $date . ' 23:59:59';
    
    $events = $wpdb->get_results($wpdb->prepare(
        "SELECT e.*, v.name as venue_name 
         FROM {$wpdb->prefix}events e 
         LEFT JOIN {$wpdb->prefix}event_venues v ON e.venue_id = v.id 
         WHERE e.start BETWEEN %s AND %s 
         ORDER BY e.start ASC",
        $start, $end
    ));
    
    return rest_ensure_response($events);
}

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
            'events-calendar-style',
            plugins_url('css/events-calendar.css', __FILE__),
            array(),
            '1.0.0'
        );
        
        wp_enqueue_script(
            'events-calendar-js',
            plugins_url('js/events-calendar.js', __FILE__),
            array('fullcalendar'),
            '1.0.0',
            true
        );
        
        // Localize script with REST API URL
        wp_localize_script('events-calendar-js', 'eventsCalendar', array(
            'restUrl' => rest_url('events/v1/'),
            'nonce' => wp_create_nonce('wp_rest')
        ));
    }
} 