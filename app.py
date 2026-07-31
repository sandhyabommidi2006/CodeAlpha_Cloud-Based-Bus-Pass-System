from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import uuid
import os

app = Flask(__name__)
app.secret_key = "cloud_bus_pass_project"

DATABASE = "bus_pass.db"


# -------------------------------
# Database Connection
# -------------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------
# Create Tables
# -------------------------------
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Bus Pass Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bus_pass(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            pass_id TEXT UNIQUE,
            source TEXT,
            destination TEXT,
            distance INTEGER,
            amount INTEGER,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


# Create database automatically
create_tables()


# -------------------------------
# Home Page
# -------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -------------------------------
# Register
# -------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users(fullname, email, password)
                VALUES (?, ?, ?)
            """, (fullname, email, password))

            conn.commit()

            flash("Registration Successful! Please Login.", "success")
            return redirect("/login")

        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")

        finally:
            conn.close()

    return render_template("register.html")


# -------------------------------
# Login
# -------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email=? AND password=?
        """, (email, password))

        user = cursor.fetchone()

        conn.close()

        if user:

            session["user"] = email

            if email == "admin@gmail.com":
                return redirect("/admin")

            return redirect("/dashboard")

        else:
            flash("Invalid Email or Password", "danger")

    return render_template("login.html")


# -------------------------------
# Logout
# -------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect("/")


# -------------------------------
# User Dashboard
# -------------------------------
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM bus_pass WHERE user_email=?",
        (session["user"],)
    )

    buspass = cursor.fetchone()

    conn.close()

    return render_template(
        "dashboard.html",
        email=session["user"],
        buspass=buspass
    )


# -------------------------------
# Distance-Based Price Calculation
# -------------------------------
def calculate_price(distance):
    """
    Automatic pricing to prevent incorrect pricing.
    """

    if distance <= 5:
        return 50

    elif distance <= 10:
        return 100

    elif distance <= 20:
        return 150

    elif distance <= 40:
        return 250

    else:
        return 350


# -------------------------------
# Generate Unique Pass ID
# -------------------------------
def generate_pass_id():
    """
    Generates a unique pass ID.
    Example:
    PASS-9F7A4C2D
    """

    return "PASS-" + uuid.uuid4().hex[:8].upper()


# -------------------------------
# Check Login Helper
# -------------------------------
def login_required():

    if "user" not in session:
        return False

    return True


# -------------------------------
# Apply Bus Pass
# -------------------------------
@app.route("/apply_pass", methods=["GET", "POST"])
def apply_pass():

    if not login_required():
        flash("Please login first.", "warning")
        return redirect("/login")

    if request.method == "POST":

        source = request.form["source"].strip()
        destination = request.form["destination"].strip()

        try:
            distance = int(request.form["distance"])
        except ValueError:
            flash("Distance must be a valid number.", "danger")
            return redirect("/payment")

        if distance <= 0:
            flash("Distance should be greater than 0.", "danger")
            return redirect("/payment")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user already has an application
        cursor.execute(
            "SELECT * FROM bus_pass WHERE user_email=?",
            (session["user"],)
        )

        existing_pass = cursor.fetchone()

        if existing_pass:
            conn.close()
            flash("You have already applied for a bus pass.", "warning")
            return redirect("/dashboard")

        amount = calculate_price(distance)
        pass_id = generate_pass_id()

        cursor.execute("""
            INSERT INTO bus_pass
            (
                user_email,
                pass_id,
                source,
                destination,
                distance,
                amount,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user"],
            pass_id,
            source,
            destination,
            distance,
            amount,
            "Pending"
        ))

        conn.commit()
        conn.close()

        flash("Bus Pass Application Submitted Successfully!", "success")
        return redirect("/my_pass")

    return render_template("apply_pass.html")

# -------------------------------
# Payment
# -------------------------------
@app.route("/payment", methods=["GET", "POST"])
def payment():

    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM bus_pass
        WHERE user_email=?
    """, (session["user"],))

    buspass = cursor.fetchone()

    conn.close()

    if buspass is None:
        flash("Please apply for a bus pass first.", "warning")
        return redirect("/apply_pass")

    if request.method == "POST":

        flash("Payment Successful!", "success")
        return redirect("/my_pass")

    return render_template(
        "payment.html",
        buspass=buspass
    )

