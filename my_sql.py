from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt
import bcrypt
import datetime
import hashlib
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_community.utilities.sql_database import SQLDatabase
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.callbacks import get_openai_callback
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt
import bcrypt
import datetime
import os
import secrets
import io
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import jwt
 
from userdb import db, generate_token, log_activities, signin, register, forgot_password, UserInfo, UserActivities
 
# Load environment variables
load_dotenv()
 
# Initialize Flask app
app = Flask(__name__)
CORS(app)
 
# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost:3306/user_credentials'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tucEDtE44BbQLv7tXCivZkn1DbmKGsYn'
db.init_app(app)  # Initialize the db with the Flask app

 
# Initialize the database
with app.app_context():
    db.create_all()
 

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




# ! CHAT API

def initialize_language_model():
    try:
        return ChatOpenAI(model='gpt-3.5-turbo', temperature=0, api_key="sk-proj-KHzaTujZGduAhDVL2GyfT3BlbkFJeLWhvD8web0AbEnkxcJc")
    except Exception as e:
        print(f"Error initializing language model: {e}")
        return None
 
def initialize_query_chain(db2):
    try:
        if db2:
            llm = initialize_language_model()
            generate_query = create_sql_query_chain(llm, db2)
            execute_query = QuerySQLDataBaseTool(db=db2)
            chain = generate_query | execute_query
            return chain
        else:
            print("Database not initialized.")
            return None
    except Exception as e:
        print(f"Error initializing query chain: {e}")
        return None
 
def initialize_database():
    try:
        db_user = "root"
        db_password = "1234"
        db_host = "localhost:3306"
        db_name = "user_credentials"
        if db_user and db_password and db_host and db_name:
            global db2
            db2=SQLDatabase.from_uri(f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}")
            return db2
        else:
            return None
    except Exception as e:
        print(f"Error initializing database: {e}")
        return None

def generate_answer_prompt():
        try:
            return PromptTemplate.from_template(
                """Given the following user question, corresponding SQL query, and SQL result, answer the user question with some neat description.
                If the user input is irrelevant to the database display message as follows:
                "I'm sorry, I cannot process the input provided as it does not relate to the database".
                If you have any specific questions related this database, please feel free to ask."
                Question: {question}
                SQL Query: {query}
                SQL Result: {result}
                Answer: """
            )
        except Exception as e:
            print(f"Error generating answer prompt: {e}")
            return None
 
def generate_output( chain, user_input, db2):
        try:
            greetings = ["hi", "hello", "hey"]
            previous_answers = {}  
            if user_input in greetings:
                return 'Hi 👋 Folk !, How can I assist you?'
            elif user_input in previous_answers:
                return previous_answers[user_input]
            else:
                llm = initialize_language_model()
                if not llm:
                    return "Error initializing language model."
 
                generate_query = create_sql_query_chain(llm, db2)
                execute_query = QuerySQLDataBaseTool(db=db2)
                chain = generate_query | execute_query
                rephrase_answer = generate_answer_prompt() |initialize_language_model() | StrOutputParser()
                chain = (
                    RunnablePassthrough.assign(query=generate_query).assign(
                        result=itemgetter("query") | execute_query
                    )
                    | rephrase_answer
                )
                with get_openai_callback() as cost:
                    answer = chain.invoke({'question': f"Provide me only the query don't give any other additional words such as sql to the human {user_input}"})
                    global prompt_Tokens, completion_Tokens, successful_Requests, total_Cost
 
                    previous_answers[user_input] = answer
                    prompt_Tokens = cost.prompt_tokens
                    completion_Tokens = cost.completion_tokens
                    successful_Requests = cost.successful_requests
                    total_Cost = cost.total_cost
                    return answer
        except Exception as e:
            print(f"Error generating output: {e}")
            return "An error occurred while processing your request."
        
def suggestion_question_prompt():
    try:
        dbd=initialize_database()
        messages = [
                {
                    "role": "user",
                    "content": f"""you are a user question generator, I will connect my database above.
                                Table information: {dbd.table_info} - this function helps to show the table details like column name and information related to the database. Analyze the table information carefully based on that you must create three different questions related to the database. Don't create incorrect or irrelevant questions. Important: only generate the questions, don't give any additional words like **Question 1:**."""
                }
            ]

            # Initializing the ChatOpenAI instance
        chat = ChatOpenAI(
                model='gpt-3.5-turbo',
                api_key="sk-proj-KHzaTujZGduAhDVL2GyfT3BlbkFJeLWhvD8web0AbEnkxcJc"
            )

        response = chat.invoke(messages)

            # Extracting only the content from the response
        questions = response.content.strip().split('\n')
        print(questions)
        return questions
    except Exception as e:
        print(f"Error in suggestion question prompt: {e}")
        return None

def get_random_questions():
    try:
        default_questions=suggestion_question_prompt()
        return default_questions
    except Exception as e:
        print(f"Error get gemini response: {e}")
        return None


def chat():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header is missing."}), 401

        # Extract the token from the header
        token = auth_header.split(" ")[1]
          # Decode the JWT token
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401
          # Extract user email from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"error": "User email not found in token."}), 401

        # Fetch user data from the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"error": "User data not found."}), 404

        # Get data from POST request
        data = request.json
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({"error": "user_input is required."}), 400

        db2 = initialize_database()
        if not db2:
            return jsonify({"error": "Database initialization failed."}), 500
        
        # Initialize query chain
        global chain
        if 'chain' not in globals() or chain is None:
            chain = initialize_query_chain(db2)
            if not chain:
                return jsonify({"error": "Query chain initialization failed."}), 500

        # Generate the output response
        response_content = generate_output(chain, user_input, db2)
        response_id = hash(user_input)  # Generate a unique identifier for the response

        log_activities(
            user_id=user_data.Pid,
            email=user_email,
            app_name='pdf',
            activity_type='File Upload',
            activity_content='Files uploaded successfully',
            response_content='Files processed and stored',
            prompt_tokens=None,
            completion_tokens=None,
            successful_requests=None,
            total_cost=None,
            error_message=None
            )

        return jsonify({"response": response_content, "id": response_id})
    except Exception as e:
        print(f"Error in chat route: {e}")
        log_activities(user_id=None,email=user_email, activity_type='error',app_name='sql', error_message=str(e))  # Log error
        return jsonify({"error": "An error occurred while processing your request."}), 500

