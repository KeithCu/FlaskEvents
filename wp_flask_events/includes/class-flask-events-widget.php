<?php
class Flask_Events_Widget extends WP_Widget {
    public function __construct() {
        parent::__construct(
            'flask_events_widget',
            'Flask Events',
            array('description' => 'Monthly calendar for Flask Events navigation')
        );
    }

    public function widget($args, $instance) {
        echo $args['before_widget'];
        if (!empty($instance['title'])) {
            echo $args['before_title'] . apply_filters('widget_title', $instance['title']) . $args['after_title'];
        }
        echo flask_events_calendar_markup();
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

function flask_events_calendar_markup() {
    ob_start();
    ?>
    <div class="flask-events-wrap">
        <div id="events-calendar" class="events-calendar-widget"></div>
    </div>
    <?php
    return ob_get_clean();
}
