import os
from flask import Flask, request, jsonify, render_template
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import ConfluenceLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
import google.generativeai as genai
from langchain_huggingface import HuggingFaceEmbeddings
import tiktoken
import random
from flask_cors import CORS
import jwt
from userdb import db,UserInfo,UserActivities,generate_token,log_activities,signin,register,forgot_password

load_dotenv()
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


#! CONFLUENCE
app.config['UPLOAD_FOLDER'] = 'upload'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

default_image_path = r"upload//TTH_Arc_1.jpeg"

# Environment variables
confluence_link = os.getenv("CONFLUENCE_LINK")
user_name = os.getenv("CONFLUENCE_USERNAME")
api_key = os.getenv("CONFLUENCE_API_KEY")
api_key2 = os.getenv("OPENAI_API_KEY")
space_key = os.getenv("CONFLUENCE_SPACE_KEY")

# Text splitter configuration
chunk_size = 600
chunk_overlap = 100
rec_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["."])

# Load documents from Confluence
loader = ConfluenceLoader(url=confluence_link, username=user_name, api_key=api_key)
documents = loader.load(space_key=space_key, max_pages=6, limit=7)
document = str(documents[1])
a = rec_splitter.create_documents([document])
texts = [doc.page_content for doc in a]

# Embeddings model
embeddings_model = HuggingFaceEmbeddings()

# Vision model
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# Document embeddings
document_embeddings = embeddings_model.embed_documents(texts)

# Creating FAISS vector store
db1 = FAISS.from_documents(a, embeddings_model)

answer_prompt = """
Query:

The user wants a concise and clear summary of the web-scraped content relevant to their question. They also need meaningful context added to their query. If the query is irrelevant or the data is not available, the user should be informed appropriately. The response should be based on the embedded vector in the FAISS vector database.Generate response within 3 to 4 lines.

Summary Response:

I understand you are looking for a summary that adds meaningful context to your query based on the web-scraped content and embedded vectors in the FAISS vector database. Here’s the response tailored to your needs:

1. Concise Summary:
   - Summarize the key points of the document in a clear and concise manner.
   - Ensure the summary is relevant to the user's query.
   - Provide a new perspective or additional details that were not included in previous summaries.

2. Meaningful Context:
   - Provide additional information that enhances the user's understanding of the topic.
   - Ensure the context is directly related to the query.
   - Add unique insights or examples to make this response different from previous ones.

3. Relevance Check:
   - If the query is irrelevant to the document or the database, inform the user.
   - If the information is not available, clearly state that the data is not available.

4. User Feedback:
   - Ask the user if the provided information is sufficient.
   - Encourage them to ask for further clarification if needed.

5. Confidence Score:
   - Provide a confidence score for the generated response from 10 to 100 based on the similarity between the output embedding and the closest embedding(s) from the training set. This similarity score can act as a confidence measure.

Example Response:

Based on your query about [specific topic], here is a summary of the relevant web-scraped content:

Document Summary:

The document discusses [main topic], highlighting [key points]. It provides detailed information about [specific aspects], including [important details]. 

Contextual Information:

Additionally, the content explains [related information] which helps to understand the [main topic] better. For instance, [specific example or data point] illustrates [particular aspect].

Please let me know if this summary addresses your query. If you need more details or further clarification, feel free to ask!

If the query is irrelevant or the data is not available:
Response:

I have been trained with a limited set of data and I am not aware of the requested query. Please provide more details or ask a different question.

User Feedback:
Is this information sufficient? If you need further details or have more questions, please let me know!

Query: {question}
Document Chunk: {context}
Answer: only respond to user query from this stored data only dont generate random content and i need the answer to get generate within 3 to 4 lines and If the user provides negative feedback (thumbs down) for an response generate new response for the request by ensuring the request id check once or twice the response id for user feedback submission if user have provided positive feedback for an requested question you just store it if user provides an negative feedback for an partcular response id generate a new response for the same question."""

