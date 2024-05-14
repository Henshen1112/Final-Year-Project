from flask import session,Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import current_user,login_user, login_required, logout_user, current_user
import mysql.connector
db = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="1234",
    database="university_timetable"
)

mycursor = db.cursor()

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.pop('user_id', None)
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please enter both email and password.', category='error')
        else:
            # Check if the email already exists in the database
            mycursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = mycursor.fetchone()

            if existing_user:
                if password == existing_user[2]:
                    session['user_id'] = existing_user[0]
                    flash('Welcome ' + existing_user[1] + '!', category='success')
                    return redirect(url_for('views.home'))
                else:
                    flash('Incorrect password, please try again.', category='error')
            else:
                flash('Email does not exist.', category='error')

    return render_template("login.html")



@auth.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", 'success')
    return redirect(url_for('auth.login'))


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')

        if not email or not full_name or not password:
            flash('Please fill in all the required fields.', category='error')
        else:
            # Check if the email already exists in the database
            mycursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = mycursor.fetchone()

            if existing_user:
                flash('Email already exists. Please choose a different email.', category='error')
            else:
                # Insert the new user into the database
                mycursor.execute("INSERT INTO users (email, full_name, password) VALUES (%s, %s, %s)", (email, full_name, password))
                db.commit()

                flash(email + ' created successfully!', category='success')
                return redirect(url_for('auth.login'))

    return render_template("sign_up.html")


@auth.route('/lecturer', methods=['GET', 'POST'])
def lecturer():
    if request.method == 'POST':
        lid = request.form.get('lid')
        lecturer_name = request.form.get('lecturer_name')
        preferences = request.form.getlist('preference')
        qualifications = request.form.getlist('qualification')

        if not lid or not lecturer_name:
            flash('Please enter a value for both Lecturer ID and Lecturer Name.', category='error')
        elif not preferences:
            flash('Please select at least one preference.', category='error')
        elif not qualifications:
            flash('Please select at least one qualification.', category='error')
        else:
            try:
                # Execute the SQL query to insert the record
                mycursor.execute("INSERT INTO lecturer (lid, lecturer_name) VALUES (%s, %s)",
                                 (lid, lecturer_name))
                db.commit()

                # Insert lecturer preferences into the 'lecturer_preferences' table
                for preference in preferences:
                    mycursor.execute("INSERT INTO lecturer_preferences (lid, cid) VALUES (%s, %s)",
                                     (lid, preference))
                    db.commit()

                # Insert lecturer qualifications into the 'lecturer_qualifications' table
                for qualification in qualifications:
                    mycursor.execute("INSERT INTO lecturer_qualifications (lid, cid) VALUES (%s, %s)",
                                     (lid, qualification))
                    db.commit()

                flash(lecturer_name + ' Added!', category='success')
            except mysql.connector.IntegrityError as e:
                # Handle the integrity constraint violation error (duplicate lid)
                flash('Lecturer ID or Lecturer Name already exists. Please try again.', category='error')

    mycursor.execute("SELECT lecturer.lid, lecturer.lecturer_name, "
                     "GROUP_CONCAT(DISTINCT course.course_name ORDER BY lecturer_preferences.cid SEPARATOR ', ') AS preferences, "
                     "GROUP_CONCAT(DISTINCT qualification.course_name ORDER BY lecturer_qualifications.cid SEPARATOR ', ') AS qualifications "
                     "FROM lecturer "
                     "LEFT JOIN lecturer_preferences ON lecturer.lid = lecturer_preferences.lid "
                     "LEFT JOIN course ON lecturer_preferences.cid = course.cid "
                     "LEFT JOIN lecturer_qualifications ON lecturer.lid = lecturer_qualifications.lid "
                     "LEFT JOIN course AS qualification ON lecturer_qualifications.cid = qualification.cid "
                     "GROUP BY lecturer.lid, lecturer.lecturer_name "
                     "ORDER BY CAST(SUBSTRING(lecturer.lid, 2) AS UNSIGNED) ASC")
    lecturers = mycursor.fetchall()

    mycursor.execute("SELECT cid, course_name FROM course ORDER BY cid ASC")
    courses = mycursor.fetchall()

    return render_template("lecturer.html", lecturers=lecturers, courses=courses)


