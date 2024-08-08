# db.py
import datetime
from flask import session
from flask_sqlalchemy import SQLAlchemy
import jwt
import bcrypt

# Initialize the SQLAlchemy database
db = SQLAlchemy()

# Define the UserInfo model
class UserInfo(db.Model):
    __tablename__ = 'user'
    
    Pid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Email = db.Column(db.String(500), unique=True, nullable=False)
    Name = db.Column(db.String(100), nullable=False)
    Password = db.Column(db.String(500), nullable=False)
    IsActive = db.Column(db.Boolean, default=True, nullable=False)
    CreatedAt = db.Column(db.DateTime, default=datetime.datetime.now(), nullable=False)
    IsFirstLogin = db.Column(db.Boolean, default=True, nullable=False)
    RoleId = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<UserInfo {self.Name}>'

# Define the UserActivities model
class UserActivities(db.Model):
    __tablename__ = 'user_activities'

    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    User_id = db.Column(db.Integer, db.ForeignKey('user.Pid'), nullable=False)
    Email = db.Column(db.String(255), nullable=False)
    Login_time = db.Column(db.DateTime, default=datetime.datetime.now(), nullable=False)
    Activity_type = db.Column(db.String(50))
    Activity_content = db.Column(db.Text)
    Response_content = db.Column(db.Text)
    Prompt_Tokens = db.Column(db.Integer)
    Completion_Tokens = db.Column(db.Integer)
    Successful_Requests = db.Column(db.Integer)
    Total_Cost = db.Column(db.Float)  # Changed to Float to handle decimal values
    Error_message = db.Column(db.Text)
    Date = db.Column(db.DateTime, default=datetime.datetime.now(), nullable=False)
    App= db.Column(db.String(40))

    def __repr__(self):
        return f'<UserActivities {self.User_id} {self.Activity_type}>'

# Function to generate token for authentication
def generate_token(user, secret_key):
    payload = {
        'user_id': user.Pid,
        'email': user.Email,
        'roleid': user.RoleId,
        'name': user.Name,
        'isActive': user.IsActive,
        'createdAt': user.CreatedAt.isoformat(),
        'isFirstLogin': user.IsFirstLogin,
        'exp': datetime.datetime.now() + datetime.timedelta(hours=12)
    }
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token

# Function to log user activities
def log_activities(user_id, email, activity_type, activity_content=None, response_content=None, prompt_tokens=None, completion_tokens=None, successful_requests=None, total_cost=None, error_message=None, app_name=None):
    activity = UserActivities(
        User_id=user_id,
        Email=email,
        Activity_type=activity_type,
        Activity_content=activity_content,
        Response_content=response_content,
        Prompt_Tokens=prompt_tokens,
        Completion_Tokens=completion_tokens,
        Successful_Requests=successful_requests,
        Total_Cost=total_cost,
        Error_message=error_message,
        App=app_name
    )
    db.session.add(activity)
    db.session.commit()

# Function for user sign-in
def signin(data, secret_key):
    email = data.get('Email')
    password = data.get('Password')
    
    if not email or not password:
        return {"status": "Failure", "message": "Missing email or password"}, 400
    
    user = UserInfo.query.filter_by(Email=email).first()
    
    if not user:
        return {"status": "Failure", "message": "User not found"}, 404
    
    if bcrypt.checkpw(password.encode('utf-8'), user.Password.encode('utf-8')):
        token = generate_token(user, secret_key)
        session['user_id'] = user.Pid
        session['user_email'] = user.Email
        log_activities(user.Pid, email, "Login", "User logged in")
        return {"status": "Success", "message": "Sign in successful", "token": token}, 200
    else:
        return {"status": "Failure", "message": "Invalid password"}, 401

# Function for user registration
def register(data):
    roleId = data.get('RoleId')
    email = data.get('Email')
    name = data.get('Name')
    password = data.get('Password')
    
    if not roleId or not email or not name or not password:
        return {"status": "Failure", "message": "Missing RoleId, Email, Name, or Password"}, 400
    
    if UserInfo.query.filter_by(Email=email).first() is not None:
        return {"status": "Failure", "message": "Email already exists"}, 409
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).strip().decode('utf-8')
    
    new_user = UserInfo(RoleId=roleId, Email=email, Name=name, Password=hashed_password, IsActive=True, CreatedAt=datetime.datetime.now(), IsFirstLogin=True)
    db.session.add(new_user)
    db.session.commit()

    log_activities(new_user.Pid, email, "Registration", "User registered successfully")
    return {"status": "Success", "message": "Registered successfully!"}, 200

# Function for forgot password
def forgot_password(data):
    email = data.get('Email')
    new_password = data.get('newPassword')
    confirm_password = data.get('confirmPassword')

    if not email or not new_password or not confirm_password:
        return {"status": "Failure", "message": "Missing email, new password, or confirm password"}, 400
    
    if new_password != confirm_password:
        return {"status": "Failure", "message": "Passwords do not match"}, 400
    
    user = UserInfo.query.filter_by(Email=email).first()
    
    if not user:
        return {"status": "Failure", "message": "User not found"}, 404
    
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.Password = hashed_password
    user.IsFirstLogin = False
    db.session.commit()

    log_activities(user.Pid, email, "Password Reset", "User reset their password", "Password reset successfully")
    return {"status": "Success", "message": "Password updated successfully"}, 200
