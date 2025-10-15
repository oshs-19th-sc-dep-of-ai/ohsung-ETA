from flask import Blueprint

post_bp = Blueprint('post', __name__)

# Import route modules to register endpoints with the blueprint
from . import comment_routes  # noqa: E402,F401
from . import image_routes  # noqa: E402,F401
from . import post_routes  # noqa: E402,F401
from . import sub_comment_routes  # noqa: E402,F401
