from routes.auth import auth
from routes.home import home
from routes.dashboard import dashboard
from routes.orders import order
from routes.trips import trip
from routes.admin import admin
from routes.blogs import blogs

def init_routes(app):
    app.register_blueprint(home, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(dashboard, url_prefix='/')
    app.register_blueprint(order, url_prefix='/')
    app.register_blueprint(trip, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/')
    app.register_blueprint(blogs, url_prefix='/')