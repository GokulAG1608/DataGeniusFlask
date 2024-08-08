import logging
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from userdb import db, UserInfo, UserActivities, generate_token, log_activities, signin, register, forgot_password
import logging
from flask import Flask, request, render_template, jsonify, session, send_from_directory
import pandas as pd
import os
import uuid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import tiktoken
from langchain.agents import AgentType
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_community.chat_models import ChatOpenAI
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt
import bcrypt
import datetime

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

# @app.route('/user/signin', methods=['POST'])
# def user_signin():
#     data = request.json
#     return jsonify(*signin(data, app.config['SECRET_KEY']))

# @app.route('/user/register', methods=['POST'])
# def user_register():
#     data = request.json
#     return jsonify(*register(data))

# @app.route('/user/forgot', methods=['POST'])
# def user_forgot_password():
#     data = request.json
#     return jsonify(*forgot_password(data))

# @app.route('/user/auth', methods=['GET'])
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

# Configure logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
                    handlers=[logging.FileHandler("app.log"),
                              logging.StreamHandler()])

logger = logging.getLogger(__name__)


# Create folders if they don't exist
BASE_UPLOAD_FOLDER = 'uploads'
TEMP_PLOT_FOLDER = 'temp_plots'

if not os.path.exists(BASE_UPLOAD_FOLDER):
    os.makedirs(BASE_UPLOAD_FOLDER)
if not os.path.exists(TEMP_PLOT_FOLDER):
    os.makedirs(TEMP_PLOT_FOLDER)

# Store file paths in session
file_or_folder_paths = []

def get_user_upload_folder():
    user_id = session.get('user_id')
    if user_id is None:
        raise ValueError("User ID not found in session.")
    
    user_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, str(user_id))
    if not os.path.exists(user_upload_folder):
        os.makedirs(user_upload_folder)
    
    return user_upload_folder

# Function to load data from files or folders
def load_data(file_or_folder_paths):
    dataframes = []
    for path in file_or_folder_paths:
        if os.path.isdir(path):
            for file_name in os.listdir(path):
                file_path = os.path.join(path, file_name)
                if os.path.isfile(file_path):
                    try:
                        dataframes.extend(load_data_from_file(file_path))
                    except Exception as e:
                        logger.error(f"Error loading file '{file_path}': {str(e)}")
        elif os.path.isfile(path):
            try:
                dataframes.extend(load_data_from_file(path))
            except Exception as e:
                logger.error(f"Error loading file '{path}': {str(e)}")
        else:
            logger.warning(f"Invalid path: '{path}'. Skipping...")
    return dataframes

# Function to load data from a single file
def load_data_from_file(file_path):
    dataframes = []
    file_name = os.path.basename(file_path)
    if file_name.endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
            dataframes.append(df)
        except Exception as e:
            logger.error(f"Error reading CSV file '{file_name}': {str(e)}")
    elif file_name.endswith('.xlsx'):
        try:
            dataframes.extend(load_data_from_excel(file_path))
        except Exception as e:
            logger.error(f"Error reading Excel file '{file_name}': {str(e)}")
    else:
        logger.warning(f"Unsupported file format: '{file_name}'. Skipping...")
    return dataframes

def load_data_from_excel(file_path):
    dataframes = []
    file_name = os.path.basename(file_path)
    
    try:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                dataframes.append(df)
            except Exception as e:
                logger.error(f"Error reading sheet '{sheet_name}' from Excel file '{file_name}': {str(e)}")
    except Exception as e:
        logger.error(f"Error opening Excel file '{file_name}': {str(e)}")
        return dataframes  # Return the list of dataframes on error

    if not dataframes:
        return dataframes  # Return the empty list if no data was loaded

    # Check if all DataFrames have the same columns
    first_df_columns = dataframes[0].columns
    if all(df.columns.equals(first_df_columns) for df in dataframes):
        # Concatenate all DataFrames into one
        combined_df = pd.concat(dataframes, ignore_index=True)
        # Append the concatenated DataFrame to the list
        dataframes.append(combined_df)
        print(dataframes)
    return dataframes 

# Function to generate a summary of dataframes
def get_dataframes_summary(dataframes_list):
    return "\n".join([df.head().to_string() for df in dataframes_list])

# Load initial data when the app starts
dataframes_list = load_data(file_or_folder_paths)
dataframes_summary = get_dataframes_summary(dataframes_list)

