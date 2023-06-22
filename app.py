from flask import Flask,jsonify,make_response,request
from flask_restful import Api, Resource, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import jwt
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

app = Flask(__name__)
db = SQLAlchemy()
api = Api(app)
CORS(app)
load_dotenv()
bcrypt = Bcrypt(app)

# Secret Key
secret_key = os.getenv('SECRET_KEY')
app.config['SECRET_KEY'] = f'{secret_key}'
app.config['JWT_EXPIRATION_DELTA'] = timedelta(minutes=30)

# Sqlite
# db_name = os.getenv('DB_NAME')
# app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_name}.db'

# Mysql
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    db.session.rollback()
    return {'message': 'A database error occurred.'}, 500

# Protect the API with JWT
def jwt_token_required(func):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return {'message': 'Token is missing'}, 401

        token = token.split()[1]

        # Check if the token is in the blacklist
        if RevokedToken.query.filter_by(token=token).first():
            return {'message': 'Token Revoked'}, 401

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            username = payload['username']
            kwargs['username'] = username
        except jwt.ExpiredSignatureError:
            return {'message': 'Token has expired'}, 401
        except jwt.InvalidTokenError:
            return {'message': 'Invalid token'}, 401

        return func(*args, **kwargs)

    return wrapper


# Revoked Token
class RevokedToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False)

    def __init__(self, name, price):
        self.name = name
        self.price = price

# Create Database
with app.app_context():
    db.create_all()



# Resource Handling Auth
class RegisterResource(Resource):
    def post(self):
        # Request parser
        parser = reqparse.RequestParser()

        # Auth
        parser.add_argument('username', type=str, required=True, help='Username is required.')
        parser.add_argument('password', type=str, required=True, help='Password is required.')

        data = parser.parse_args()
        username = data['username']
        password = data['password']

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return {'message': 'Username already exists'}, 400

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Create a new user
        user = User(username=username, password=hashed_password)
        db.session.add(user)

        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            return {'message': 'An error occurred while registering the user.'}, 500

        return {'message': 'User registered successfully'}, 201

class LoginResource(Resource):
    def post(self):
        # Request parser
        parser = reqparse.RequestParser()

        # Auth
        parser.add_argument('username', type=str, required=True, help='Username is required.')
        parser.add_argument('password', type=str, required=True, help='Password is required.')
      
        data = parser.parse_args()
        username = data['username']
        password = data['password']

        user = User.query.filter_by(username=username).first()
        user_id = user.id
        try:
            if RevokedToken.query.filter_by(user_id=user_id).first():
                RevokedToken.query.filter_by(user_id=user_id).delete()
                db.session.commit()

            if not username or not password:
                return make_response(jsonify({'message': 'Username and password are required'}), 400)

            user = User.query.filter_by(username=username).first()
            if not user or not bcrypt.check_password_hash(user.password, password):
                return make_response(jsonify({'message': 'Invalid username or password'}), 401)

            token = jwt.encode({'username': username}, app.config['SECRET_KEY'], algorithm='HS256')
            
            return make_response(jsonify({'access_token': token}), 200)
        except SQLAlchemyError as e:
            return {'message': 'An error occurred while processing the login request.'}, 500


class LogoutResource(Resource):
    @jwt_token_required
    def post(self,username):
        token = request.headers.get('Authorization').split()[1]
        data = User.query.filter_by(username=username).first()
        
        # Add the token to the blacklist
        revoked_token = RevokedToken(token=token,user_id=data.id)
        db.session.add(revoked_token)
        db.session.commit()

        return {'message': 'User logged out successfully'}, 200

# Resource for handling product operations
class ProductResource(Resource):
    def get(self, product_id=None):
        if product_id:
            product = Product.query.get(product_id)
            if product:
                return {'id': product.id, 'name': product.name, 'price': product.price}
            else:
                return {'error': 'Product not found'}, 404
        else:
            products = Product.query.all()
            result = []
            for product in products:
                result.append({'id': product.id, 'name': product.name, 'price': product.price})
            return result

    @jwt_token_required
    def post(self,username):
        # Request parser
        parser = reqparse.RequestParser()

        # Produt
        parser.add_argument('name', type=str, required=True, help='Name field is required')
        parser.add_argument('price', type=int, required=True, help='Price field is required')

        data = parser.parse_args()
        new_product = Product(name=data['name'], price=data['price'])
        db.session.add(new_product)
        db.session.commit()
        return {'message': 'Product created successfully'}, 201
    
    @jwt_token_required
    def put(self, product_id, username):
        # Request parser
        parser = reqparse.RequestParser()

        # Produt
        parser.add_argument('name', type=str, required=True, help='Name field is required')
        parser.add_argument('price', type=int, required=True, help='Price field is required')

        product = Product.query.get(product_id)
        if product:
            data = parser.parse_args()
            product.name = data['name']
            product.price = data['price']
            db.session.commit()
            return {'message': 'Product updated successfully'}
        else:
            return {'error': 'Product not found'}, 404

    @jwt_token_required
    def delete(self, product_id, username):
        product = Product.query.get(product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            return {'message': 'Product deleted successfully'}
        else:
            return {'error': 'Product not found'}, 404

# Protected resource
class ProtectedResource(Resource):
    @jwt_token_required
    def get(self, username):
        return {'message': f'Protected resource for user: {username}'}, 200


# API endpoints
api.add_resource(RegisterResource, '/register')
api.add_resource(LoginResource, '/login')
api.add_resource(LogoutResource, '/logout')
api.add_resource(ProductResource, '/products', '/products/<int:product_id>')
api.add_resource(ProtectedResource, '/protected')

if __name__ == '__main__':
    app.run(debug=True)