negative_feedback_prompt = """
Query:

User Feedback Improvement Prompt:

Please generate a response using content exclusively from my FAISS vector database. Ensure the response is based solely on the indexed data. If uncertain, indicate, "This response is derived from the content stored in my FAISS vector database." Thank you

Summary Response:

I understand you are looking for a summary that adds meaningful context to your query based on the web-scraped content and embedded vectors in the FAISS vector database. Here’s the response tailored to your needs:

1. Concise Summary:
   - Summarize the key points of the document in a clear and concise manner.
   - Ensure the summary is relevant to the user's query.
   - Provide a new perspective or additional details that were not included in previous summaries.

2. Meaningful Context:
   - Provide additional information that enhances the user's understanding of the topic.
   - Ensure the context is directly related to the query.
   - Add unique insights or examples to make this response different from previous ones.

3. Relevance Check:
   - If the query is irrelevant to the document or the database, inform the user.
   - If the information is not available, clearly state that the data is not available.

4. User Feedback:
   - Ask the user if the provided information is sufficient.
   - Encourage them to ask for further clarification if needed.

5. Confidence Score:
   - Provide a confidence score for the generated response from 10 to 100 based on the similarity between the output embedding and the closest embedding(s) from the training set. This similarity score can act as a confidence measure.

Example Response:

Based on your query about [specific topic], here is a summary of the relevant web-scraped content:

Document Summary:

The document discusses [main topic], highlighting [key points]. It provides detailed information about [specific aspects], including [important details]. 

Contextual Information:

Additionally, the content explains [related information] which helps to understand the [main topic] better. For instance, [specific example or data point] illustrates [particular aspect].

Please let me know if this summary addresses your query. If you need more details or further clarification, feel free to ask!

If the query is irrelevant or the data is not available:
Response:

I have been trained with a limited set of data and I am not aware of the requested query. Please provide more details or ask a different question.

User Feedback:
Is this information sufficient? If you need further details or have more questions, please let me know!

Query: {question}
Document Chunk: {context}
Answer: only respond to user query from this stored data only dont generate random content and i need the answer to get generate within 3 to 4 lines and If the user provides negative feedback (thumbs down) for an response generate new response for the request by ensuring the request id check once or twice the response id for user feedback submission if user have provided positive feedback for an requested question you just store it if user provides an negative feedback for an partcular response id generate a new response for the same question."""

model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=api_key2)
prompt = PromptTemplate(template=answer_prompt, input_variables=["query", "context"])
negative_prompt = PromptTemplate(template = negative_feedback_prompt,input_variables=['query','context'])
qa_chain = RetrievalQA.from_llm(llm=model, retriever=db1.as_retriever(), prompt=prompt)
qa_chain_negative = RetrievalQA.from_llm(llm=model, retriever=db1.as_retriever(), prompt=negative_prompt)

# In-memory store for feedback counts 
feedback_store = {}

# In-memory store for generated responses
response_store = {}

def handle_query(query):

    # Generate a new response
    response = qa_chain.run({"query": query})

    # Compute the embedding of the generated response
    response_embedding = embeddings_model.embed_documents([response])


    # Calculate tokens
    COST_PER_1000_TOKENS = 0.002 

    enc = tiktoken.get_encoding("cl100k_base")
    global prompt_Tokens,question_tokens,response_tokens,total_tokens,total_Cost

    prompt_Tokens = len(enc.encode(answer_prompt))
    question_tokens = len(enc.encode(query))
    response_tokens = len(enc.encode(response))

    total_tokens = prompt_Tokens + question_tokens + response_tokens
    total_Cost = (total_tokens / 1000) * COST_PER_1000_TOKENS
    
    response_store[query] = {
        'response': response,
        'thumbs_up': 0,
        'thumbs_down': 0
    }

    return response

