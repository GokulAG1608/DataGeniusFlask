from flask import Flask,jsonify,request,render_template
from flask_cors import CORS

# call the confluence file
from confluence import *
# call the pdf file
from pdf1 import *
# call the csv file
from my_csv import *
# call the sql file
from my_sql import *

from plot import *

from feedback import *

app = Flask(__name__)
CORS(app, supports_credentials=True)


# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root123@localhost:3306/user_credentials'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tucEDtE44BbQLv7tXCivZkn1DbmKGsYn'

# Initialize the SQLAlchemy database
db.init_app(app)

# Create all tables if they don't exist
with app.app_context():
    db.create_all()

# @app.route('/user/signin', methods=['POST'])
# def user_signin():
#     data = request.json
#     return jsonify(*signin(data, app.config['SECRET_KEY']))
@app.route('/user/signin', methods=['POST'])
def user_signin():
    data = request.json
    response, status_code = signin(data, app.config['SECRET_KEY'])
    return jsonify(response), status_code

@app.route('/user/register', methods=['POST'])
def user_register():
    data = request.json
    response, status_code = register(data)
    return jsonify(response), status_code


@app.route('/user/forgot', methods=['POST'])
def user_forgot_password():
    data = request.json
    response, status_code = forgot_password(data)
    return jsonify(response), status_code


@app.route('/user/auth', methods=['GET'])
def auth():
    auth_header = request.headers.get('Authorization')
    
    if auth_header:
        try:
            token = auth_header.split(" ")[1]
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            
            log_activities(
                user_id=decoded.get('user_id'),
                email=decoded.get('email'),
                activity_type="Token Validation",
                activity_content="Token validated successfully",
                response_content="Token is valid",
                error_message=None,
                app_name=None
            )
            
            return jsonify({"status": "Success", "data": decoded}), 200
        
        except jwt.ExpiredSignatureError:
            log_activities(
                user_id=None,
                email=None,
                activity_type="Token Validation",
                activity_content="Token expired",
                response_content="Token is expired",
                error_message="Token expired"
            )
            return jsonify({"status": "Failure", "message": "Token expired"}), 401
        
        except jwt.InvalidTokenError:
            log_activities(
                user_id=None,
                email=None,
                activity_type="Token Validation",
                activity_content="Invalid token",
                response_content="Token is invalid",
                error_message="Invalid token"
            )
            return jsonify({"status": "Failure", "message": "Invalid token"}), 401
    
    else:
        log_activities(
            user_id=None,
            email=None,
            activity_type="Token Validation",
            activity_content="Token is missing",
            response_content="No token provided",
            error_message="Token is missing"
        )
        return jsonify({"status": "Failure", "message": "Token is missing"}), 401

@app.route('/dashboard', methods=['POST'])
def get_emails():
    try:
        data = request.json  # JSON body is available in POST requests
        emails = data.get('Email')  # Corrected variable name

        # Fetch the user from the database using the provided email
        user = UserInfo.query.filter_by(Email=emails).first()

        if not user:
            return jsonify({'status':'Error', 'message': 'User not found'}), 404

        if user.RoleId == 1:
            # If RoleId is 1, return all user emails
            emails_list = [user.Email for user in UserInfo.query.all()]
            return jsonify({'status': 'Success', 'message': 'Emails retrieved successfully', 'emails': emails_list})
        else:
            # Otherwise, return the current user's email
            return jsonify({'status': 'Success', 'message': 'Email retrieved successfully', 'emails': user.Email})

    except Exception as e:
        return jsonify({'status': 'Error', 'message': f'An error occurred: {str(e)}'}), 500   
@app.route('/plot', methods=['GET'])
def plots():
    return plot_route()


#! FEEDBACK

@app.route('/feedback', methods=['POST'])
def feedback1():
    return feedback()


#! CONFLUENCES

@app.route('/chat1', methods=['POST'])
def cf_chat():
    return chat1()

@app.route('/suggestion', methods=['POST'])
def cf_question():
    return suggestion()
    

#! PDF

@app.route("/ask_question", methods=["POST"])
def p_ask_questions():
    return ask_question()

@app.route("/generate_top_questions", methods=["POST"])
def p_generate_questions():
    return generate_top_questions_route()

@app.route("/chat_history", methods=["GET"])
def p_history():
    return get_chat_history()


#! CSV 

@app.route('/load_files', methods=['POST'])
def c_loadfiles():
    return load_files()