@auth.route('/lecturer/<lid>/edit', methods=['GET', 'POST'])
def edit_lecturer(lid):
    # Retrieve the lecturer data for the given ID from the database
    mycursor.execute("""
        SELECT l.lid, l.lecturer_name,
            GROUP_CONCAT(DISTINCT cp.course_name ORDER BY cp.course_name SEPARATOR ',') AS preferences,
            GROUP_CONCAT(DISTINCT cq.course_name ORDER BY cq.course_name SEPARATOR ',') AS qualifications
        FROM lecturer l
        LEFT JOIN lecturer_preferences p ON l.lid = p.lid
        LEFT JOIN course cp ON p.cid = cp.cid
        LEFT JOIN lecturer_qualifications q ON l.lid = q.lid
        LEFT JOIN course cq ON q.cid = cq.cid
        WHERE l.lid = %s
        GROUP BY l.lid
    """, (lid,))
    lecturer = mycursor.fetchone()

    if request.method == 'POST':
        # Retrieve the updated data from the form
        updated_name = request.form.get('lecturer_name')
        preferences = request.form.getlist('preference')
        qualifications = request.form.getlist('qualification')

        if not updated_name:
            flash('Please enter a lecturer name.', category='error')
        elif not preferences:
            flash('Please select at least one preference.', category='error')
        elif not qualifications:
            flash('Please select at least one qualification.', category='error')
        else:
            # Check if the updated lecturer name already exists (excluding the current lecturer)
            mycursor.execute("SELECT lid FROM lecturer WHERE lecturer_name = %s AND lid != %s", (updated_name, lid))
            existing_lecturer = mycursor.fetchone()

            if existing_lecturer:
                flash('Lecturer name already exists. Please choose a different name.', category='error')
            else:
                try:
                    # Update the lecturer's data in the database
                    mycursor.execute("UPDATE lecturer SET lecturer_name = %s WHERE lid = %s", (updated_name, lid))
                    db.commit()

                    # Update lecturer preferences in the 'lecturer_preferences' table
                    mycursor.execute("DELETE FROM lecturer_preferences WHERE lid = %s", (lid,))
                    for preference in preferences:
                        mycursor.execute("INSERT INTO lecturer_preferences (lid, cid) VALUES (%s, %s)", (lid, preference))
                    db.commit()

                    # Update lecturer qualifications in the 'lecturer_qualifications' table
                    mycursor.execute("DELETE FROM lecturer_qualifications WHERE lid = %s", (lid,))
                    for qualification in qualifications:
                        mycursor.execute("INSERT INTO lecturer_qualifications (lid, cid) VALUES (%s, %s)", (lid, qualification))
                    db.commit()

                    flash(updated_name+' updated!', category='success')
                    return redirect(url_for('auth.lecturer'))
                except mysql.connector.IntegrityError as e:
                    # Handle the integrity constraint violation error (duplicate lecturer name)
                    flash('Lecturer name already exists. Please choose a different name.', category='error')

    mycursor.execute("SELECT cid, course_name FROM course")
    courses = mycursor.fetchall()

    mycursor.execute("""
        SELECT l.lid, l.lecturer_name,
            GROUP_CONCAT(DISTINCT cp.course_name ORDER BY cp.course_name SEPARATOR ',') AS preferences,
            GROUP_CONCAT(DISTINCT cq.course_name ORDER BY cq.course_name SEPARATOR ',') AS qualifications
        FROM lecturer l
        LEFT JOIN lecturer_preferences p ON l.lid = p.lid
        LEFT JOIN course cp ON p.cid = cp.cid
        LEFT JOIN lecturer_qualifications q ON l.lid = q.lid
        LEFT JOIN course cq ON q.cid = cq.cid
        GROUP BY l.lid
        ORDER BY l.lid ASC
    """)
    lecturers = mycursor.fetchall()

    return render_template("lecturer.html", lecturers=lecturers, edit_lecturer=lecturer, courses=courses)


@auth.route('/delete_lecturer/<lid>', methods=['GET', 'POST'])
def delete_lecturer(lid):
    try:
        # Delete the lecturer preferences associated with the lecturer
        mycursor.execute("DELETE FROM lecturer_preferences WHERE lid = %s", (lid,))
        db.commit()

        # Delete the lecturer qualifications associated with the lecturer
        mycursor.execute("DELETE FROM lecturer_qualifications WHERE lid = %s", (lid,))
        db.commit()

        # Delete the lecturer's data from the database
        mycursor.execute("DELETE FROM lecturer WHERE lid = %s", (lid,))
        db.commit()

        flash('Lecturer deleted!', category='success')
    except mysql.connector.IntegrityError as e:
        # Handle the integrity constraint violation error
        flash('Cannot delete the lecturer. Please ensure there are no dependent records.', category='error')

    return redirect(url_for('auth.lecturer'))

@auth.route('/room', methods=['GET', 'POST'])
def room():
    rooms = []

    if request.method == 'POST':
        rid = request.form.get('rid')
        seat = request.form.get('seat')
        room_type = request.form.get('room_type')

        if not rid or not seat or not room_type:
            flash('Please fill in all fields.', category='error')
        else:
            try:
                seat = int(seat)

                if seat <= 0:
                    raise ValueError("Seat value must be a positive integer.")

                # Execute the SQL query to insert the record
                mycursor.execute("INSERT INTO room (rid, seat, room_type) VALUES (%s, %s, %s)", (rid, seat, room_type))
                db.commit()
                flash(rid + ' Added!', category='success')
            except ValueError:
                # Handle the error when the seat value is not a valid positive integer
                flash('Seat value must be a valid positive integer. Please try again.', category='error')
            except mysql.connector.IntegrityError as e:
                # Handle the integrity constraint violation error (duplicate rid)
                flash('Room ID already exists. Please try again.', category='error')

    # Retrieve room data from the database
    mycursor.execute("SELECT rid, seat, room_type FROM room ORDER BY CAST(SUBSTRING(room.rid, 3) AS UNSIGNED) ASC")
    rooms = mycursor.fetchall()

    return render_template("room.html", rooms=rooms)





