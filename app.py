from pathlib import Path

from flask                 import Flask
from flask_cors            import CORS
from flask_session         import Session
from utils.database_util   import DatabaseManager
from utils.config_util     import ConfigManager as Config
from flask import redirect, url_for

from routes.auth import auth_bp
from routes.main_page import mainpage_bp
from routes.meal import meal_bp
from routes.schedule import schedule_bp
from routes.timetable import timetable_bp
from routes.post import post_bp

app = Flask(__name__)

# 프론트엔드와 세션 유지 가능하게 설정 (프론트엔드에서 꼭 withCredentials: true 확인!)
CORS(app, supports_credentials=True)
Config().read_file("config.json")
config_data = Config().get()


# Flask 세션 설정 추가
app.config['SECRET_KEY']         = config_data["Session"]["Key"]
app.config['SESSION_TYPE']       = config_data["Session"]["Type"]
app.config['SESSION_PERMANENT']  = config_data["Session"]["Permanent"]
app.config['SESSION_USE_SIGNER'] = config_data["Session"]["UseSigner"]
app.config['SESSION_KEY_PREFIX'] = config_data["Session"]["KeyPrefix"]

# 업로드 관련 설정
uploads_cfg = config_data.get("Uploads", {})
raw_upload_dir = uploads_cfg.get("PostImageFolder", "uploads/posts")
upload_dir_path = Path(raw_upload_dir)
if not upload_dir_path.is_absolute():
    upload_dir_path = Path(app.root_path) / upload_dir_path
upload_dir_path.mkdir(parents=True, exist_ok=True)
app.config['POST_IMAGE_UPLOAD_FOLDER'] = str(upload_dir_path)
allowed_exts = uploads_cfg.get("AllowedExtensions", ["jpg", "jpeg", "png", "gif", "webp"])
app.config['POST_IMAGE_ALLOWED_EXTENSIONS'] = {ext.lower() for ext in allowed_exts}
app.config['POST_IMAGE_MAX_BYTES'] = int(uploads_cfg.get("MaxImageSizeMB", 5) * 1024 * 1024)
max_request_mb = uploads_cfg.get("MaxRequestSizeMB", 20)
if max_request_mb:
    app.config['MAX_CONTENT_LENGTH'] = int(max_request_mb * 1024 * 1024)

Session(app)

# 데이터베이스 연결 초기화
DatabaseManager().connect(
    host     = config_data["Database"]["Host"],
    username = config_data["Database"]["Username"],
    password = config_data["Database"]["Password"],
)

app.register_blueprint(auth_bp)
app.register_blueprint(mainpage_bp)
app.register_blueprint(meal_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(timetable_bp)
app.register_blueprint(post_bp)

@app.route("/")
def home():
    return redirect(url_for('main.main_page'))

if __name__ == "__main__":
    try:
        app.run(debug=False)
    except Exception as e:
        print(e)
