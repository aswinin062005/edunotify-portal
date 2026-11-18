import os
import time
import io
import random
import sqlite3
import pandas as pd
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from sms_templates import build_sms_message

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_college_key")
DB_NAME = "college.db"

# --- DATABASE SETUP ---
def init_db():
    """Initializes SQLite database tables with class_name separation."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Exam Records Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exam_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL DEFAULT '1st MCA',
                exam_type TEXT NOT NULL,
                student_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                failed_count INTEGER,
                failed_subjects TEXT,
                result_status TEXT,
                sms_status TEXT,
                sms_message TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Auto-migration: Add class_name column if upgrading an existing college.db
        cursor.execute("PRAGMA table_info(exam_records)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'class_name' not in columns:
            cursor.execute("ALTER TABLE exam_records ADD COLUMN class_name TEXT NOT NULL DEFAULT '1st MCA'")

        # Users Table for Permanent HOD/Faculty Authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Insert default HOD account if table is empty
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO users (username, email, phone, password)
                VALUES (?, ?, ?, ?)
            ''', ('hod_cs', 'hod@college.edu', '9876543210', 'password123'))
            
        conn.commit()

init_db()

# --- FAST2SMS API CONFIGURATION ---
FAST2SMS_API_KEY = os.environ.get(
    "FAST2SMS_API_KEY", 
    "nvZuVrdUo65JGhu9JUiSJqUnoj9Kkx2l5wQMHKG22jBfKfqWQHB4PC80C8zn"
).strip()

def send_real_sms(phone_number, message_text, lang_mode='unicode'):
    """Triggers a single SMS via Fast2SMS (supports Unicode for Tamil & Kannada)."""
    url = "https://www.fast2sms.com/dev/bulkV2"
    
    clean_phone = str(phone_number).replace(".0", "").strip()
    clean_phone = "".join(filter(str.isdigit, clean_phone))[-10:]
    
    if len(clean_phone) != 10:
        print(f"[-] Invalid phone number format: {phone_number} -> Cleaned: {clean_phone}")
        return False

    payload = {
        'authorization': FAST2SMS_API_KEY,
        'message': message_text,
        'language': lang_mode,  # 'unicode' renders English + Tamil + Kannada properly
        'route': 'q',
        'numbers': clean_phone
    }
    
    headers = {
        'authorization': FAST2SMS_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache'
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        result = response.json()
        print(f"[SMS API Response] To: {clean_phone} | Response: {result}")
        return result.get('return') == True
    except Exception as e:
        print(f"[-] Network/API Exception for {clean_phone}: {e}")
        return False


# ==========================================
# AUTHENTICATION & 2-STEP OTP ROUTES
# ==========================================

@app.route('/', methods=['GET'])
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    identifier = request.form.get('identifier', '').strip()
    password = request.form.get('password', '').strip()
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username FROM users 
            WHERE (username = ? OR email = ? OR phone = ?) AND password = ?
        ''', (identifier, identifier, identifier, password))
        row = cursor.fetchone()
        
    if row:
        session['user'] = row[0]
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid Username/Email/Phone or Password!")

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, phone, password)
                VALUES (?, ?, ?, ?)
            ''', (username, email, phone, password))
            conn.commit()
        return render_template('login.html', success="Account created successfully! Please Sign In.")
    except sqlite3.IntegrityError:
        return render_template('login.html', error="Username, email, or phone number already registered!")

@app.route('/send-otp', methods=['POST'])
def send_otp():
    phone = request.form.get('phone', '').strip()
    clean_phone = "".join(filter(str.isdigit, phone))[-10:]

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE phone = ?', (clean_phone,))
        user = cursor.fetchone()

    if not user:
        return render_template(
            'login.html',
            error="Phone number not registered in our records!",
            active_section='forgot-section'
        )

    otp = str(random.randint(100000, 999999))
    session['reset_otp'] = otp
    session['reset_phone'] = clean_phone

    otp_message = f"EduAlert Portal: Your OTP for password reset is {otp}. Do not share this with anyone."
    is_sent = send_real_sms(clean_phone, otp_message, lang_mode='english')

    if is_sent:
        return render_template(
            'login.html',
            success=f"OTP sent to ******{clean_phone[-4:]}. Please enter it below.",
            active_section='forgot-section',
            otp_sent=True
        )
    else:
        return render_template(
            'login.html',
            error="Failed to send SMS OTP. Check Fast2SMS balance or Quick API setting.",
            active_section='forgot-section'
        )

@app.route('/verify-reset-otp', methods=['POST'])
def verify_reset_otp():
    entered_otp = request.form.get('otp', '').strip()
    new_password = request.form.get('new_password', '').strip()

    saved_otp = session.get('reset_otp')
    saved_phone = session.get('reset_phone')

    if not saved_otp or not saved_phone:
        return render_template(
            'login.html',
            error="Session expired. Please request a new OTP.",
            active_section='forgot-section'
        )

    if entered_otp != saved_otp:
        return render_template(
            'login.html',
            error="Invalid OTP! Please check your SMS and try again.",
            active_section='forgot-section',
            otp_sent=True
        )

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE phone = ?', (new_password, saved_phone))
        conn.commit()

    session.pop('reset_otp', None)
    session.pop('reset_phone', None)

    return render_template(
        'login.html',
        success="Password verified and updated successfully! Please Sign In."
    )

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


# ==========================================
# DASHBOARD & SINGLE COMBINED 3-LANG SMS ROUTE
# ==========================================

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))

    selected_class = request.args.get('class_name', '1st MCA')
    selected_exam = request.args.get('exam_type', 'Unit 1 Test')
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT student_name, phone, failed_count, failed_subjects, result_status, sms_status, sms_message 
            FROM exam_records 
            WHERE class_name = ? AND exam_type = ?
        ''', (selected_class, selected_exam))
        rows = cursor.fetchall()

    total_students = len(rows)
    passed_students = sum(1 for r in rows if r[4] == 'Pass')
    failed_students = sum(1 for r in rows if r[4] == 'Fail')
    pass_percentage = round((passed_students / total_students * 100), 1) if total_students > 0 else 0

    return render_template(
        'dashboard.html',
        selected_class=selected_class,
        selected_exam=selected_exam,
        rows=rows,
        total_students=total_students,
        passed_students=passed_students,
        failed_students=failed_students,
        pass_percentage=pass_percentage,
        current_user=session['user']
    )

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user' not in session:
        return redirect(url_for('index'))

    class_name = request.form.get('class_name', '1st MCA')
    exam_type = request.form.get('exam_type')
    
    if 'file' not in request.files or not exam_type:
        flash("Please select a class, exam category, and attach an Excel file.", "danger")
        return redirect(url_for('dashboard', class_name=class_name))
        
    file = request.files['file']
    if file.filename == '':
        flash("No file selected.", "warning")
        return redirect(url_for('dashboard', class_name=class_name, exam_type=exam_type))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(file)
            df.columns = df.columns.astype(str).str.strip()
            
            column_mapping = {
                'Student Name': 'Name', 'Student': 'Name',
                'Parent Number': 'Phone', 'Contact': 'Phone', 'Mobile': 'Phone'
            }
            df.rename(columns=column_mapping, inplace=True)
            
            if 'Name' not in df.columns or 'Phone' not in df.columns:
                flash(f"Missing required columns! Found: {list(df.columns)}", "danger")
                return redirect(url_for('dashboard', class_name=class_name, exam_type=exam_type))

            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM exam_records WHERE class_name = ? AND exam_type = ?', (class_name, exam_type))

                non_subject_cols = ['Roll No', 'Roll Number', 'Name', 'Phone', 'Parent Number', 'Marks', 'Total', 'Average', 'Result']
                subject_cols = [col for col in df.columns if col not in non_subject_cols]

                fail_count_total = 0
                pass_count_total = 0

                for index, row in df.iterrows():
                    student = str(row['Name']).strip()
                    phone = str(row['Phone']).strip()
                    failed_subjects = []
                    all_marks_list = []

                    for subject in subject_cols:
                        try:
                            if pd.notna(row[subject]):
                                score_val = float(row[subject])
                                display_score = int(score_val) if score_val.is_integer() else round(score_val, 1)
                                all_marks_list.append(f"{subject}: {display_score}")

                                if score_val < 50:
                                    failed_subjects.append(subject)
                        except (ValueError, TypeError):
                            continue

                    failed_count = len(failed_subjects)
                    subjects_str = ", ".join(failed_subjects) if failed_subjects else "None"
                    all_marks_str = ", ".join(all_marks_list) if all_marks_list else "N/A"

                    context = {
                        'student_name': student,
                        'exam_type': exam_type,
                        'all_marks': all_marks_str,
                        'failed_subjects': subjects_str
                    }

                    result_status = "Pass" if failed_count == 0 else "Fail"
                    status_key = 'pass' if failed_count == 0 else 'fail'

                    # Build all 3 languages and merge into ONE single SMS
                    en_msg = build_sms_message('en', status_key, context)
                    ta_msg = build_sms_message('ta', status_key, context)
                    kn_msg = build_sms_message('kn', status_key, context)

                    single_combined_sms = f"{en_msg}\n\n{ta_msg}\n\n{kn_msg}"

                    # Send ONCE per student using Unicode mode
                    is_sent = send_real_sms(phone, single_combined_sms, lang_mode='unicode')
                    time.sleep(0.1)

                    sms_status = "Sent" if is_sent else "Failed"
                    combined_msg_log = f"[EN]: {en_msg} | [TA]: {ta_msg} | [KN]: {kn_msg}"

                    if result_status == "Pass":
                        pass_count_total += 1
                    else:
                        fail_count_total += 1

                    cursor.execute('''
                        INSERT INTO exam_records 
                        (class_name, exam_type, student_name, phone, failed_count, failed_subjects, result_status, sms_status, sms_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (class_name, exam_type, student, phone, failed_count, subjects_str, result_status, sms_status, combined_msg_log))

                conn.commit()

            flash(f"[{class_name}] Successfully processed {exam_type}! Sent 1 combined 3-language SMS each for {fail_count_total} failed and {pass_count_total} passed student(s).", "success")

        except Exception as e:
            flash(f"Error processing Excel file: {str(e)}", "danger")

        return redirect(url_for('dashboard', class_name=class_name, exam_type=exam_type))

    flash("Invalid file format. Please upload an Excel (.xlsx or .xls) file.", "danger")
    return redirect(url_for('dashboard', class_name=class_name))


@app.route('/export')
def export_excel():
    if 'user' not in session:
        return redirect(url_for('index'))

    selected_class = request.args.get('class_name', '1st MCA')
    selected_exam = request.args.get('exam_type', 'Unit 1 Test')

    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(
            'SELECT * FROM exam_records WHERE class_name = ? AND exam_type = ?', 
            conn, 
            params=(selected_class, selected_exam)
        )

    if df.empty:
        flash(f"No records found to export for {selected_class} - {selected_exam}.", "warning")
        return redirect(url_for('dashboard', class_name=selected_class, exam_type=selected_exam))

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        sheet_title = f"{selected_class}_{selected_exam}"[:30]
        df.to_excel(writer, sheet_name=sheet_title, index=False)

    output.seek(0)
    filename = f'{selected_class.replace(" ", "_")}_{selected_exam.replace(" ", "_")}_Audit_Log.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)