PROMPT_TEMPLATE = f"""
        You are a data interaction tool. User will upload single or multiple csv or excel files. 
        You have to create python code to retreive the response and give in natural language as per user question.
        The respons should be crisp and clear and most accurate to the data.
        If the user asks for a plot, generate it using the same process as above. 
        
        If the user question is not relevant to the connected data give response as, "Sorry, I cannot answer this question since it is not relevant to the connected file.
    
"""

# Template for generating feedback on responses
FEEDBACK_PROMPT_TEMPLATE = """
You are an AI agent for reinforcement learning with human feedback, tasked with improving the previous response when a button is clicked.

The previous answer was: "{previous_answer}"

If the dislike button is clicked, rephrase the generated output for that particular question in a better way, maintaining context and correctness.

Rephrased Answer:
"""

# Define prompts for OpenAI models
PROMPT = PromptTemplate(input_variables=["context", "question"], template=PROMPT_TEMPLATE)

FEEDBACK_PROMPT = PromptTemplate(input_variables=["previous_answer"], template=FEEDBACK_PROMPT_TEMPLATE)

# Initialize OpenAI models and agents
def initialize_smart_datalake(dataframes, prompt_template):
    llm = ChatOpenAI(
        temperature=0, model="gpt-3.5-turbo", openai_api_key="sk-proj-KHzaTujZGduAhDVL2GyfT3BlbkFJeLWhvD8web0AbEnkxcJc"
    )
    pandas_df_agent = create_pandas_dataframe_agent(
        llm,
        df=dataframes[0],  # Assuming dataframes[0] as the primary dataframe for simplicity
        verbose=True,
        prompt=prompt_template,
        agent_executor_kwargs={"handle_parsing_errors": True},
        agent_type="zero-shot-react-description",
        return_intermediate_steps=True,
        allow_dangerous_code=True
    )
    return pandas_df_agent

def initialize_feedback(dataframes, feedback_prompt):
    llm = ChatOpenAI(
        temperature=0, model="gpt-3.5-turbo", openai_api_key="sk-proj-KHzaTujZGduAhDVL2GyfT3BlbkFJeLWhvD8web0AbEnkxcJc"
    )
    feedback_agent = create_pandas_dataframe_agent(
        llm,
        df=dataframes[0],  # Assuming dataframes[0] as the primary dataframe for simplicity
        verbose=True,
        prompt=feedback_prompt,
        agent_type=AgentType.OPENAI_FUNCTIONS,
        agent_executor_kwargs={"handle_parsing_errors": True},
        return_intermediate_steps=True,
        allow_dangerous_code=True
    )
    return feedback_agent

# Function to initialize OpenAI for generating suggestions
def initialize_suggestion(dataframes):
    llm = OpenAI(model_name="gpt-3.5-turbo-instruct", n=2, best_of=2, openai_api_key="sk-proj-KHzaTujZGduAhDVL2GyfT3BlbkFJeLWhvD8web0AbEnkxcJc")
    return llm

# Function to save generated plots
def save_plot(plt, filename):
    plot_path = os.path.join(TEMP_PLOT_FOLDER, filename)
    plt.savefig(plot_path)
    plt.close()
    return plot_path
def count_tokens(text, model='gpt-3.5-turbo'):
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    return len(tokens)

def chain(pandas_df_agent, query):
    try:
        answer = pandas_df_agent.invoke(query)
        if answer:
            output_text = answer.get('output', '')
            plot_path = None
            
            prompt_tokens = count_tokens(query)
            completion_tokens = count_tokens(output_text)
            total_tokens = prompt_tokens + completion_tokens
            
            cost_per_token = 0.02 / 1000  # Example cost per token, replace with actual
            cost= total_tokens * cost_per_token
            
            if 'plot' in output_text:
                filename = f"plot_{uuid.uuid4().hex}.png"
                plot_path = save_plot(plt, filename)
            
            return output_text, plot_path, prompt_tokens, completion_tokens, cost
        else:
            return '', None, 0, 0, 0.0
    except Exception as e:
        logger.error(f"Error invoking OpenAI agent: {str(e)}")
        return '', None, 0, 0, 0.0
       
# Route to load files or folders
def load_files():
    data = request.get_json()
    folder_paths = data.get('path', '')
    if folder_paths:
        session['file_or_folder_paths'] = folder_paths.split(',')
        files = []
        for path in session['file_or_folder_paths']:
            if os.path.isdir(path):
                files.extend(os.listdir(path))
            elif os.path.isfile(path):
                files.append(os.path.basename(path))
        return jsonify(success=True, files=files)
    else:
        return jsonify(success=False)

