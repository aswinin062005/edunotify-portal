import sqlite3

DB_NAME = "college.db"

def init_database():
    """Initializes SQLite database tables for EduAlert."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # 1. Exam Records Table (Segmented by Class & Exam Type)
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

        # 2. Users Table (HOD & Faculty Login / OTP Recovery)
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
            print("[+] Default HOD user created (Username: hod_cs | Password: password123)")

        conn.commit()
        print("[+] Database `college.db` initialized successfully with `exam_records` and `users` tables.")

if __name__ == '__main__':
    init_database()