from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash,request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user,login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import *
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Adding flask gravator:
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

gravatar.init_app(app)
# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(uid):
    return db.get_or_404(User, uid)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI","sqlite:///posts.db")

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Foreign key creation:
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users_table.id"))
    # Connection with author:
    author: Mapped["User"] = relationship("User", back_populates="posts")
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Linking to Comment Table:
    comments:Mapped[list["Comment"]] = relationship("Comment",back_populates="parent_post")

# TODO: Create a User table for all your registered users.
class User(UserMixin,db.Model):
    __tablename__ = "users_table"
    id:Mapped[int] = mapped_column(Integer,primary_key=True)
    email:Mapped[str] = mapped_column(String(50),unique = True)
    password: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(50))
    posts: Mapped[list["BlogPost"]] = relationship("BlogPost", back_populates="author")
    # Adding comments:
    comments : Mapped[list["Comment"]] = relationship("Comment",back_populates = "author")

# Comment Table:
class Comment(db.Model):
    __tablename__ = "comment"
    id:Mapped[int] = mapped_column(Integer,primary_key=True)
    text:Mapped[str] = mapped_column(Text,nullable=False)
    # Foreign Key:
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users_table.id"))
    # Linking to Users:
    author:Mapped["User"] = relationship("User",back_populates = "comments")
    # Linking to blogposts:
    post_id:Mapped[int] = mapped_column(Integer,ForeignKey("blog_posts.id"))
    parent_post:Mapped["BlogPost"] = relationship("BlogPost",back_populates = "comments")

with app.app_context():
    db.create_all()

# Custom Decorator:
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return function(*args, **kwargs)
    return decorated_function

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods = ["GET","POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if form.validate_on_submit():
            if db.session.execute(db.select(User).where(User.email == form.email.data)).scalar():
                flash("You've already registered with this email you can log in instead")
            else:
                user = User(
                    email = form.email.data,
                    password = generate_password_hash(form.password.data,method = "pbkdf2:sha256",salt_length = 8),
                    name = form.name.data,
                )
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for('get_all_posts'))
    return render_template("register.html",form = form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods = ["GET","POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        try:
            select = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
            if check_password_hash(select.password,form.password.data):
                login_user(select)
                return redirect(url_for('get_all_posts',uid = select.id))
            else:
                flash("Incorrect password")
        except:
            flash("Your account didn't exist. Please Register instead")
    return render_template("login.html",form = form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    if current_user.is_authenticated:
        return render_template("index.html", all_posts=posts,logged_in = current_user.is_authenticated,userid = current_user.id,uname = current_user.name)
    else:
        return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)

# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods = ["GET","POST"])
@login_required
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if request.method == "POST":
        if form.validate_on_submit():
            comment = Comment(
                text = form.comment.data,
                author = current_user,
                parent_post = requested_post,
            )
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('get_all_posts'))
    return render_template("post.html", post=requested_post,cform = form,logged_in = current_user.is_authenticated,userid = current_user.id)


# TODO: Use a decorator so only an admin user can create a new post
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
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form,logged_in = current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, int(post_id))
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if request.method == "POST":
        if edit_form.validate_on_submit():
            post.title = edit_form.title.data
            post.subtitle = edit_form.subtitle.data
            post.img_url = edit_form.img_url.data
            post.author = current_user
            post.body = edit_form.body.data
            db.session.commit()
            return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True,logged_in = current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route("/about")
def about():
    return render_template("about.html",logged_in = current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html",logged_in = current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=False)