def upload_files():
    if 'user_id' not in session:
        return jsonify(success=False, message="User not authenticated."), 401

    if 'files' not in request.files:
        return jsonify(success=False, message="No files part in the request.")
    
    files = request.files.getlist('files')
    user_upload_folder = get_user_upload_folder()
    session['file_or_folder_paths'] = []
    
    for file in files:
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):    
            file_path = os.path.join(user_upload_folder, file.filename)
            try:
                file.save(file_path)
                session['file_or_folder_paths'].append(file_path)
                # Log the uploaded file activity
                log_activities(
                    user_id=session.get('user_id'),
                    email=session.get('user_email', 'unknown'),
                    activity_type="File Upload",
                    activity_content=f"Uploaded file: {file.filename}",
                    response_content=None,
                    error_message=None,
                    app_name="csv"
                )
            except Exception as e:
                logger.error(f"Error saving file '{file_path}': {str(e)}")
    
    logger.info(f"Uploaded files: {[os.path.basename(path) for path in session['file_or_folder_paths']]}")
    return jsonify(success=True, files=[os.path.basename(path) for path in session['file_or_folder_paths']])

def ask_questions():
    user_email = None  # Initialize user_email for error logging
    try:
        if request.content_type != 'application/json':
            return jsonify(success=False, message="Content-Type must be application/json"), 415

        data = request.get_json()
        query = data.get('question', '')

        if not query:
            return jsonify(success=False, message="No question provided."), 400

        if 'file_or_folder_paths' not in session:
            return jsonify(success=False, message="Please upload files or folders first."), 400

        # Log the user's question
        logger.info(f"User question: {query}")

        # Fetch user email from the session or token
        auth_header = request.headers.get('Authorization')
        if auth_header:
            token = auth_header.split(" ")[1]
            logger.info(f"Authorization header: {auth_header}")
            logger.info(f"Token extracted: {token}")
            try:
                decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                user_email = decoded_token.get('email')
                logger.info(f"Decoded token: {decoded_token}")
            except jwt.ExpiredSignatureError:
                logger.error("Token expired")
                return jsonify(success=False, message="Token expired"), 401
            except jwt.InvalidTokenError:
                logger.error("Invalid token")
                return jsonify(success=False, message="Invalid token"), 401

        # Load data and initialize smart data lake
        dataframes_list = load_data(session['file_or_folder_paths'])
        if not dataframes_list:
            logger.error("No data loaded from the provided paths")
            return jsonify(success=False, message="Failed to load data from provided files or folders."), 500

        smart_df = initialize_smart_datalake(dataframes_list, PROMPT_TEMPLATE)
        logger.info("Smart data lake initialized")

        # Generate the answer and plot
        answer, plot_path, prompt_tokens, completion_tokens, total_cost = chain(smart_df, query)
        logger.info(f"Generated answer: {answer}")

        if not answer:
            logger.error("No answer generated by the AI agent")
            return jsonify(success=False, message="Failed to generate an answer."), 500

        # Log user activity in the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if user_data:
            log_activities(
                user_id=user_data.Pid,
                email=user_email,
                app_name='csv',
                activity_type='question',
                activity_content=query,
                response_content=answer,
                total_cost=total_cost,
                successful_requests=1,
                completion_tokens=completion_tokens,
                prompt_tokens=prompt_tokens
            )

        # Prepare the response
        response = {"success": True, "answer": answer}
        if plot_path:
            response["plot_url"] = f"/temp_plots/{os.path.basename(plot_path)}"

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in ask_question route: {e}", exc_info=True)
        log_activities(
            user_id=None,
            email=user_email,
            activity_type='error',
            app_name='csv',
            activity_content='ask_question',
            response_content='Error occurred',
            error_message=str(e)
        )  # Log error
        return jsonify(success=False, message="An error occurred while processing")