# -------------------------------
# My Bus Pass
# -------------------------------
@app.route("/my_pass")
def my_pass():

    if not login_required():
        flash("Please login first.", "warning")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM bus_pass
        WHERE user_email=?
    """, (session["user"],))

    buspass = cursor.fetchone()

    conn.close()

    if buspass is None:
        flash("You have not applied for a bus pass yet.", "warning")
        return redirect("/apply_pass")

    return render_template(
        "my_pass.html",
        buspass=buspass
    )


# -------------------------------
# Check Pass Status
# -------------------------------
@app.route("/pass_status")
def pass_status():

    if not login_required():
        flash("Please login first.", "warning")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM bus_pass
        WHERE user_email=?
    """, (session["user"],))

    result = cursor.fetchone()

    conn.close()

    if result:
        flash(f"Current Pass Status : {result['status']}", "info")
    else:
        flash("No application found.", "warning")

    return redirect("/my_pass")


# -------------------------------
# Delete Own Pass (Optional)
# -------------------------------
@app.route("/delete_pass")
def delete_pass():

    if not login_required():
        flash("Please login first.", "warning")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM bus_pass
        WHERE user_email=?
    """, (session["user"],))

    conn.commit()
    conn.close()

    flash("Bus Pass Deleted Successfully.", "success")
    return redirect("/dashboard")

# -------------------------------
# Admin Dashboard
# -------------------------------
@app.route("/admin")
def admin():

    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect("/login")

    if session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM bus_pass
        ORDER BY id DESC
    """)

    applications = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        applications=applications
    )


# -------------------------------
# Approve Bus Pass
# -------------------------------
@app.route("/approve/<int:pass_id>")
def approve(pass_id):

    if "user" not in session or session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bus_pass
        SET status='Approved'
        WHERE id=?
    """, (pass_id,))

    conn.commit()
    conn.close()

    flash("Bus Pass Approved Successfully!", "success")
    return redirect("/admin")


# -------------------------------
# Reject Bus Pass
# -------------------------------
@app.route("/reject/<int:pass_id>")
def reject(pass_id):

    if "user" not in session or session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bus_pass
        SET status='Rejected'
        WHERE id=?
    """, (pass_id,))

    conn.commit()
    conn.close()

    flash("Bus Pass Rejected.", "warning")
    return redirect("/admin")


# -------------------------------
# Delete Application
# -------------------------------
@app.route("/delete_application/<int:pass_id>")
def delete_application(pass_id):

    if "user" not in session or session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM bus_pass
        WHERE id=?
    """, (pass_id,))

    conn.commit()
    conn.close()

    flash("Application Deleted Successfully!", "success")
    return redirect("/admin")


# -------------------------------
# View All Registered Users
# -------------------------------
@app.route("/users")
def users():

    if "user" not in session or session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users
        ORDER BY id DESC
    """)

    users = cursor.fetchall()

    conn.close()

    return render_template(
        "users.html",
        users=users
    )


# -------------------------------
# Delete User
# -------------------------------
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):

    if "user" not in session or session["user"] != "admin@gmail.com":
        flash("Access Denied!", "danger")
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find user's email
    cursor.execute("""
        SELECT email
        FROM users
        WHERE id=?
    """, (user_id,))

    user = cursor.fetchone()

    if user:

        cursor.execute("""
            DELETE FROM bus_pass
            WHERE user_email=?
        """, (user["email"],))

        cursor.execute("""
            DELETE FROM users
            WHERE id=?
        """, (user_id,))

        conn.commit()

    conn.close()

    flash("User Deleted Successfully!", "success")
    return redirect("/users")


# -------------------------------
# Run Application
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)