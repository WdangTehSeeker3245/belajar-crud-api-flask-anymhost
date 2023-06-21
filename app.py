from flask import Flask
from flask_restful import Api, Resource, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
db = SQLAlchemy(app)
api = Api(app)
CORS(app)

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

# Request parser
parser = reqparse.RequestParser()
parser.add_argument('name', type=str, required=True, help='Name field is required')
parser.add_argument('price', type=int, required=True, help='Price field is required')

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

    def post(self):
        args = parser.parse_args()
        new_product = Product(name=args['name'], price=args['price'])
        db.session.add(new_product)
        db.session.commit()
        return {'message': 'Product created successfully'}, 201

    def put(self, product_id):
        product = Product.query.get(product_id)
        if product:
            args = parser.parse_args()
            product.name = args['name']
            product.price = args['price']
            db.session.commit()
            return {'message': 'Product updated successfully'}
        else:
            return {'error': 'Product not found'}, 404

    def delete(self, product_id):
        product = Product.query.get(product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            return {'message': 'Product deleted successfully'}
        else:
            return {'error': 'Product not found'}, 404

# API endpoints
api.add_resource(ProductResource, '/products', '/products/<int:product_id>')

if __name__ == '__main__':
    app.run(debug=True)
