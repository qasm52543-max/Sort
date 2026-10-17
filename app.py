import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape, Markup

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

CARD_NUMBER = "5892101486080860"
CARD_OWNER = "دهمیری"
SUPPORT_ID = "@iz_mahdi_rigan__16"
SUPPORT_URL = "https://rubika.ir/iz_mahdi_rigan__16"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-password")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "receipts")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PACKAGES = {
    "60": ("۶۰ یوسی", 256000),
    "325": ("۳۲۵ یوسی", 1285000),
    "660": ("۶۶۰ یوسی", 2574000),
    "1800": ("۱۸۰۰ یوسی", 6559000),
}

def connect_db():
    con = sqlite3.connect("mahdi_shop.db")
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect_db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            package TEXT NOT NULL,
            price INTEGER NOT NULL,
            player_id TEXT NOT NULL,
            player_name TEXT NOT NULL,
            receipt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'در انتظار بررسی',
            created_at TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()

init_db()

BASE = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>مهدی شاپ | خرید یوسی پابجی</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b0e14;color:#f2f4f8;font-family:Tahoma,Arial,sans-serif}
header{background:#141a24;padding:18px;text-align:center;border-bottom:2px solid #f5b82e}
header h1{color:#f5b82e;margin:5px}
nav{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:15px}
a{color:#f5b82e;text-decoration:none}
main{max-width:850px;margin:25px auto;padding:12px}
.card{background:#151c28;border:1px solid #30394a;border-radius:14px;padding:18px;margin-bottom:16px}
h2{color:#f5b82e}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.price{font-size:22px;color:#f5b82e;font-weight:bold}
button,.btn{display:inline-block;background:#f5b82e;color:#141414;border:0;border-radius:8px;padding:11px 16px;font-weight:bold;cursor:pointer;margin-top:10px}
input,select{width:100%;padding:12px;margin:8px 0 14px;background:#0b0e14;color:white;border:1px solid #465064;border-radius:8px}
label{display:block}
.notice{background:#282315;padding:13px;border-radius:8px;line-height:2;overflow-wrap:anywhere}
.small{color:#b9c0cd;font-size:13px;line-height:2}
table{width:100%;border-collapse:collapse}
td,th{padding:9px;border-bottom:1px solid #30394a;text-align:right}
img{max-width:160px;border-radius:8px}
footer{text-align:center;color:#9098a8;padding:25px}
</style>
</head>
<body>
<header>
<h1>مهدی شاپ</h1>
<p>فروش یوسی پابجی موبایل</p>
<nav>
<a href="/">صفحه اصلی</a>
{% if user %}
<a href="/orders">سفارش‌های من</a>
<a href="/logout">خروج</a>
{% else %}
<a href="/login">ورود</a>
<a href="/register">ثبت‌نام</a>
{% endif %}
<a href="{{ support_url }}">پشتیبانی روبیکا</a>
</nav>
</header>
<main>{{ content }}</main>
<footer>مهدی شاپ | فروش یوسی پابجی موبایل</footer>
</body>
</html>
"""

def page(html, **kwargs):
    user = session.get("username")
    inner = render_template_string(html, **kwargs)
    return render_template_string(
        BASE, content=Markup(inner), user=user, support_url=SUPPORT_URL
    )

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    html = """
    <div class="card">
      <h2>به مهدی شاپ خوش آمدید</h2>
      <p>بسته یوسی موردنظرت رو انتخاب کن.</p>
      <p class="small">برای ثبت سفارش، ابتدا وارد حساب کاربری شو یا ثبت‌نام کن.</p>
    </div>
    <div class="grid">
    {% for key, item in packages.items() %}
      <div class="card">
        <h2>{{ item[0] }}</h2>
        <p class="price">{{ "{:,}".format(item[1]) }} تومان</p>
        {% if user %}
        <a class="btn" href="/buy/{{ key }}">خرید این بسته</a>
        {% else %}
        <a class="btn" href="/login">ورود برای خرید</a>
        {% endif %}
      </div>
    {% endfor %}
    </div>
    <div class="card">
      <h2>اطلاعات پرداخت</h2>
      <div class="notice">
      شماره کارت: <b>{{ card }}</b><br>
      به نام: <b>{{ owner }}</b><br>
      پس از واریز، تصویر رسید را در فرم سفارش بارگذاری کن.
      </div>
      <p class="small">رسید باید حداکثر تا ۱۰ دقیقه پس از پرداخت ارسال شود. سفارش پس از بررسی مدیریت تأیید می‌شود.</p>
      <a class="btn" href="{{ support }}">ارتباط با پشتیبانی روبیکا</a>
    </div>
    """
    return page(
        html, packages=PACKAGES, card=CARD_NUMBER,
        owner=CARD_OWNER, support=SUPPORT_URL
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            error = "نام کاربری باید حداقل ۳ و رمز عبور حداقل ۶ حرف باشد."
        else:
            con = connect_db()
            try:
                con.execute(
                    "INSERT INTO users (username,password) VALUES (?,?)",
                    (username, generate_password_hash(password))
                )
                con.commit()
                row = con.execute(
                    "SELECT id FROM users WHERE username=?", (username,)
                ).fetchone()
                session["user_id"] = row["id"]
                session["username"] = username
                return redirect("/")
            except sqlite3.IntegrityError:
                error = "این نام کاربری قبلاً ثبت شده است."
            finally:
                con.close()
    return page("""
    <div class="card">
    <h2>ثبت‌نام</h2><p style="color:#ff7777">{{ error }}</p>
    <form method="post">
      <label>نام کاربری</label><input name="username" required minlength="3">
      <label>رمز عبور</label><input name="password" type="password" required minlength="6">
      <button>ساخت حساب</button>
    </form></div>
    """, error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        con = connect_db()
        row = con.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        con.close()
        if row and check_password_hash(row["password"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect("/")
        error = "نام کاربری یا رمز عبور اشتباه است."
    return page("""
    <div class="card">
    <h2>ورود به حساب</h2><p style="color:#ff7777">{{ error }}</p>
    <form method="post">
      <label>نام کاربری</label><input name="username" required>
      <label>رمز عبور</label><input name="password" type="password" required>
      <button>ورود</button>
    </form>
    <p><a href="/register">حساب نداری؟ ثبت‌نام کن</a></p>
    </div>
    """, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/buy/<package_id>", methods=["GET", "POST"])
@login_required
def buy(package_id):
    if package_id not in PACKAGES:
        abort(404)
    package_name, price = PACKAGES[package_id]
    error = ""
    if request.method == "POST":
        player_id = request.form.get("player_id", "").strip()
        player_name = request.form.get("player_name", "").strip()
        receipt = request.files.get("receipt")

        if not player_id or not player_name:
            error = "شناسه و نام داخل بازی را وارد کن."
        elif not receipt or not receipt.filename:
            error = "تصویر رسید پرداخت را انتخاب کن."
        else:
            filename = secure_filename(receipt.filename)
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("jpg", "jpeg", "png", "webp"):
                error = "فقط تصویر JPG، PNG یا WEBP مجاز است."
            else:
                filename = secrets.token_hex(16) + "." + ext
                receipt.save(os.path.join(UPLOAD_FOLDER, filename))
                con = connect_db()
                con.execute("""
                    INSERT INTO orders
                    (user_id,package,price,player_id,player_name,receipt,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    session["user_id"], package_name, price, player_id,
                    player_name, filename, "در انتظار بررسی",
                    datetime.now().strftime("%Y-%m-%d %H:%M")
                ))
                con.commit()
                con.close()
                return redirect("/orders")
    return page("""
    <div class="card">
      <h2>سفارش {{ package_name }}</h2>
      <p class="price">{{ "{:,}".format(price) }} تومان</p>
      <div class="notice">
      شماره کارت: <b>{{ card }}</b><br>
      به نام: <b>{{ owner }}</b><br>
      ابتدا مبلغ دقیق را واریز کن، سپس رسید را همین‌جا بفرست.
      </div>
      <p class="small">رسید را حداکثر تا ۱۰ دقیقه پس از پرداخت ارسال کن. ثبت سفارش به معنی تأیید پرداخت نیست.</p>
      <p style="color:#ff7777">{{ error }}</p>
      <form method="post" enctype="multipart/form-data">
        <label>شناسه بازیکن پابجی (Player ID)</label>
        <input name="player_id" required>
        <label>نام بازیکن داخل بازی</label>
        <input name="player_name" required>
        <label>تصویر رسید پرداخت</label>
        <input type="file" name="receipt" accept=".jpg,.jpeg,.png,.webp" required>
        <button>ثبت سفارش و ارسال رسید</button>
      </form>
    </div>
    """, package_name=package_name, price=price, card=CARD_NUMBER,
       owner=CARD_OWNER, error=error)

@app.route("/orders")
@login_required
def orders():
    con = connect_db()
    rows = con.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    con.close()
    return page("""
    <div class="card">
    <h2>سفارش‌های من</h2>
    {% if rows %}
    <table>
    <tr><th>شماره</th><th>بسته</th><th>مبلغ</th><th>وضعیت</th></tr>
    {% for o in rows %}
    <tr>
      <td>{{ o['id'] }}</td><td>{{ o['package'] }}</td>
      <td>{{ "{:,}".format(o['price']) }}</td><td>{{ o['status'] }}</td>
    </tr>
    {% endfor %}
    </table>
    {% else %}
    <p>هنوز سفارشی ثبت نکردی.</p>
    {% endif %}
    </div>
    """, rows=rows)

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD and ADMIN_PASSWORD != "change-this-password":
            session["is_admin"] = True
            return redirect("/admin")
        error = "رمز مدیریت اشتباه است یا هنوز در تنظیمات سایت عوض نشده."
    return page("""
    <div class="card">
    <h2>ورود مدیریت</h2><p style="color:#ff7777">{{ error }}</p>
    <form method="post">
      <label>رمز مدیریت</label>
      <input type="password" name="password" required>
      <button>ورود</button>
    </form></div>
    """, error=error)

@app.route("/admin")
@admin_required
def admin():
    con = connect_db()
    rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return page("""
    <div class="card">
    <h2>پنل مدیریت سفارش‌ها</h2>
    <p class="small">رسیدها را بررسی کن و سپس وضعیت سفارش را تغییر بده.</p>
    {% for o in rows %}
    <div class="card">
      <h3>سفارش شماره {{ o['id'] }} — {{ o['package'] }}</h3>
      <p>مبلغ: {{ "{:,}".format(o['price']) }} تومان</p>
      <p>کاربر: {{ o['user_id'] }} | بازیکن: {{ o['player_name'] }} | شناسه: {{ o['player_id'] }}</p>
      <p>تاریخ: {{ o['created_at'] }}</p>
      <p>وضعیت فعلی: <b>{{ o['status'] }}</b></p>
      <a class="btn" href="/admin/receipt/{{ o['id'] }}" target="_blank">دیدن رسید</a>
      <form method="post" action="/admin/status/{{ o['id'] }}">
        <label>تغییر وضعیت</label>
        <select name="status">
        {% for s in statuses %}
          <option value="{{ s }}" {% if s == o['status'] %}selected{% endif %}>{{ s }}</option>
        {% endfor %}
        </select>
        <button>ذخیره وضعیت</button>
      </form>
    </div>
    {% else %}
    <p>هنوز سفارشی ثبت نشده.</p>
    {% endfor %}
    <a href="/admin-logout">خروج از مدیریت</a>
    </div>
    """, rows=rows, statuses=[
        "در انتظار بررسی", "پرداخت تأیید شد",
        "در حال ارسال", "تکمیل‌شده", "رد شده"
    ])

@app.route("/admin/receipt/<int:order_id>")
@admin_required
def admin_receipt(order_id):
    con = connect_db()
    row = con.execute(
        "SELECT receipt FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    con.close()
    if not row:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, row["receipt"])

@app.route("/admin/status/<int:order_id>", methods=["POST"])
@admin_required
def admin_status(order_id):
    allowed = [
        "در انتظار بررسی", "پرداخت تأیید شد",
        "در حال ارسال", "تکمیل‌شده", "رد شده"
    ]
    status = request.form.get("status", "")
    if status not in allowed:
        abort(400)
    con = connect_db()
    con.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    con.commit()
    con.close()
    return redirect("/admin")

@app.route("/admin-logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/")

@app.errorhandler(413)
def too_large(error):
    return "حجم تصویر رسید نباید بیشتر از ۵ مگابایت باشد.", 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
