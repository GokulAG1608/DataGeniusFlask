import tiktoken
import random
import jwt
from flask import Flask,request,jsonify
from flask_cors import CORS
from userdb import *

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = 'tucEDtE44BbQLv7tXCivZkn1DbmKGsYn'

def feedback():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"status": "Failure","error": "Authorization header is missing."}), 401

        # Extract the token from the header
        token = auth_header.split(" ")[1]
          # Decode the JWT token
       
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "Failure","error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401
          # Extract user email from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"status": "Failure","error": "User email not found in token."}), 401

        # Fetch user data from the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"status": "Failure","error": "User data not found."}), 404

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
    
        if query and feedback_type == 'thumbsdown':
            if chosen_option not in options:
                return jsonify({"status":"Failure", "error":"Invalid option selected."}), 400
            
            feedback_message = options[chosen_option]
           
            # Calculate tokens
            COST_PER_1000_TOKENS = 0.002 

            enc = tiktoken.get_encoding("cl100k_base")
            # global prompt_Tokens,question_tokens,response_tokens,total_tokens,total_Cost

            prompt_Tokens = len(enc.encode(query))
            question_tokens = len(enc.encode(query))
            response_tokens = len(enc.encode(feedback_message))

            total_tokens = prompt_Tokens + question_tokens + response_tokens
            total_Cost = (total_tokens / 1000) * COST_PER_1000_TOKENS
    
            # Log the user feedback option
            log_activities(user_data.Pid, user_email,app_name='app', activity_type="feedback", activity_content=feedback_type, response_content=query,total_cost=total_Cost,successful_requests=1,completion_tokens=total_tokens,prompt_tokens=prompt_Tokens)

            return jsonify({"status":"Success", "message":"Feedback recorded", "chosen_option":feedback_message})
        elif feedback_type == 'thumbsup':
            # Calculate tokens
            COST_PER_1000_TOKENS = 0.002 

            enc = tiktoken.get_encoding("cl100k_base")
            # global prompt_Tokens,question_tokens,response_tokens,total_tokens,total_Cost

            prompt_Tokens = len(enc.encode(query))
            question_tokens = len(enc.encode(query))
            response_tokens = len(enc.encode(feedback_type))
           
            total_tokens = prompt_Tokens + question_tokens + response_tokens
            total_Cost = (total_tokens / 1000) * COST_PER_1000_TOKENS
            
            log_activities(user_data.Pid, user_email,app_name='app', activity_type="feedback", activity_content=feedback_type, response_content=query,total_cost=total_Cost,successful_requests=1,completion_tokens=total_tokens,prompt_tokens=prompt_Tokens)
            return jsonify({"status":"Success", "message":"Thank you for your feedback!"})
        else:
            log_activities(user_id=None,email=user_email, activity_type='error',app_name='app', error_message=str(e))  # Log error
           
            return jsonify({"status":"Failure", "error":"Invalid feedback request."})
    except Exception as e:
        print(f"Error in chat route: {e}")
        log_activities(user_id=None,email=user_email, activity_type='error',app_name='app', error_message=str(e))  # Log error
        return jsonify({"status": "Failure","error": "An error occurred while processing your request."}), 500
