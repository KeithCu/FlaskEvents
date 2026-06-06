<?php
/**
 * Plugin Name: Flask Events
 * Description: Embed Flask Events calendar and daily list widgets on your WordPress site
 * Version: 0.1.0
 * Author: KeithCu
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Configuration - Update this URL to point to your Flask app
define('FLASK_EVENTS_URL', 'http://localhost:5000');

require_once plugin_dir_path(__FILE__) . 'includes/class-flask-events-widget.php';
require_once plugin_dir_path(__FILE__) . 'includes/class-flask-events-list-widget.php';

add_action('widgets_init', 'register_flask_events_widgets');

function register_flask_events_widgets() {
    register_widget('Flask_Events_Widget');
    register_widget('Flask_Events_List_Widget');
}

add_shortcode('flask_events', 'flask_events_shortcode');
add_shortcode('flask_events_list', 'flask_events_list_shortcode');

function flask_events_shortcode() {
    flask_events_mark_assets_needed();
    return flask_events_calendar_markup();
}

function flask_events_list_shortcode() {
    flask_events_mark_assets_needed();
    return flask_events_list_markup();
}

function flask_events_mark_assets_needed() {
    global $flask_events_assets_needed;
    $flask_events_assets_needed = true;
}

function flask_events_page_needs_assets() {
    global $flask_events_assets_needed, $post;

    if (!empty($flask_events_assets_needed)) {
        return true;
    }

    if (is_active_widget(false, false, 'flask_events_widget') ||
        is_active_widget(false, false, 'flask_events_list_widget')) {
        return true;
    }

    if (!is_a($post, 'WP_Post')) {
        return false;
    }

    return has_shortcode($post->post_content, 'flask_events') ||
           has_shortcode($post->post_content, 'flask_events_list');
}

add_action('wp_enqueue_scripts', 'flask_events_enqueue_assets');

function flask_events_enqueue_assets() {
    if (!flask_events_page_needs_assets()) {
        return;
    }

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

    wp_localize_script('flask-events-js', 'flaskEvents', array(
        'flaskUrl' => FLASK_EVENTS_URL,
        'eventsEndpoint' => '/events',
        'searchEndpoint' => '/search'
    ));
}
