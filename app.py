from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import csv
import sqlite3

from flask import Flask, render_template, request, redirect

app = Flask(__name__)


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
DATASET_PATH = BASE_DIR / "data" / "hotel_bookings.csv"


# -----------------------------
# Database Connection
# -----------------------------
def connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_arrival_date(row):
    return datetime.strptime(
        f"{to_int(row.get('arrival_date_day_of_month'))} {row.get('arrival_date_month')} {to_int(row.get('arrival_date_year'))}",
        "%d %B %Y"
    )


def load_dataset_preview(limit=8, max_rows=5000):
    if not DATASET_PATH.exists():
        return {
            "summary": {
                "total_bookings": 0,
                "cancellation_rate": 0,
                "average_lead_time": 0,
                "average_daily_rate": 0,
                "top_hotel": "N/A",
                "top_country": "N/A",
                "top_room_type": "N/A",
                "top_hotel_share": 0,
                "top_room_share": 0,
                "confirmed_share": 0,
            },
            "preview": [],
        }

    total_rows = 0
    canceled_rows = 0
    lead_time_total = 0
    adr_total = 0.0
    hotel_counter = Counter()
    country_counter = Counter()
    room_counter = Counter()
    preview_rows = []

    with DATASET_PATH.open(newline="", encoding="utf-8") as dataset_file:
        reader = csv.DictReader(dataset_file)

        for index, row in enumerate(reader, start=1):
            if index > max_rows:
                break

            total_rows += 1

            is_canceled = to_int(row.get("is_canceled")) == 1
            if is_canceled:
                canceled_rows += 1

            lead_time_total += to_int(row.get("lead_time"))
            adr_total += to_float(row.get("adr"))

            hotel_counter[row.get("hotel") or "Unknown"] += 1
            country = row.get("country") or "Unknown"
            if country == "NULL":
                country = "Unknown"
            country_counter[country] += 1
            room_counter[row.get("reserved_room_type") or "Unknown"] += 1

            if len(preview_rows) < limit:
                arrival_date = format_arrival_date(row)
                stay_length = to_int(row.get("stays_in_weekend_nights")) + to_int(row.get("stays_in_week_nights"))
                check_out = arrival_date + timedelta(days=stay_length or 1)
                guest_count = to_int(row.get("adults")) + to_int(row.get("children")) + to_int(row.get("babies"))

                preview_rows.append({
                    "booking_ref": f"#{index:05d}",
                    "hotel": row.get("hotel") or "Unknown",
                    "country": country,
                    "arrival": arrival_date.strftime("%d %b %Y"),
                    "checkout": check_out.strftime("%d %b %Y"),
                    "guests": guest_count or 1,
                    "room_type": row.get("reserved_room_type") or "Unknown",
                    "status": "Cancelled" if is_canceled else "Confirmed",
                    "status_class": "cancelled" if is_canceled else "confirmed",
                    "adr": f"₹{to_float(row.get('adr')):,.0f}",
                })

    return {
        "summary": {
            "total_bookings": total_rows,
            "cancellation_rate": round((canceled_rows / total_rows) * 100, 1) if total_rows else 0,
            "average_lead_time": round(lead_time_total / total_rows) if total_rows else 0,
            "average_daily_rate": round(adr_total / total_rows) if total_rows else 0,
            "top_hotel": hotel_counter.most_common(1)[0][0] if hotel_counter else "N/A",
            "top_country": country_counter.most_common(1)[0][0] if country_counter else "N/A",
            "top_room_type": room_counter.most_common(1)[0][0] if room_counter else "N/A",
            "top_hotel_share": round((hotel_counter.most_common(1)[0][1] / total_rows) * 100, 1) if total_rows and hotel_counter else 0,
            "top_room_share": round((room_counter.most_common(1)[0][1] / total_rows) * 100, 1) if total_rows and room_counter else 0,
            "confirmed_share": round(((total_rows - canceled_rows) / total_rows) * 100, 1) if total_rows else 0,
        },
        "preview": preview_rows,
    }


DATASET_RESULTS = load_dataset_preview()


# -----------------------------
# Create Booking Table
# -----------------------------
conn = connect()

conn.execute("""
CREATE TABLE IF NOT EXISTS booking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    room TEXT,
    days INTEGER
)
""")

conn.commit()
conn.close()


# -----------------------------
# Home Page
# -----------------------------
@app.route('/')
def home():
    return render_template(
        "index.html",
    )


# -----------------------------
# Rooms Page
# -----------------------------
@app.route('/rooms')
def rooms():
    return render_template("rooms.html")


# -----------------------------
# Booking Page
# -----------------------------
@app.route('/booking', methods=["GET", "POST"])
def booking():

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        room = request.form["room"]
        days = request.form["days"]

        conn = connect()

        cursor = conn.execute(
            "INSERT INTO booking(name, phone, room, days) VALUES (?, ?, ?, ?)",
            (name, phone, room, days)
        )

        conn.commit()
        conn.close()

        return redirect("/bookings")

    return render_template("booking.html")


# -----------------------------
# Bookings Page
# -----------------------------
@app.route('/bookings')
def bookings():
    conn = connect()

    data = conn.execute("SELECT * FROM booking ORDER BY id DESC").fetchall()

    conn.close()

    return render_template(
        "bookings.html",
        data=data,
        summary=DATASET_RESULTS["summary"],
        preview=DATASET_RESULTS["preview"],
    )

# -----------------------------
# Gallery Page
# -----------------------------
@app.route('/gallery')
def gallery():
    return render_template("gallery.html")
# -----------------------------
# Contact Page
# -----------------------------
@app.route('/contact')
def contact():
    return render_template("contact.html")



# -----------------------------
# Run Flask
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)