def get_random_questions_route():
    try:
        # Authorization Header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header is missing."}), 401

        # Extract the token
        try:
            token = auth_header.split(" ")[1]
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401

        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"error": "User email not found in token."}), 401

        # Fetch user data from the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"error": "User data not found."}), 404

        # Generate random questions
        try:
            random_questions = get_random_questions()
            if isinstance(random_questions, str):
                questions = random_questions.strip().split('\n')
            elif isinstance(random_questions, list):
                questions = random_questions
            else:
                questions = []
        except Exception as e:
            return jsonify({"error": "Failed to generate random questions: " + str(e)}), 500

        # Log user activity
        log_activities(
            user_id=user_data.Pid,
            email=user_email,
            activity_type='Generate Random Questions',
            activity_content='Random questions generated successfully',
            response_content=str(questions),
            app_name='sql'
        )

        return jsonify({"random_questions": questions}), 200

    except Exception as e:
        # Log the error activity
        log_activities(
            user_id=user_data.Pid if 'user_data' in locals() else None,
            email=user_email if 'user_email' in locals() else None,
            activity_type='error',
            app_name='get_random_questions',
            error_message=str(e)
        )
        return jsonify({"error": "An error occurred while generating random questions: " + str(e)}), 500




    
    
# Ensure chat_history is defined somewhere globally or in session context
chat_history = []  # This should be maintained with user interactgghnbctf hjtions elsewhere in your code

def dislike_feedback1():
    try:
        # Authorization Header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header is missing."}), 401

        # Extract the token
        token = auth_header.split(" ")[1]
        try:
            decoded_token = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401

        # Get user information from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"error": "User email not found in token."}), 401

        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"error": "User data not found."}), 404

        # Get feedback data from request
        feedback_data = request.json
        chosen_option = feedback_data.get('option')

        # Check if the chosen option is valid
        options = {
            "1": "The response was inaccurate.",
            "2": "The response was unclear.",
            "3": "The response was too long.",
            "4": "The response was irrelevant."
        }

        if chosen_option not in options:
            return jsonify({"error": "Invalid option selected."}), 400

        # Get the full feedback message
        feedback_message = options[chosen_option]

        # Retrieve the last user question and answer from chat history
        last_user_question = None
        last_user_answer = None

        # Debugging: Print the chat history
        print("Chat History:", chat_history)

        for entry in reversed(chat_history):
            if entry["role"] == "user" and last_user_question is None:
                last_user_question = entry["content"]
            elif entry["role"] == "assistant" and last_user_answer is None:
                last_user_answer = entry["content"]

            # Break once both question and answer are found
            if last_user_question is not None and last_user_answer is not None:
                break

        # Debugging: Print the retrieved values
        print("Last User Question:", last_user_question)
        print("Last User Answer:", last_user_answer)

        # Log the user feedback option
        log_activities(
            user_id=user_data.Pid,
            email=user_email,
            activity_type="Dislike Feedback",
            activity_content=feedback_message,
            response_content=None,
            app_name='sql',
            error_message=None
        )

        # Return response including the previous question, answer, and feedback
        return jsonify({
            "message": "Feedback recorded",
            "chosen_option": feedback_message,
            "previous_question": last_user_question,
            "previous_answer": last_user_answer
        }), 200

    except Exception as e:
        # Log the error activity instead of printing/logging the error
        log_activities(
            user_id=user_data.Pid if 'user_data' in locals() else None,
            email=user_email if 'user_email' in locals() else "Unknown",
            activity_type='error',
            app_name='dislike_feedback',
            error_message=str(e)
        )
        return jsonify({"error": "An error occurred while processing your request."}), 500

    
    
def submit_feedback1():
    try:
        # Authorization Header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header is missing."}), 401

        # Extract the token
        token = auth_header.split(" ")[1]
        try:
            decoded_token = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401

        # Get user information from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"error": "User email not found in token."}), 401

        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"error": "User data not found."}), 404

        # Get feedback data from request
        feedback_data = request.json
        is_liked = feedback_data.get('liked')

        if is_liked is None:
            return jsonify({"error": "Feedback (liked) is required."}), 400

        feedback_message = (
            "Thank you for your feedback! We're glad you liked it." if is_liked
            else "Thank you for your feedback! We'll try to improve."
        )

        # Log the user feedback
        log_activities(
            user_id=user_data.Pid,
            email=user_email,
            activity_type="Like Feedback" if is_liked else "Dislike Feedback",
            activity_content="User liked the response" if is_liked else "User disliked the response",
            response_content=None,
            app_name='sql',
            error_message=None
        )

        # Return response
        return jsonify({"message": feedback_message}), 200

    except Exception as e:
        # Log the error activity
        log_activities(
            user_id=user_data.Pid if 'user_data' in locals() else None,
            email=user_email if 'user_email' in locals() else "Unknown",
            activity_type='error',
            app_name='like_feedback',
            error_message=str(e)
        )
        return jsonify({"error": "An error occurred while processing your request."}), 500


if __name__ == "__main__":
    app.run()
