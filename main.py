import os
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user,login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text,ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm,RegisterForm,LoginForm,CommentForm




'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")
print(app.config['SECRET_KEY'])
ckeditor = CKEditor(app)
Bootstrap5(app)
gravatar = Gravatar(app)

login_manager = LoginManager()
login_manager.login_view = "login"

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
db = SQLAlchemy(model_class=Base)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI","sqlite:///db.sqlite3")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
login_manager.init_app(app)

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blogposts"
    id = db.Column(db.Integer, primary_key=True)
    title=db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date=db.Column(db.String(250), nullable=False)
    body=db.Column(db.Text, nullable=False)
    author_id=db.Column(db.Integer,db.ForeignKey("users.id"))
    img_url=db.Column(db.String(250), nullable=False)
    comments = db.relationship("Comments",backref="blogposts")

class Users(db.Model,UserMixin):
    __tablename__ = "users"
    id=db.Column(db.Integer,primary_key=True)
    email=db.Column(db.String,unique=True,nullable=False)
    password=db.Column(db.String,nullable=False)
    name = db.Column(db.String,nullable=False)
    posts = db.relationship("BlogPost",backref="poster")
    comments = db.relationship("Comments",backref="commenter")


class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer,primary_key=True)
    text = db.Column(db.Text,nullable=False)
    author_id = db.Column(db.Integer,db.ForeignKey("users.id"))
    post_id = db.Column(db.Integer,db.ForeignKey("blogposts.id"))



with app.app_context():
    db.create_all()

#CREATE DECORATOR
def admin_only(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        admin_id = current_user.get_id()
        if current_user.is_authenticated:
            if admin_id == "1":
                return func(*args,**kwargs)
            else:
                abort(403)
        else:
            abort(403)
    return wrapper


@app.route('/register',methods = ["GET","POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        #checking if added email is in database
        users = db.session.execute(db.select(Users).order_by(Users.email)).scalars().all()
        for user in users:
            if user.email == form.email.data:
                flash("You've already signed up with that email.Log in instead!")
                return redirect(url_for("login"))

        #registering and adding users to database
        new_user = Users(
            email = form.email.data,
            password = generate_password_hash(form.password.data,method="pbkdf2:sha256",salt_length=8),
            name = form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("register.html",form = form)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users,user_id)

@app.route('/login',methods=["GET","POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        #logging in users
        user = Users.query.filter_by(email=login_form.email.data).first()
        if user:
            #checking if password is correct
            if check_password_hash(user.password,login_form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Password incorrect,try again!")
        else:
            flash("This email doesn't exist!")

    return render_template("login.html",form = login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    admin_id = current_user.get_id()
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts,current_user=current_user,admin_id=admin_id)


@app.route("/post/<int:post_id>",methods=["GET","POST"])
def show_post(post_id):

    form = CommentForm()
    #Adding comments into database
    if form.validate_on_submit():
        #Checking if user is logged in or not
        if current_user.is_authenticated:
            new_comment = Comments(
                text=form.comment.data,
                author_id = current_user.id,
                post_id = post_id
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You need to login or register to comment!")
            return redirect(url_for("login"))

    user_comments = db.session.execute(db.select(Comments).order_by(Comments.id)).scalars().all()
    admin_id = current_user.get_id()
    requested_post = db.get_or_404(BlogPost, post_id)
    return render_template("post.html", post=requested_post,admin_id=admin_id,
                           current_user=current_user,form=form,user_comments=user_comments)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id = current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)
