def register_categories(app):
    from flask import render_template, request, jsonify, redirect, url_for, flash
    from database import SessionLocal, Category

    @app.route('/categories')
    def list_categories():
        session = SessionLocal()
        try:
            categories = session.query(Category).order_by(Category.usage_count.desc(), Category.name).all()
            return render_template('categories.html', categories=categories)
        finally:
            session.close()

    @app.route('/category/new', methods=['GET', 'POST'])
    def add_category():
        if request.method == 'POST':
            name = request.form['name']
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Category name is required', 'error')
                return render_template('category_form.html', name=name, is_active=is_active)
            
            session = SessionLocal()
            try:
                # Check if category already exists
                existing = session.query(Category).filter_by(name=name).first()
                if existing:
                    flash('A category with this name already exists', 'error')
                    return render_template('category_form.html', name=name, is_active=is_active)
                
                category = Category(name=name, is_active=is_active, usage_count=0)
                session.add(category)
                session.commit()
                flash('Category added successfully', 'success')
                return redirect(url_for('list_categories'))
            finally:
                session.close()
        
        return render_template('category_form.html')

    @app.route('/category/<int:id>/edit', methods=['GET', 'POST'])
    def edit_category(id):
        session = SessionLocal()
        category = session.query(Category).get_or_404(id)
        
        if request.method == 'POST':
            name = request.form['name']
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Category name is required', 'error')
                session.close()
                return render_template('category_form.html', category=category, name=name, is_active=is_active)
            
            # Check if name already exists (excluding current category)
            existing = session.query(Category).filter(Category.name == name, Category.id != id).first()
            if existing:
                flash('A category with this name already exists', 'error')
                session.close()
                return render_template('category_form.html', category=category, name=name, is_active=is_active)
            
            category.name = name
            category.is_active = is_active
            session.commit()
            flash('Category updated successfully', 'success')
            session.close()
            return redirect(url_for('list_categories'))
        
        session.close()
        return render_template('category_form.html', category=category)

    @app.route('/category/<int:id>/delete', methods=['POST'])
    def delete_category(id):
        session = SessionLocal()
        category = session.query(Category).get_or_404(id)
        
        # Check if category is used by any events
        from database import Event
        events_using_category = session.query(Event).filter(
            Event.categories.contains(category.name)
        ).count()
        
        if events_using_category > 0:
            flash(f'Cannot delete category "{category.name}" because it is used by {events_using_category} event(s). Please reassign or remove those events first.', 'error')
            session.close()
            return redirect(url_for('list_categories'))
        
        session.delete(category)
        session.commit()
        flash('Category deleted successfully', 'success')
        session.close()
        return redirect(url_for('list_categories')) 