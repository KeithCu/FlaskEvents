<?php
class Flask_Events_List_Widget extends WP_Widget {
    public function __construct() {
        parent::__construct(
            'flask_events_list_widget',
            'Flask Events List',
            array('description' => 'Daily event list from Flask Events')
        );
    }

    public function widget($args, $instance) {
        echo $args['before_widget'];
        if (!empty($instance['title'])) {
            echo $args['before_title'] . apply_filters('widget_title', $instance['title']) . $args['after_title'];
        }
        echo flask_events_list_markup();
        echo $args['after_widget'];
    }

    public function form($instance) {
        $title = !empty($instance['title']) ? $instance['title'] : '';
        ?>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('title')); ?>">Title:</label>
            <input class="widefat" id="<?php echo esc_attr($this->get_field_id('title')); ?>"
                   name="<?php echo esc_attr($this->get_field_name('title')); ?>"
                   type="text" value="<?php echo esc_attr($title); ?>">
        </p>
        <?php
    }

    public function update($new_instance, $old_instance) {
        $instance = array();
        $instance['title'] = (!empty($new_instance['title'])) ? strip_tags($new_instance['title']) : '';
        return $instance;
    }
}

function flask_events_list_markup() {
    ob_start();
    ?>
    <div class="flask-events-wrap">
        <div class="events-list-widget">
            <div class="search-box">
                <input type="text" id="search-input" placeholder="Search events...">
            </div>
            <div class="navigation-buttons">
                <div id="prev-day">&laquo; Previous Day</div>
                <div id="next-day">Next Day &raquo;</div>
            </div>
            <div id="selected-date-display"></div>
            <div id="events-list" class="event-list"></div>
            <div class="navigation-buttons">
                <div id="prev-day-bottom">&laquo; Previous Day</div>
                <div id="next-day-bottom">Next Day &raquo;</div>
            </div>
        </div>
    </div>
    <?php
    return ob_get_clean();
}
