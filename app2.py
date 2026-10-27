from flask import Flask, request
import os
import logging

app = Flask(__name__)

# ---------- Logging: errors are written to a file (error history) ----------
LOG_FILE = os.environ.get("LOG_FILE", "logs/app2.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log_format = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.ERROR)          # the file only keeps errors
file_handler.setFormatter(log_format)
console_handler = logging.StreamHandler()     # the console shows everything
console_handler.setFormatter(log_format)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])


@app.after_request
def log_errors(response):
    # every response with an error status (404, 405, 500...) goes to the log
    if response.status_code >= 400:
        logging.error("%s %s -> %s", request.method, request.path, response.status_code)
    return response


students=[
    {
        "id": 1,
        "Fname": "Ali",
        "Lname": "Mastouri",
        "reports":[
            {
                "Title": "title1",
                "Type": "Mini senior project"
            }
        ]
    }
]

@app.get("/students") #return all students inside your list
def get_students():
    return {"students": students}

@app.post("/students") #add a new student to your list
def add_student():
    request_data = request.get_json()
    new_student = {
        "id": len(students) + 1,
        "Fname": request_data.get("Fname"),
        "Lname": request_data.get("Lname"),
        "reports": request_data.get("reports", [])
    }
    students.append(new_student)
    return {"message": "Student added successfully", "student": new_student}, 201

@app.post("/students/<int:student_id>/reports")
def add_report(student_id):
    request_data = request.get_json()
    student = next((s for s in students if s["id"] == student_id), None)
    if student is None:
        return {"message": " Student not found"}, 404

    new_report = {
        "Title": request_data.get("Title"),
        "Type": request_data.get("Type")
    }
    student["reports"].append(new_report)
    return {"message": "Report added successfully", "report": new_report}, 201

@app.get("/students/<int:student_id>")  # return a specific student
def get_student(student_id):
    for student in students:
        if student["id"] == student_id:
            return {"student": student}

    return {"message": "Student not found"}, 404

@app.get("/students/<int:student_id>/report")
def get_student_reports(student_id):
    student = next((s for s in students if s["id"] == student_id), None)
    if student is None:
        return {"message": "Student not found"}, 404
    return {"reports": student["reports"]}






if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),   # 0.0.0.0 is required inside Docker
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("DEBUG", "false").lower() == "true",
    )
