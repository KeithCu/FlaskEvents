def register_venues(app):
    from flask import render_template, request, jsonify, redirect, url_for, flash
    from database import SessionLocal, Event, Venue

    @app.route('/venues')
    def list_venues():
        session = SessionLocal()
        try:
            venues = session.query(Venue).order_by(Venue.name).all()
            return render_template('venues.html', venues=venues)
        finally:
            session.close()

    @app.route('/venue/new', methods=['GET', 'POST'])
    def add_venue():
        if request.method == 'POST':
            name = request.form['name']
            address = request.form['address']
            if not name:
                flash('Venue name is required', 'error')
                return render_template('venue_form.html', name=name, address=address)
            session = SessionLocal()
            try:
                venue = Venue(name=name, address=address)
                session.add(venue)
                session.commit()
                flash('Venue added successfully', 'success')
                return redirect(url_for('list_venues'))
            finally:
                session.close()
        return render_template('venue_form.html')

    @app.route('/venue/<int:id>/edit', methods=['GET', 'POST'])
    def edit_venue(id):
        session = SessionLocal()
        venue = session.query(Venue).get_or_404(id)
        if request.method == 'POST':
            name = request.form['name']
            address = request.form['address']
            if not name:
                flash('Venue name is required', 'error')
                session.close()
                return render_template('venue_form.html', venue=venue, name=name, address=address)
            venue.name = name
            venue.address = address
            session.commit()
            flash('Venue updated successfully', 'success')
            session.close()
            return redirect(url_for('list_venues'))
        session.close()
        return render_template('venue_form.html', venue=venue)

    @app.route('/venue/<int:id>/delete', methods=['POST'])
    def delete_venue(id):
        session = SessionLocal()
        venue = session.query(Venue).get_or_404(id)
        event_count = session.query(Event).filter(Event.venue_id == id).count()
        if event_count > 0:
            flash(f'Cannot delete venue "{venue.name}" because it has {event_count} associated event(s). Please reassign or delete those events first.', 'error')
            session.close()
            return redirect(url_for('list_venues'))
        session.delete(venue)
        session.commit()
        flash('Venue deleted successfully', 'success')
        session.close()
        return redirect(url_for('list_venues'))