def generate_questions():
    # Generate suggestions based on Confluence content
    # loader = ConfluenceLoader(url=confluence_link, username=user_name, api_key=api_key)
    # documents = loader.load(space_key=space_key, max_pages=6, limit=7)
    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    # split_documents = text_splitter.split_documents(documents)
    
    # embeddings = OpenAIEmbeddings()
    # vector_store = FAISS.from_documents(split_documents, embeddings)
    
    # retriever = vector_store.as_retriever(search_kwargs={"k": 1})
    
    # # Create a QA chain with OpenAI and FAISS retriever
    # chain = RetrievalQA.from_chain_type(llm=model, chain_type="stuff", retriever=retriever)
    ques = "Generate  5 questions from Confluence content"
    
    response = qa_chain.run({"query": ques})
    

    # #Cost Finding
    COST_PER_1000_TOKENS = 0.002 

    enc = tiktoken.get_encoding("cl100k_base")

    global prompt_Tokens2,question_tokens2,response_tokens2,total_tokens2,total_Cost2

    prompt_Tokens2 = len(enc.encode(answer_prompt))
    question_tokens2 = len(enc.encode(ques))
    response_tokens2 = len(enc.encode(response))

    total_tokens2 = prompt_Tokens2 + question_tokens2 + response_tokens2
    total_Cost2 = (total_tokens2 / 1000) * COST_PER_1000_TOKENS
    
    return response


def chat1():
    user_email = None
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
            return jsonify({"status": "Failure","error": "Invalid token."}), 401
          # Extract user email from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"status": "Failure","error": "User email not found in token."}), 401

        # Fetch user data from the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"status": "Failure","error": "User data not found."}), 404

        # Get data from POST request
        
        data = request.json
        input = data.get('user_input')

        response_Content = handle_query(input)
        response_id = hash(input)

        # Log user activity including user input
        log_activities(user_data.Pid, user_email,app_name='confluence', activity_type='question', activity_content=input, response_content=response_Content,total_cost=total_Cost,successful_requests=1,completion_tokens=total_tokens,prompt_tokens=prompt_Tokens)

        return jsonify({"status": "Success", "response": response_Content, "id": response_id})

    except Exception as e:
        print(f"Error in chat route: {e}")
        log_activities(user_id=None,email=user_email, activity_type='error',app_name='confluence', error_message=str(e))  # Log error
        return jsonify({"status": "Failure","error": "An error occurred while processing your request."}), 500

def suggestion():
    user_email = None  # Initialize user_email to handle possible exceptions
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"status": "Failure","error": "Authorization header is missing."}), 401

        # Extract the token from the header
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({"status": "Failure","error": "Token is missing."}), 401

        # Decode the JWT token
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "Failure","error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"status": "Failure","error": "Invalid token."}), 401

        # Extract user email from the decoded token
        user_email = decoded_token.get('email')
        if not user_email:
            return jsonify({"status": "Failure","error": "User email not found in token."}), 401

        # Fetch user data from the database
        user_data = UserInfo.query.filter_by(Email=user_email).first()
        if not user_data:
            return jsonify({"status": "Failure","error": "User data not found."}), 404

        # Calling function to suggest question
        question = generate_questions()
    

        # #Log activities
        log_activities(user_data.Pid, user_email,app_name='confluence', activity_type='suggestion', activity_content="Generated the Questions from the Confluence Page", response_content=question,total_cost=total_Cost2,successful_requests=1,completion_tokens=total_tokens2,prompt_tokens=prompt_Tokens2)

        
        return jsonify({"status": "Success", "suggestions": question}), 200
    except Exception as e:
        print(f"Error in suggestion route: {e}")
        log_activities(
            user_id=None,
            email=user_email, 
            activity_type='error',
            app_name='confluence',
            error_message=str(e)
        )  # Log error
        return jsonify({"status": "Failure","error": "An error occurred while processing your request."}), 500


    
if __name__ == '__main__':
    app.run()
