from flask import Flask, jsonify, request
from functools import wraps
import datetime
import os
import logging
import jwt

app = Flask(__name__)

# ---------- Settings (read from environment variables, see .env) ----------
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-this-is-only-a-default-key")
ACCESS_MINUTES = int(os.environ.get("ACCESS_MINUTES", 2))
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", 10))
USERS = [[os.environ.get("API_USER", "maycem"),
          os.environ.get("API_PASSWORD", "pwd123")]]   # [username, password]

# ---------- Logging: errors are written to a file (error history) ----------
LOG_FILE = os.environ.get("LOG_FILE", "logs/app.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_format = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.ERROR)          # the file only keeps errors
file_handler.setFormatter(log_format)
console_handler = logging.StreamHandler()     # the console shows everything
console_handler.setFormatter(log_format)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])


# ---------- The two classes ----------
class Student:
    def __init__(self, id_s, fn, ln, dmj, level, id_r):
        self.id_s = id_s
        self.fn = fn
        self.ln = ln
        self.dmj = dmj        # [0,1] -> optional, can be None
        self.level = level
        self.id_r = id_r      # foreign key: the report this student writes

    def to_list(self):
        return [self.id_s, self.fn, self.ln, self.dmj, self.level, self.id_r]


class Report:
    # the only values allowed for the type attribute
    REPORT_TYPES = ["Mini Senior Project", "PhD Thesis", "Internship", "Master's Thesis"]

    def __init__(self, id_r, title, type, report_date):
        if type not in Report.REPORT_TYPES:
            raise ValueError("Invalid type. Allowed: " + ", ".join(Report.REPORT_TYPES))
        try:
            datetime.datetime.strptime(report_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("Invalid date. Use the format YYYY-MM-DD")
        self.id_r = id_r
        self.title = title
        self.type = type
        self.report_date = report_date

    def to_list(self):
        return [self.id_r, self.title, self.type, self.report_date]


# ---------- The two lists ----------
reports = [
    Report(1, "Sales Dashboard", "Mini Senior Project", "2026-05-20"),
    Report(2, "Network Monitoring", "Internship", "2026-08-30"),
    Report(3, "Credit Risk Models", "Master's Thesis", "2026-06-15"),
    Report(4, "Machine Learning for Finance", "PhD Thesis", "2026-09-01"),
]

students = [
    Student(1, "Maycem", "Azaza", "Computer Science", "Senior", 1),
    Student(2, "Maryem", "Arfa", None, "Senior", 1),          # no dmj -> None
    Student(3, "Yassine", "Gharbi", "Networks", "Senior", 2),
    Student(4, "Ines", "Mansour", "Finance", "Master", 3),
    Student(5, "Karim", "Jlassi", None, "PhD", 4),
]

# Increment: the next id is the current counter, then +1
next_student_id = 6
next_report_id = 5


# ---------- Error handling ----------
def error(msg, code):
    logging.error("%s %s -> %s: %s", request.method, request.path, code, msg)  # console + log file
    return jsonify([msg]), code                    # and is sent to Postman


@app.errorhandler(404)
def url_not_found(e):
    return error("This URL does not exist", 404)


@app.errorhandler(405)
def method_not_allowed(e):
    return error("Wrong method for this URL (GET or POST?)", 405)


@app.errorhandler(500)
def server_error(e):
    logging.error("Server crashed: %r", getattr(e, "original_exception", e))
    return jsonify(["Internal server error"]), 500


def get_list(expected_length):
    """Checks the JSON body. Returns (data, None) or (None, error_response)."""
    data = request.get_json(silent=True)
    if data is None:
        return None, error("Body is missing or is not valid JSON", 400)
    if not isinstance(data, list):
        return None, error("JSON must be a list", 400)
    if len(data) != expected_length:
        return None, error("Wrong number of values: expected " + str(expected_length)
                           + ", received " + str(len(data)), 400)
    return data, None


def check_id(value):
    """The id in the URL must be a number. Returns (number, None) or (None, error_response)."""
    if not value.isdigit():
        return None, error("The id must be a number, but received '" + value + "'", 400)
    return int(value), None


def find_report(id_r):
    for r in reports:
        if r.id_r == id_r:
            return r
    return None


# ---------- Home ----------
@app.route("/", methods=["GET"])
def home():
    return jsonify(["The API is running"])


# ---------- Token ----------
def make_token(username, token_type, minutes):
    payload = {
        "sub": username,
        "type": token_type,                       # "access" or "refresh"
        "exp": datetime.datetime.now(datetime.timezone.utc)
               + datetime.timedelta(minutes=minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def check_token(expected_type):
    """Returns (payload, None) or (None, error_response)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, error("Token missing (use Authorization: Bearer <token>)", 401)
    token = header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, error("Token expired", 401)
    except jwt.InvalidTokenError:
        return None, error("Invalid token", 401)
    if payload.get("type") != expected_type:
        return None, error("Wrong token type: a " + expected_type + " token is required", 401)
    return payload, None


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload, err = check_token("access")
        if err:
            return err
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["POST"])
def login():
    data, err = get_list(2)                       # ["username", "password"]
    if err:
        return err
    if data not in USERS:
        return error("Wrong username or password", 401)
    return jsonify([make_token(data[0], "access", ACCESS_MINUTES),
                    make_token(data[0], "refresh", REFRESH_MINUTES)])


@app.route("/refresh", methods=["POST"])
def refresh():
    payload, err = check_token("refresh")         # send the REFRESH token here
    if err:
        return err
    return jsonify([make_token(payload["sub"], "access", ACCESS_MINUTES)])


# ---------- Reports: public (no token) ----------
@app.route("/reports", methods=["GET"])
def get_reports():
    result = []
    for r in reports:
        result.append(r.to_list())
    return jsonify(result)


@app.route("/reports/<id_r>", methods=["GET"])
def get_report(id_r):
    number, err = check_id(id_r)
    if err:
        return err
    report = find_report(number)
    if report is None:
        return error("Report " + str(number) + " not found", 404)
    return jsonify(report.to_list())


@app.route("/reports", methods=["POST"])
def add_report():
    global next_report_id
    data, err = get_list(3)                       # [title, type, report_date]
    if err:
        return err
    if not isinstance(data[0], str) or data[0].strip() == "":
        return error("The title must be a non-empty text", 400)
    try:
        report = Report(next_report_id, data[0], data[1], data[2])
    except ValueError as e:                       # raised by the Report class
        return error(str(e), 400)
    reports.append(report)
    next_report_id += 1
    return jsonify(report.to_list()), 201


# ---------- Students: GET needs a token (sensitive data) ----------
@app.route("/students", methods=["GET"])
@token_required
def get_students():
    result = []
    for s in students:
        result.append(s.to_list())
    return jsonify(result)


@app.route("/students/<id_s>", methods=["GET"])
@token_required
def get_student(id_s):
    number, err = check_id(id_s)
    if err:
        return err
    for s in students:
        if s.id_s == number:
            return jsonify(s.to_list())
    return error("Student " + str(number) + " not found", 404)


@app.route("/students", methods=["POST"])
def add_student():
    global next_student_id
    data, err = get_list(5)                       # [fn, ln, dmj, level, id_r]
    if err:
        return err
    fn, ln, dmj, level, id_r = data
    for value, name in ((fn, "fn"), (ln, "ln"), (level, "level")):
        if not isinstance(value, str) or value.strip() == "":
            return error("'" + name + "' must be a non-empty text", 400)
    if dmj == "":
        dmj = None                                # dmj is optional
    if not isinstance(id_r, int) or isinstance(id_r, bool):
        return error("id_r must be a number", 400)
    if find_report(id_r) is None:
        return error("Report " + str(id_r) + " does not exist", 404)
    count = 0
    for s in students:
        if s.id_r == id_r:
            count += 1
    if count >= 2:                                # a report has 1 to 2 students
        return error("Report " + str(id_r) + " already has 2 students", 400)
    student = Student(next_student_id, fn, ln, dmj, level, id_r)
    students.append(student)
    next_student_id += 1
    return jsonify(student.to_list()), 201


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),   # 0.0.0.0 is required inside Docker
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("DEBUG", "false").lower() == "true",
    )