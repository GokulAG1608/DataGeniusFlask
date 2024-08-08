from flask import Flask,jsonify,request,render_template
from flask_cors import CORS

#call the confluence file
from confluence import *
#call the pdf file
from pdf1 import *
#call the csv file
from my_csv import *
#call the sql file
from my_sql import *


app = Flask(__name__)
CORS(app)


# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost:3306/user_credentials'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tucEDtE44BbQLv7tXCivZkn1DbmKGsYn'

# Initialize the SQLAlchemy database
db.init_app(app)

# Create all tables if they don't exist
with app.app_context():
    db.create_all()

@app.route('/user/signin', methods=['POST'])
def user_signin():
    data = request.json
    return jsonify(*signin(data, app.config['SECRET_KEY']))

@app.route('/user/register', methods=['POST'])
def user_register():
    data = request.json
    return jsonify(*register(data))

@app.route('/user/forgot', methods=['POST'])
def user_forgot_password():
    data = request.json
    return jsonify(*forgot_password(data))

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

#! CONFLUENCES

@app.route('/chat1', methods=['POST'])
def cf_chat():
    return chat1()

@app.route('/feedback', methods=['POST'])
def cf_feedback():
    return feedback1()

@app.route('/suggestion', methods=['POST'])
def cf_question():
    return suggestion()
    

#! PDF

@app.route("/upload", methods=["POST"])
def p_uploads():
    return upload()

@app.route("/ask_question", methods=["POST"])
def p_ask_questions():
    return ask_question()

@app.route("/generate_top_questions", methods=["POST"])
def p_generate_questions():
    return generate_top_questions_route()

@app.route("/dislike_feedback", methods=["POST"])
def p_feedback():
    return dislike_feedback()

@app.route("/like_feedback", methods=["POST"])
def p_feedback1():
    return submit_feedback()

@app.route("/chat_history", methods=["GET"])
def p_history():
    return get_chat_history()


#! CSV 

@app.route('/load_files', methods=['POST'])
def c_loadfiles():
    return load_files()

@app.route('/upload_files', methods=['POST'])
def c_uploadfiiles():
    return upload_files()

@app.route('/question', methods=['POST'])
def c_question():
    return ask_questions()

@app.route('/feedback1', methods=['POST'])
def c_feedback():
    return feedback()

@app.route('/smart_suggestion', methods=['POST'])
def c_suggestion():
    return smart_suggestion()

@app.route('/temp_plots/<filename>')
def c_plot():
    return serve_plot()


#! SQL 

@app.route('/chat', methods=['POST'])
def s_chat():
    return chat()

@app.route('/get_random_questions', methods=['POST'])
def s_question():
    return get_random_questions_route()

@app.route("/dislike_feedback_sql", methods=["POST"])
def s_feedback():
    return dislike_feedback1()

@app.route("/like_feedback_sql", methods=["POST"])
def s_feedback1():
    return submit_feedback1()




if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=3796)