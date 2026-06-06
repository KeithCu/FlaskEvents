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

add_action('wp_enqueue_scripts', 'flask_events_enqueue_assets', 999);

function flask_events_asset_version($relative_path) {
    $path = plugin_dir_path(__FILE__) . ltrim($relative_path, '/');
    return file_exists($path) ? (string) filemtime($path) : '1.0.2';
}

function flask_events_enqueue_assets() {
    if (!flask_events_page_needs_assets()) {
        return;
    }

    $css_version = flask_events_asset_version('css/flask-events.css');
    $js_version = flask_events_asset_version('js/flask-events.js');

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
        $css_version
    );

    wp_enqueue_script(
        'flask-events-js',
        plugins_url('js/flask-events.js', __FILE__),
        array('fullcalendar'),
        $js_version,
        true
    );

    wp_localize_script('flask-events-js', 'flaskEvents', array(
        'flaskUrl' => FLASK_EVENTS_URL,
        'eventsEndpoint' => '/events',
        'searchEndpoint' => '/search',
        'eventLinkArrow' => '⇒',
        'fallbackEventUrl' => 'https://thedetroitilove.com',
    ));
}

// Keep Flask Events assets out of W3 Total Cache minify so updates apply immediately.
add_filter('w3tc_minify_css_do_tag', 'flask_events_skip_w3tc_minify_css', 10, 3);
add_filter('w3tc_minify_js_do_tag', 'flask_events_skip_w3tc_minify_js', 10, 3);

function flask_events_skip_w3tc_minify_css($do_tag, $style_tag, $style) {
    if (!empty($style['src']) && strpos($style['src'], 'wp_flask_events') !== false) {
        return false;
    }
    return $do_tag;
}

function flask_events_skip_w3tc_minify_js($do_tag, $script_tag, $script) {
    if (!empty($script['src']) && strpos($script['src'], 'wp_flask_events') !== false) {
        return false;
    }
    return $do_tag;
}
