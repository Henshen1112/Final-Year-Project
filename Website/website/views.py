from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, make_response, Blueprint
from website.genetic_algorithm import genetic_algorithm
import mysql.connector
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.paragraph import Paragraph

# Create a MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="university_timetable"
)

views = Blueprint('views', __name__)

@views.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))  # Redirect to the login page

    if request.method == 'POST':
        year_levels = request.form.getlist('year_level')
        programs = request.form.getlist('program')
        student_groups = request.form.getlist('studentGroup')

        all_timetables = []

        best_timetable = genetic_algorithm(year_levels, programs, student_groups)
        if any(best_timetable):
            all_timetables.append({
                'year_levels': year_levels,
                'programs': programs,
                'student_groups': student_groups,
                'timetable': best_timetable
            })

        session['all_timetables'] = all_timetables  # Store all_timetables in the session

        return render_template("timetables.html", all_timetables=all_timetables)

    return render_template("home.html")

@views.route('/download_pdf')
def download_pdf():
    all_timetables = session.get('all_timetables')  # Retrieve the timetable data from the session

    if all_timetables:
        response = make_response(generate_pdf(all_timetables))  # Pass all_timetables to generate PDF content
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=timetable.pdf'
        return response
    else:
        flash('Timetable data not available for download.', category='error')
        return redirect(url_for('views.home'))

def generate_pdf(timetable_data):
    buffer = BytesIO()

    # Create a new PDF document with landscape orientation
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    story = []

    # Add a title to the PDF
    title = Paragraph("UTeM FTMK Timetable", getSampleStyleSheet()["Title"])
    story.append(title)

    # Loop through each timetable and create a table for each
    for timetable in timetable_data:
        table_data = [
            ["Time", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        ]  # Start with the header row

        # Populate the timetable cells
        for hour in range(9, 18):
            row = [f"{hour}:00 - {hour + 1}:00"]
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                classes = []
                for timeslot in timetable['timetable']:
                    if timeslot['day'] == day and timeslot['hour'] <= hour < timeslot['hour'] + timeslot['duration']:
                        classes.append(
                            f"{timeslot['class_type']} - {timeslot['cid']}\n"
                            f"{timeslot['room_id']}\n"
                            f"{timeslot['lecturer_name']}\n"
                            f"{timeslot['year_level']} {timeslot['program']} {timeslot['student_group']}"
                        )
                row.append('\n'.join(classes))
            table_data.append(row)

        table = Table(table_data, colWidths=[90, 120, 120, 120, 120, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Apply background to header row
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Apply background to data rows
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        story.append(table)
        story.append(Spacer(1, 20))  # Add some space between tables

    doc.build(story)  # Build the PDF document
    buffer.seek(0)
    return buffer.read()