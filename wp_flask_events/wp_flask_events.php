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
add_shortcode('flask_venues', 'flask_venues_shortcode');

function flask_events_shortcode() {
    flask_events_mark_assets_needed();
    return flask_events_calendar_markup();
}

function flask_events_list_shortcode() {
    flask_events_mark_assets_needed();
    return flask_events_list_markup();
}

function flask_venues_shortcode($atts) {
    flask_events_venues_assets_needed();

    $atts = shortcode_atts(array(
        'neighborhood' => '',
        'group_by' => 'venue_type',
    ), $atts, 'flask_venues');

    $neighborhood = trim($atts['neighborhood']);
    if ($neighborhood === '') {
        return '<p class="flask-venues-empty">Neighborhood is required. Example: [flask_venues neighborhood="Corktown"]</p>';
    }

    $group_by = trim($atts['group_by']);
    if ($group_by === '') {
        $group_by = 'venue_type';
    }

    return sprintf(
        '<div class="flask-events-wrap flask-venues-wrap" data-neighborhood="%s" data-group-by="%s"></div>',
        esc_attr($neighborhood),
        esc_attr($group_by)
    );
}

function flask_events_mark_assets_needed() {
    global $flask_events_assets_needed;
    $flask_events_assets_needed = true;
}

function flask_events_venues_assets_needed() {
    global $flask_events_venues_assets_needed;
    $flask_events_venues_assets_needed = true;
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

function flask_events_page_needs_venues_assets() {
    global $flask_events_venues_assets_needed, $post;

    if (!empty($flask_events_venues_assets_needed)) {
        return true;
    }

    if (!is_a($post, 'WP_Post')) {
        return false;
    }

    return has_shortcode($post->post_content, 'flask_venues');
}

add_action('wp_enqueue_scripts', 'flask_events_enqueue_assets', 999);

function flask_events_asset_version($relative_path) {
    $path = plugin_dir_path(__FILE__) . ltrim($relative_path, '/');
    return file_exists($path) ? (string) filemtime($path) : '1.0.2';
}

function flask_events_enqueue_assets() {
    $needs_events = flask_events_page_needs_assets();
    $needs_venues = flask_events_page_needs_venues_assets();

    if (!$needs_events && !$needs_venues) {
        return;
    }

    $css_version = flask_events_asset_version('css/flask-events.css');

    wp_enqueue_style(
        'flask-events-style',
        plugins_url('css/flask-events.css', __FILE__),
        array(),
        $css_version
    );

    if ($needs_events) {
        $js_version = flask_events_asset_version('js/flask-events.js');

        wp_enqueue_script(
            'fullcalendar',
            'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.17/index.global.min.js',
            array(),
            '6.1.17',
            true
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
            'eventLinkArrow' => '→',
            'fallbackEventUrl' => 'https://thedetroitilove.com',
        ));
    }

    if ($needs_venues) {
        $venues_js_version = flask_events_asset_version('js/flask-venues.js');

        wp_enqueue_script(
            'flask-venues-js',
            plugins_url('js/flask-venues.js', __FILE__),
            array(),
            $venues_js_version,
            true
        );

        wp_localize_script('flask-venues-js', 'flaskEvents', array(
            'flaskUrl' => FLASK_EVENTS_URL,
        ));
    }
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
