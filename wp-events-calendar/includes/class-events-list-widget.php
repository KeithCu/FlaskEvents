<?php
class Events_List_Widget extends WP_Widget {
    public function __construct() {
        parent::__construct(
            'events_list_widget',
            'Events List',
            array('description' => 'Displays events for the selected day')
        );
    }

    public function widget($args, $instance) {
        echo $args['before_widget'];
        if (!empty($instance['title'])) {
            echo $args['before_title'] . apply_filters('widget_title', $instance['title']) . $args['after_title'];
        }
        ?>
        <div class="events-list-widget">
            <div class="navigation-buttons">
                <button id="prev-day" class="btn btn-primary">Previous Day</button>
                <button id="next-day" class="btn btn-primary">Next Day</button>
            </div>
            <div id="events-list" class="event-list">
                <div class="loading">Loading events...</div>
            </div>
        </div>
        <?php
        echo $args['after_widget'];
    }

    public function form($instance) {
        $title = !empty($instance['title']) ? $instance['title'] : '';
        ?>
        <p>
            <label for="<?php echo esc_attr($this->get_field_id('title')); ?>">Title:</label>
            <input class="widefat" id="<?php echo esc_attr($this->get_field_id('title')); ?>" 
                   name="<?php echo esc_attr($this->get_field_id('title')); ?>" 
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