@auth.route('/course', methods=['GET', 'POST'])
def course():
    if request.method == 'POST':
        cid = request.form.get('cid')
        course_name = request.form.get('course_name')
        
        if not cid or not course_name:
            flash('Please enter a value for both Course ID and Course Name.', category='error')
        else:
            try:
                # Execute the SQL query to insert the new course into the database
                mycursor.execute("INSERT INTO course (cid, course_name) VALUES (%s, %s)", (cid, course_name))
                db.commit()
                flash(cid + ' ' + course_name + ' Added!', category='success')
            except mysql.connector.IntegrityError as e:
                # Handle the integrity constraint violation error (duplicate cid)
                flash('Course ID already exists. Please try again.', category='error')
            except Exception as e:
                # Handle other unexpected errors
                flash('An error occurred while adding the course. Please try again later.', category='error')

    # Retrieve the updated list of courses from the database
    mycursor.execute("SELECT cid, course_name FROM course ORDER BY cid ASC")
    courses = mycursor.fetchall()

    return render_template("course.html", courses=courses)


@auth.route('/classgroup', methods=['GET', 'POST'])
def classgroup():
    if request.method == 'POST':
        cid = request.form.get('course_id')
        class_type = request.form.get('class_type')
        duration = request.form.get('duration')

        if not cid or not class_type or not duration:
            flash('Please enter values for Course ID, Class Type, and Duration.', category='error')
        else:
            try:
                # Execute the SQL query to insert the record
                mycursor.execute("INSERT INTO classgroup (cid, class_type, duration) VALUES (%s, %s, %s)",
                             (cid, class_type, duration))
                db.commit()
                flash(class_type + ' Added!', category='success')
            except mysql.connector.IntegrityError as e:
                # Handle the integrity constraint violation error
                flash('Class already exists. Please try again.', category='error')

    mycursor.execute("SELECT cg.gid, cg.cid, cg.class_type, cg.duration, c.course_name FROM classgroup cg INNER JOIN course c ON cg.cid = c.cid ORDER BY cg.gid ASC")
    classgroups = mycursor.fetchall()

    mycursor.execute("SELECT cid, course_name FROM course ORDER BY cid ASC")
    courses = mycursor.fetchall()

    return render_template("classgroup.html", classgroups=classgroups, courses=courses)

@auth.route('/studentgroup', methods=['GET', 'POST'])
def studentgroup():
    if request.method == 'POST':
        program = request.form.get('program')
        classgroup_ids = request.form.getlist('classgroup_id')
        studentgroup_name = request.form.get('studentgroup_name')
        year_level = request.form.get('year_level')
        
        if not program or not classgroup_ids or not studentgroup_name or not year_level:
            flash('Please enter values for all fields.', category='error')
        else:
            try:
                # Insert separate records for each selected classgroup_id
                for classgroup_id in classgroup_ids:
                    mycursor.execute("INSERT INTO studentgroup (gid, program, studentgroup_name, year_level) VALUES (%s, %s, %s, %s)",
                                 (classgroup_id, program, studentgroup_name, year_level))
                    db.commit()
                flash('Student Groups added successfully!', category='success')
            except mysql.connector.IntegrityError as e:
                # Handle the integrity constraint violation error (duplicate studentgroup_id)
                flash('Student Group already exists. Please try again.', category='error')

    mycursor.execute("SELECT sg.sgid, sg.program, cg.class_type, cg.cid, c.course_name, sg.studentgroup_name, sg.year_level FROM studentgroup sg JOIN classgroup cg ON sg.gid = cg.gid JOIN course c ON cg.cid = c.cid ORDER BY sg.sgid ASC")
    studentgroups = mycursor.fetchall()

    mycursor.execute("SELECT cg.gid, cg.class_type, cg.cid, c.course_name FROM classgroup cg JOIN course c ON cg.cid = c.cid ORDER BY cg.gid ASC")
    classgroups = mycursor.fetchall()

    return render_template("studentgroup.html", studentgroups=studentgroups, classgroups=classgroups)


@auth.route('/delete_studentgroup/<int:sgid>', methods=['GET'])
def delete_studentgroup(sgid):
    # Delete the student group from the table
    delete_query = "DELETE FROM studentgroup WHERE sgid = %s"
    mycursor.execute(delete_query, (sgid,))
    db.commit()

    # Reset the auto-increment counter
    reset_query = "ALTER TABLE studentgroup AUTO_INCREMENT = 1"
    mycursor.execute(reset_query)
    db.commit()

    flash('Student Group deleted successfully!', category='success')

    return redirect(url_for('auth.studentgroup'))