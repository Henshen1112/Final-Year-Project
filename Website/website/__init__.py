from flask import Flask,render_template,redirect,request,url_for,session
from os import path

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'website'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:1234@localhost/university_timetable'

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    return app