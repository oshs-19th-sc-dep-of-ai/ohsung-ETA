from flask import current_app, send_from_directory

from . import post_bp


@post_bp.route('/api/posts/images/<path:filename>', methods=['GET'])
def get_post_image(filename: str):
    upload_dir = current_app.config['POST_IMAGE_UPLOAD_FOLDER']
    return send_from_directory(upload_dir, filename)