# Route to handle feedback on answers
def feedback():
    data = request.get_json()
    query = data.get('question', '')
    feedback_type = data.get('feedback_type', '')
    chosen_option = data.get('option', '')  # Get the selected option from the request
 
    options = {
        "1": "The response was inaccurate.",
        "2": "The response was unclear.",
        "3": "The response was too long.",
        "4": "The response was irrelevant."
    }
 
    if query and feedback_type == 'dislike':
        if chosen_option not in options:
            return jsonify(success=False, message="Invalid option selected."), 400
 
        feedback_message = options[chosen_option]
 
        # Log the user feedback option
        log_activities(
            user_id=session.get('user_id'),
            email=session.get('user_email'),
            activity_type="Dislike Feedback",
            activity_content=feedback_message,
            response_content=None,
            app_name='csv',
            error_message=None
        )
 
        logger.info(f"User feedback (dislike) for question: {query}")
        logger.info(f"Feedback message: {feedback_message}")
 
        return jsonify(success=True, message="Feedback recorded", chosen_option=feedback_message)
    elif feedback_type == 'like':
        logger.info(f"User feedback (like) for question: {query}")
        return jsonify(success=True, answer="Thank you for your feedback!")
    else:
        return jsonify(success=False, message="Invalid feedback request.")
 




def smart_suggestion():
    user_email = None  # Initialize user_email for logging
    try:
        dataframes_list = load_data(session.get('file_or_folder_paths', []))
        llm = initialize_suggestion(dataframes_list)
        dataframes_summary = get_dataframes_summary(dataframes_list)
        
        prompt = f'''Here are the first few rows of each dataframe:\n{dataframes_summary}\n
        You are an AI tasked with suggesting questions based on the uploaded data. Generate the top 5 relevant questions for data analysis and plots.'''
        
        prompt_tokens = count_tokens(prompt)
        
        try:
            result = llm.invoke(prompt)
            logger.info(f"Generated suggestions: {result}")  # Log the generated suggestions
            
            completion_tokens = count_tokens(result)
            total_tokens = prompt_tokens + completion_tokens
            cost_per_token = 0.02 / 1000  # Example cost per token, replace with actual
            cost = total_tokens * cost_per_token

            # Fetch user email from the session or token
            auth_header = request.headers.get('Authorization')
            if auth_header:
                token = auth_header.split(" ")[1]
                logger.info(f"Authorization header: {auth_header}")
                logger.info(f"Token extracted: {token}")
                try:
                    decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                    user_email = decoded_token.get('email')
                    logger.info(f"Decoded token: {decoded_token}")
                except jwt.ExpiredSignatureError:
                    logger.error("Token expired")
                    return jsonify(success=False, message="Token expired"), 401
                except jwt.InvalidTokenError:
                    logger.error("Invalid token")
                    return jsonify(success=False, message="Invalid token"), 401

            # Log user activity in the database
            user_data = UserInfo.query.filter_by(Email=user_email).first()
            if user_data:
                log_activities(
                    user_id=user_data.Pid,
                    email=user_email,
                    app_name='csv',
                    activity_type='smart_suggestion',
                    activity_content="top question generated successfully",
                    response_content=result,
                    total_cost=cost,
                    successful_requests=1,
                    completion_tokens=completion_tokens,
                    prompt_tokens=prompt_tokens
                )

            return jsonify(success=True, suggestions=result.split('\n'))
        except Exception as e:
            logger.error(f"Error generating suggestions: {str(e)}")  # Log any errors that occur
            log_activities(
                user_id=None,
                email=user_email,
                activity_type='error',
                app_name='csv',
                error_message=str(e)
            )  # Log error
            return jsonify(success=False, message="Error generating suggestions"), 500

    except Exception as e:
        logger.error(f"Error in smart_suggestion route: {str(e)}")
        log_activities(
            user_id=None,
            email=user_email,
            activity_type='error',
            app_name='csv',
            error_message=str(e)
        )  # Log error
        return jsonify(success=False, message="An error occurred while processing your request."), 500


# Placeholder route to refer session state
@app.route('/refer_session', methods=['POST'])
def refer_session():
    # Implement logic to save/share current session state
    # Example: Save important session data to a database or generate a shareable link
    return render_template('index.html')

# Route to serve temporary plots

def serve_plot(filename):
    return send_from_directory(TEMP_PLOT_FOLDER, filename)

# Error handling for 404 not found errors
@app.errorhandler(404)
def page_not_found(e):
    logger.error(f"Page not found: {request.url}")
    return jsonify(error="Page not found"), 404

# Error handling for 500 internal server errors
@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {str(e)}")
    return jsonify(error="Internal server error"), 500
    

# Start Flask application
if __name__ == '__main__':
    app.run()







