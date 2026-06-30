from pathlib import Path
import os
import re
import time
import platform
import shutil
import multiprocessing as mp
import random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import folium

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, send_from_directory, abort
)
from flask_session import Session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

import pdfkit

# --- Project imports ---
from sawmill_model import Model
from run_replication import run_replication
from sawmill_utilities import (
    aggregate_and_average_results,
    average_elements_with_count,
    add_lists_with_padding,
    find_alternative_sawmill,
)

# -----------------------------------------------------------------------------
# App & Config
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "a-super-secret-key-that-does-not-change"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
server_session = Session(app)

# -----------------------------------------------------------------------------
# Data Loading
#--------------------------------------------------------------------------
data = pd.ExcelFile("data/timber_59_sawmill.xlsx")
logging_site_data = pd.read_excel(data, "LoggingSite")
sawmill_data = pd.read_excel(data, "Sawmill")
company_data = pd.read_excel(data, "Company")
truck_data = pd.read_excel(data, "Truck")
travel_times_data = pd.read_excel(data, "Travel_times")

# --- DATA PRE-PROCESSING FOR NEW COLUMNS ---
# Ensure Logging Site columns exist and fill NaNs
if 'species' not in logging_site_data.columns:
    logging_site_data['species'] = 'mixed'
if 'type' not in logging_site_data.columns:
    logging_site_data['type'] = 'other'

# Default 'saw/other' if missing, default 'mixed' species if missing
logging_site_data.fillna({'species': 'mixed', 'type': 'other'}, inplace=True)

# Ensure Sawmill columns exist
if 'mill_type' not in sawmill_data.columns:
    sawmill_data['mill_type'] = 'lumber'
if 'species' not in sawmill_data.columns:
    sawmill_data['species'] = 'mixed'

sawmill_data.fillna({'mill_type': 'lumber', 'species': 'mixed'}, inplace=True)

# -----------------------------------------------------------------------------
# User Management via Excel
# -----------------------------------------------------------------------------
USER_FILE = "users.xlsx"
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


def load_users():
    """Load users from Excel into a dict."""
    if os.path.exists(USER_FILE):
        df = pd.read_excel(USER_FILE)
        users_dict = {}
        for _, row in df.iterrows():
            users_dict[row["username"]] = {
                "password": row["password"],
                "email": row.get("email", ""),
            }
        return users_dict
    return {}


def save_user(username, hashed_password, email):
    """Persist (username, password hash, email) to Excel."""
    users = load_users()
    users[username] = {"password": hashed_password, "email": email}
    df = pd.DataFrame(
        [
            {"username": uname, "password": data["password"], "email": data["email"]}
            for uname, data in users.items()
        ]
    )
    df.to_excel(USER_FILE, index=False)


# -----------------------------------------------------------------------------
# Auth Helpers
# -----------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if "username" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return _wrap


# -----------------------------------------------------------------------------
# Auth Routes
# -----------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not re.match(EMAIL_REGEX, email):
            flash("Invalid email address format.", "register")
            return redirect(url_for("home", auth="register"))

        if password != confirm_password:
            flash("Passwords do not match.", "register")
            return redirect(url_for("home", auth="register"))

        users = load_users()
        if username in users:
            flash("Username already exists.", "register")
            return redirect(url_for("home", auth="register"))

        if any(u.get("email") == email for u in users.values()):
            flash("This email address is already registered.", "register")
            return redirect(url_for("home", auth="register"))

        hashed_password = generate_password_hash(password)
        save_user(username, hashed_password, email)
        flash("Registration successful! Please log in.", "login")
        return redirect(url_for("home", auth="login"))

    # Direct /register hit -> show homepage with register modal
    return redirect(url_for("home", auth="register"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        users = load_users()
        user_to_login = next(
            (uname for uname, info in users.items() if info.get("email") == email),
            None,
        )

        if user_to_login is None or not check_password_hash(
            users[user_to_login]["password"], password
        ):
            flash("Invalid email or password.", "login")
            return redirect(url_for("home", auth="login"))

        session["username"] = user_to_login
        flash(f"Welcome back, {user_to_login}!", "login")
        return redirect(url_for("index"))

    # GET /login -> homepage with login modal
    return redirect(url_for("home", auth="login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been successfully logged out.", "login")
    return redirect(url_for("home", auth="login"))


# -----------------------------------------------------------------------------
# Core Pages
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """Homepage that hosts the auth modals & entry points."""
    return render_template("home.html")


@app.route("/dashboard", methods=["GET", "POST"], endpoint="index")
@login_required
def dashboard():
    """Main dashboard shown after login."""
    sawmills = sawmill_data[["sawmill_id", "sawmill_name"]]
    return render_template("index.html", sawmills=sawmills)


@app.route("/reset_session")
@login_required
def reset_session():
    """Clear only session data (not login) and go back to dashboard."""
    session.clear()
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Plot Helpers
# -----------------------------------------------------------------------------
def save_dual_series_plot(series_a, series_b, label_a, label_b, title, ylabel, filename):
    plt.figure(figsize=(10, 5))
    if series_a:
        plt.plot(series_a, marker=".", label=label_a)
    if series_b:
        plt.plot(series_b, marker=".", label=label_b)
    plt.title(title)
    plt.xlabel("Truck Index")
    plt.ylabel(ylabel)
    if series_a or series_b:
        plt.legend()
    plt.grid(True)
    plt.tight_layout()
    os.makedirs("static/plots", exist_ok=True)
    plt.savefig(os.path.join("static/plots", filename))
    plt.close()


def save_cumulative_plot(data, title, ylabel, filename, color="b"):
    plt.figure(figsize=(10, 5))
    if data:
        x_vals = np.cumsum(data)
        plt.plot(x_vals, data, marker=".", color=color)
    plt.title(title)
    plt.xlabel("Accumulated Time (Minutes)")
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.tight_layout()
    os.makedirs("static/plots", exist_ok=True)
    plt.savefig(os.path.join("static/plots", filename))
    plt.close()
def save_plot(data, title, ylabel, filename, color="b"):
            plt.figure(figsize=(10, 5));
            if data: plt.plot(data, marker=".", color=color)
            plt.title(title); plt.xlabel("Truck Index"); plt.ylabel(ylabel);
            plt.grid(True); plt.tight_layout();
            plt.savefig(os.path.join("static/plots", filename)); plt.close();
     

def save_time_series_plot(x_times, y_vals, title, ylabel, filename, color="b"):
    if not x_times or not y_vals:
        return

    import datetime as dt

    x_dt = [dt.datetime(2000, 1, 1) + dt.timedelta(minutes=int(m)) for m in x_times]
    n = min(len(x_dt), len(y_vals))
    x = np.asarray(x_dt[:n])
    y = np.asarray(y_vals[:n])

    plt.figure(figsize=(12, 5))
    plt.step(x, y, where="post", color=color)
    plt.title(title)
    plt.xlabel("Time of Day (HH:MM)")
    plt.ylabel(ylabel)
    plt.grid(True)
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=90)
    plt.tight_layout()
    os.makedirs("static/plots", exist_ok=True)
    plt.savefig(os.path.join("static/plots", filename))
    plt.close()


# ... (imports remain the same) ...

# -----------------------------------------------------------------------------
# HELPER: Compatibility & Routing
# -----------------------------------------------------------------------------
def _check_compatibility(ls_row, sm_row):
    """
    Python implementation of the simulation's compatibility logic.
    """
    # 1. Species Logic
    ls_species = str(ls_row.get('species', 'mixed')).lower()
    if 'mixed' in ls_species or '/' in ls_species: ls_species = 'mixed'
    
    sm_species = str(sm_row.species).lower()
    if 'mixed' in sm_species or '/' in sm_species: sm_species = 'mixed'

    species_match = (sm_species == 'mixed') or (ls_species == 'mixed') or (ls_species == sm_species)
    if not species_match: return False

    # 2. Mill Type Logic
    ls_type = str(ls_row.get('type', 'other')).lower()
    sm_type = str(sm_row.mill_type).lower()

    if 'saw' in ls_type: # saw/other -> Must go to Lumber
        if sm_type != 'lumber': return False
    else: # other -> Must NOT go to Lumber
        if sm_type == 'lumber': return False
        
    return True

def _get_travel_time(sm_id, ls_id):
    filtered = travel_times_data[(travel_times_data['Sawmill'] == sm_id) & (travel_times_data['LoggingSite'] == ls_id)]
    if filtered.empty: return float('inf')
    return filtered.iloc[0]['Total_TruckTravelTime']

# --- UPDATED HELPER: IGNORE COMPETITION ---
def _get_potential_sites_for_sawmill(target_sm_id):
    """
    Returns ALL logging sites that satisfy:
    1. Compatibility (Species & Type)
    2. Reachability (Travel time exists in Excel)
    Ignores whether another sawmill is closer.
    """
    assigned_sites = []
    
    # Get the target sawmill object
    target_sm_df = sawmill_data[sawmill_data['sawmill_id'] == target_sm_id]
    if target_sm_df.empty: return []
    target_sm = list(target_sm_df.itertuples())[0]
    
    for ls in logging_site_data.itertuples():
        ls_dict = ls._asdict()
        ls_id = str(ls_dict['site_id'])
        
        # Check 1: Compatibility
        if not _check_compatibility(ls_dict, target_sm):
            continue
            
        # Check 2: Reachability
        dist = _get_travel_time(target_sm_id, ls_id)
        if dist == float('inf'):
            continue
            
        # If passed, add to list (No competition check)
        assigned_sites.append(ls_dict)
            
    return assigned_sites

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/start_one_sawmill")
@login_required
def start_one_sawmill():
    """Reset sim-specific session data before starting a new single-sawmill run."""
    # Clear session keys related to custom simulation data
    for key in ["company_data", "truck_data", "new_travel_times"]:
        session.pop(key, None)

    # Clear all logging site lists for specific sawmills
    for key in [k for k in session.keys() if k.startswith("logging_sites_")]:
        session.pop(key, None)

    return redirect(url_for("one_sawmill"))



import math
import random

def generate_logging_site_on_circle(sawmill_lat, sawmill_lng, real_distance, conversion_factor=0.2):
    """
    Generates a logging site exactly on the boundary of a circle around the disrupted sawmill.
    """
    # 1. Map real distance to Euclidean radius T
    T = real_distance * (1 - conversion_factor)
    
    # 2. Convert T to coordinate degrees so it plots correctly on the map (1 deg approx 69 miles)
    # Assuming the real_distance is in miles. If it is in minutes, assume 45mph (0.75 miles/min)
    # distance_in_miles = real_distance * 0.75  <-- uncomment this if input is in minutes!
    distance_in_miles = real_distance 
    
    T_degrees = distance_in_miles / 69.0 
    
    # 3. Generate random angle
    theta = random.uniform(0, 2 * math.pi)
    
    # 4. Calculate new coordinates (x = lng, y = lat)
    new_lng = sawmill_lng + (T_degrees * math.cos(theta))
    new_lat = sawmill_lat + (T_degrees * math.sin(theta))
    
    return round(new_lat, 6), round(new_lng, 6)


# -----------------------------------------------------------------------------
# 1. GENERATE SITES ROUTE (Called by the "Generate & View" button)
# -----------------------------------------------------------------------------
# @app.route("/generate_sites", methods=["POST"])
# @login_required
# def generate_sites():
    sawmill_id = request.form.get("sawmill_id")
    try:
        num_sites = int(request.form.get("num_generated_sites", 10))
        max_time = float(request.form.get("max_travel_time", 90))
        # Get Softwood Ratio (Default 50%)
        sw_ratio_percent = float(request.form.get("softwood_ratio", 50))
    except ValueError:
        num_sites = 10
        max_time = 90.0
        sw_ratio_percent = 50.0
    
    if not sawmill_id:
        return jsonify({"error": "Sawmill ID required"}), 400

    # Get Sawmill Specs
    filtered = sawmill_data[sawmill_data["sawmill_id"] == sawmill_id]
    if filtered.empty: return jsonify({"error": "Invalid Sawmill"}), 400
    sm_row = filtered.iloc[0]
    
    # Determine Timber Type (Sawlog vs Pulpwood)
    sm_type = str(sm_row.get('mill_type', 'pulp/paper')).lower()
    ls_type = 'saw/other' if sm_type == 'lumber' else 'other'

    # Calculate Capacities based on Ratio
    total_capacity = 200000
    sw_amount = int(total_capacity * (sw_ratio_percent / 100.0))
    hw_amount = int(total_capacity - sw_amount)

    # Determine Species based on Ratio
    if sw_amount > 0 and hw_amount > 0:
        ls_species = 'mixed'
    elif sw_amount > 0:
        ls_species = 'soft'
    else:
        ls_species = 'hard'

    generated_sites = []
    
    for i in range(num_sites):
        site_id = f"GEN_LS_{i+1}"
        travel_time = round(random.uniform(10, max_time), 1)
        
        site = {
            'site_id': site_id,
            'sawmill': sawmill_id,
            'company_id': f"GEN_CO_{i+1}",
            'avg_loading_time': 15.0,
            'opening_time': 360,
            'closing_time': 960,
            'initial_log_capacity': total_capacity,
            'hardwood_amount': hw_amount,
            'softwood_amount': sw_amount,
            'species': ls_species,
            'type': ls_type,
            'num_trucks': 13,
            'travel_time': travel_time
        }
        generated_sites.append(site)

    session[f"generated_sites_{sawmill_id}"] = generated_sites
    session.modified = True
    
    return jsonify({
        "status": "success", 
        "message": f"Generated {num_sites} sites ({sw_ratio_percent}% Softwood) for {sawmill_id}."
    })
# -----------------------------------------------------------------------------
# 2. LS_INFO ROUTE (Displays list of sites + Travel Time)
# -----------------------------------------------------------------------------
@app.route("/ls_info", methods=["GET"])
@login_required
def ls_info():
    sawmill_id = request.args.get("sawmill_id")
    if not sawmill_id: return "Error: Sawmill ID is required.", 400

    sawmill_row = sawmill_data[sawmill_data["sawmill_id"] == sawmill_id]
    sawmill_name = sawmill_row.iloc[0]["sawmill_name"] if not sawmill_row.empty else "Unknown"
    
    # 1. Determine Species (Same as Sawmill)
    sawmill_species = "mixed"
    if not sawmill_row.empty:
        val = sawmill_row.iloc[0].get('species')
        if pd.notna(val): sawmill_species = str(val).lower()

    # 2. Determine Type (Lumber -> saw/other, else -> other)
    sawmill_mill_type = "pulp/paper" # default
    if not sawmill_row.empty:
        val = sawmill_row.iloc[0].get('mill_type')
        if pd.notna(val): sawmill_mill_type = str(val).lower()
    
    logging_site_type = "saw/other" if sawmill_mill_type == "lumber" else "other"

    # 3. Get Sites (Generated or DB)
    session_key = f"generated_sites_{sawmill_id}"
    if session_key in session:
        sites_for_sawmill = session[session_key]
    else:
        sites_for_sawmill = _get_potential_sites_for_sawmill(sawmill_id)
        
        # Add derived info to DB sites if missing
        active_companies = company_data[company_data['logging_site'].isin([s['site_id'] for s in sites_for_sawmill])]
        active_trucks = truck_data[truck_data['company_id'].isin(active_companies['company_id'])]
        truck_counts = active_trucks.groupby("company_id").size()

        for s in sites_for_sawmill:
             t_time = _get_travel_time(sawmill_id, str(s['site_id']))
             s['travel_time'] = round(t_time, 1) if t_time != float('inf') else 0
             cid = s.get('company_id')
             s['num_trucks'] = int(truck_counts.get(cid, 0))
             
             # Ensure DB sites visualize the correct inferred type/species
             if 'species' not in s: s['species'] = sawmill_species
             if 'type' not in s: s['type'] = logging_site_type

    return render_template(
        "ls_info.html",
        sawmill_id=sawmill_id,
        sawmill_name=sawmill_name,
        sawmill_species=sawmill_species, # Passed for auto-fill
        logging_site_type=logging_site_type, # Passed for auto-fill
        logging_sites=sites_for_sawmill,
        total_rows=len(sites_for_sawmill),
        sawmill_data=sawmill_data.to_dict(orient="records"),
    )
# -----------------------------------------------------------------------------
# 3. ONE_SAWMILL ROUTE (Simulation Logic)
# -----------------------------------------------------------------------------
@app.route('/generate_sites', methods=['POST'])
@login_required
def generate_sites():
    # 1. CLEAN THE ID (Fixes the whitespace bug)
    sawmill_id = str(request.form.get('sawmill_id')).strip()
    
    num_sites = int(request.form.get('num_generated_sites', 10))
    max_travel = float(request.form.get('max_travel_time', 90))
    
    # HARDCODED CONVERSION FACTOR (e.g., 20% penalty for winding roads)
    conversion_factor = 0.20
    
    # Get the target sawmill from your dataframe
    sm_row = sawmill_data[sawmill_data['sawmill_id'] == sawmill_id]
    if sm_row.empty:
        return jsonify({"status": "error", "error": "Sawmill not found"}), 404
        
    sm_lat = float(sm_row['Latitude'].values[0])
    sm_lng = float(sm_row['Longitude'].values[0])
    
    # --- NEW LOGIC: Determine Species and Ratio based on Sawmill ---
    raw_sm_species = str(sm_row['species'].values[0]).lower().strip()
    sm_type = str(sm_row.get('mill_type', 'pulp/paper')).lower().strip()
    ls_type = 'saw/other' if 'lumber' in sm_type else 'other'
    
    if 'soft' in raw_sm_species and 'hard' not in raw_sm_species and 'mixed' not in raw_sm_species:
        # Sawmill is strictly Softwood
        actual_softwood_ratio = 1.0
        ls_species_label = 'soft'
    elif 'hard' in raw_sm_species and 'soft' not in raw_sm_species and 'mixed' not in raw_sm_species:
        # Sawmill is strictly Hardwood
        actual_softwood_ratio = 0.0
        ls_species_label = 'hard'
    else:
        # Sawmill is Mixed (or undefined), use the user's requested ratio
        user_ratio = float(request.form.get('softwood_ratio', 50)) / 100.0
        actual_softwood_ratio = user_ratio
        
        if actual_softwood_ratio == 1.0:
            ls_species_label = 'soft'
        elif actual_softwood_ratio == 0.0:
            ls_species_label = 'hard'
        else:
            ls_species_label = 'mixed'
    # ---------------------------------------------------------------

    generated_sites = []
    
    for i in range(1, num_sites + 1):
        # Generate random travel time (or distance) up to the max
        travel_time = round(random.uniform(10.0, max_travel), 1)
        
        # GENERATE LATITUDE AND LONGITUDE
        site_lat, site_lng = generate_logging_site_on_circle(
            sm_lat, 
            sm_lng, 
            travel_time, # Match parameter names to your function!
            conversion_factor
        )
        
        # Calculate specific tonnage
        capacity = 10000
        softwood_amt = int(capacity * actual_softwood_ratio)
        hardwood_amt = capacity - softwood_amt
        
        site_id_val = f"GEN_{sawmill_id}_LS{i}"
        
        # Build the site dictionary
        site_info = {
            "site_id": site_id_val,
            "company_id": f"{site_id_val}_CO",
            "sawmill": sawmill_id,
            "lat": site_lat,               
            "lng": site_lng,               
            "travel_time": travel_time,
            "avg_loading_time": 15.0,
            "opening_time": 360,           
            "closing_time": 960,           
            "initial_log_capacity": capacity,
            "softwood_amount": softwood_amt,
            "hardwood_amount": hardwood_amt,
            "species": ls_species_label, 
            "type": ls_type,
            "num_trucks": 13  # <--- FIX: ADDED TRUCKS HERE!
        }
        generated_sites.append(site_info)

    # Save to session so the ls_info page can read it
    session_key = f"generated_sites_{sawmill_id}"
    session[session_key] = generated_sites
    
    # --- FIX: INJECT TRAVEL TIMES SO THE ENGINE CAN ROUTE THE TRUCKS ---
    new_tt = session.get("new_travel_times", [])
    for site in generated_sites:
        new_tt.append({
            "Sawmill": sawmill_id, 
            "LoggingSite": site['site_id'], 
            "Total_TruckTravelTime": site['travel_time']
        })
    session["new_travel_times"] = new_tt
    # -------------------------------------------------------------------

    session.modified = True

    # FIX: Return the sites array so the frontend modal can display it!
    return jsonify({
        "status": "success", 
        "message": f"Successfully generated {num_sites} {ls_species_label} sites.",
        "sites": generated_sites
    })

@app.route("/generate_multi_sites", methods=["POST"])
@login_required
def generate_multi_sites():
    data = request.get_json()
    raw_sawmill_ids = data.get("sawmill_ids", [])
    if not raw_sawmill_ids: return jsonify({"error": "No sawmills selected"}), 400
    
    # 1. CLEAN IDs: Strip all hidden whitespace
    sawmill_ids = [str(sid).strip() for sid in raw_sawmill_ids]
    
    total_sites_req = int(data.get("total_sites", 100))
    max_time = float(data.get("max_travel_time", 90))
    sw_ratio_percent = float(data.get("softwood_ratio", 50))
    conversion_factor = 0.20

    # 2. FILTER SAFELY: Create a temporary clean column to match against
    sd_copy = sawmill_data.copy()
    sd_copy['clean_id'] = sd_copy['sawmill_id'].astype(str).str.strip()
    selected_mills = sd_copy[sd_copy['clean_id'].isin(sawmill_ids)].copy()

    # 3. FIX MATH: Force capacities to be real numbers (fallback to 1 if missing/broken)
    if 'sawmill_capacity' not in selected_mills.columns: 
        selected_mills['sawmill_capacity'] = 1 
    selected_mills['sawmill_capacity'] = pd.to_numeric(selected_mills['sawmill_capacity'], errors='coerce').fillna(1)
    
    total_capacity_sum = selected_mills['sawmill_capacity'].sum()
    if total_capacity_sum <= 0: total_capacity_sum = 1 # Prevent division by zero

    sites_created_count = 0
    all_generated_data_flat = [] 

    # Clear old session data using clean IDs
    for sid in sawmill_ids:
        session.pop(f"logging_sites_{sid}", None) 

    for _, sm_row in selected_mills.iterrows():
        sid = str(sm_row['clean_id']) # Use the guaranteed clean ID
        capacity = sm_row['sawmill_capacity']
        sm_name = sm_row['sawmill_name']
        
        # Coordinates
        sm_lat = float(sm_row.get('Latitude', 0.0))
        sm_lng = float(sm_row.get('Longitude', 0.0))
        
        # Math for distribution
        my_share_sites = int(round((capacity / total_capacity_sum) * total_sites_req))
        if my_share_sites < 1 and total_sites_req > 0: my_share_sites = 1
            
        sm_species = str(sm_row.get('species', 'mixed')).lower().strip()
        sm_type = str(sm_row.get('mill_type', 'pulp/paper')).lower().strip()
        ls_type = 'saw/other' if 'lumber' in sm_type else 'other'
        
        # Species Logic
        if 'soft' in sm_species and 'hard' not in sm_species and 'mixed' not in sm_species:
            actual_sw_ratio = 1.0
            ls_species = 'soft'
        elif 'hard' in sm_species and 'soft' not in sm_species and 'mixed' not in sm_species:
            actual_sw_ratio = 0.0
            ls_species = 'hard'
        else:
            actual_sw_ratio = sw_ratio_percent / 100.0
            if actual_sw_ratio == 1.0: ls_species = 'soft'
            elif actual_sw_ratio == 0.0: ls_species = 'hard'
            else: ls_species = 'mixed'
        
        total_log_cap = 200000
        sw_amount = int(total_log_cap * actual_sw_ratio)
        hw_amount = total_log_cap - sw_amount

        my_sites = []
        for k in range(my_share_sites):
            site_id = f"GEN_{sid}_{k+1}"
            travel_time = round(random.uniform(10, max_time), 1)
            
            site_lat, site_lng = generate_logging_site_on_circle(
                sm_lat, sm_lng, travel_time, conversion_factor
            )
            
            site_obj = {
                'site_id': site_id, 'sawmill': sid, 'company_id': f"CO_{site_id}",
                'lat': site_lat, 'lng': site_lng, 
                'avg_loading_time': 15.0, 'opening_time': 360, 'closing_time': 960,
                'initial_log_capacity': total_log_cap, 'hardwood_amount': hw_amount, 'softwood_amount': sw_amount,
                'species': ls_species, 'type': ls_type, 'num_trucks': 13, 'travel_time': travel_time
            }
            my_sites.append(site_obj)
            
            display_obj = site_obj.copy()
            display_obj['sawmill_name'] = sm_name
            all_generated_data_flat.append(display_obj)
            
        session[f"logging_sites_{sid}"] = my_sites
        sites_created_count += len(my_sites)

        new_tt = session.get("new_travel_times", [])
        for s in my_sites:
            new_tt.append({"Sawmill": sid, "LoggingSite": s['site_id'], "Total_TruckTravelTime": s['travel_time']})
        session["new_travel_times"] = new_tt

    session.modified = True
    
    return jsonify({
        "status": "success", 
        "message": f"Successfully generated {sites_created_count} sites based on sawmill capacity.",
        "sites": all_generated_data_flat 
    })

# --- ONE SAWMILL ROUTE ---
@app.route("/one_sawmill", methods=["GET", "POST"])
@login_required
def one_sawmill():
    if request.method == "POST":
        # 1. FIX THE WHITESPACE BUG HERE
        selected_sawmill_id = str(request.form.get("sawmill")).strip()
        
        if not selected_sawmill_id:
            flash("Please select a sawmill.", "error")
            return redirect(url_for("one_sawmill"))

        # Collect Params
        unload_mean_time = float(request.form.get("unload_mean_time", 15))
        scale_in_time = float(request.form.get("scale_in_time", 1))
        scale_out_time = float(request.form.get("scale_out_time", 1))
        breakdown_type = request.form.get("breakdown_type")
        breakdown_gap = int(request.form.get("breakdown_gap", 1))
        truck_waiting_area = int(request.form.get("truck_waiting_area", 40))
        total_days = int(request.form.get("simulation_days", 1))
        
        filtered_sawmill = sawmill_data[sawmill_data["sawmill_id"] == selected_sawmill_id].copy()
        if filtered_sawmill.empty:
            flash(f"Sawmill ID {selected_sawmill_id} not found in database.", "error")
            return redirect(url_for("one_sawmill"))
            
        sawmill_name = filtered_sawmill.iloc[0]["sawmill_name"]
        
        # Apply form overrides
        filtered_sawmill["unload_time_mean"] = unload_mean_time
        filtered_sawmill["scale_in_time"] = scale_in_time
        filtered_sawmill["scale_out_time"] = scale_out_time
        filtered_sawmill["truck_area_capacity"] = truck_waiting_area

        ls_source = request.form.get("ls_source")
        
        # 2. Get Logging Sites
        if ls_source == "generated":
            # Because we stripped the ID above, this will perfectly match your modal generation!
            session_key = f"generated_sites_{selected_sawmill_id}"
            
            if session_key in session:
                generated_sites = session[session_key]
            else:
                # Fallback Generation (Added num_trucks just in case!)
                num_sites = int(request.form.get("num_generated_sites", 10))
                max_time = float(request.form.get("max_travel_time", 90))
                sw_ratio_percent = float(request.form.get("softwood_ratio", 50))

                sm_row = filtered_sawmill.iloc[0]
                sm_type = str(sm_row.get('mill_type', 'pulp/paper')).lower()
                ls_type = 'saw/other' if sm_type == 'lumber' else 'other'
                
                total_capacity = 200000
                sw_amount = int(total_capacity * (sw_ratio_percent / 100.0))
                hw_amount = int(total_capacity - sw_amount)
                
                if sw_amount > 0 and hw_amount > 0: ls_species = 'mixed'
                elif sw_amount > 0: ls_species = 'soft'
                else: ls_species = 'hard'

                generated_sites = []
                for i in range(num_sites):
                    site_id = f"GEN_{selected_sawmill_id}_LS_{i+1}"
                    generated_sites.append({
                        'site_id': site_id, 'sawmill': selected_sawmill_id,
                        'company_id': f"{site_id}_CO", 'avg_loading_time': 15.0,
                        'opening_time': 480, 'closing_time': 1080, 'initial_log_capacity': total_capacity,
                        'hardwood_amount': hw_amount, 'softwood_amount': sw_amount, 
                        'species': ls_species, 'type': ls_type,
                        'travel_time': random.uniform(10, max_time),
                        'num_trucks': 13 # Added to fallback as well
                    })
                session[session_key] = generated_sites

            all_active_logging_sites = pd.DataFrame(generated_sites)
            
            # Generate Travel Times
            gen_travel_times = pd.DataFrame([
                {'Sawmill': s['sawmill'], 'LoggingSite': s['site_id'], 'Total_TruckTravelTime': s['travel_time']}
                for s in generated_sites
            ])
            active_travel_times = pd.concat([travel_times_data, gen_travel_times], ignore_index=True)
            
            # Generate Companies & Trucks
            all_active_companies = pd.DataFrame([
                {'company_id': s.get('company_id', f"{s['site_id']}_CO"), 'logging_site': s['site_id'], 'num_trucks': 13, 'mean_truck_generate_interval': 0.000001, 'sawmill': selected_sawmill_id}
                for s in generated_sites
            ])
            all_active_trucks = pd.DataFrame([
                {'truck_id': f"{c['company_id']}_T{t}", 'company_id': c['company_id'], 'truck_capacity': 25}
                for c in all_active_companies.to_dict('records')
                for t in range(1, 14)
            ])

        else:
            # DB Logic
            assigned_site_dicts = _get_potential_sites_for_sawmill(selected_sawmill_id)
            all_active_logging_sites = pd.DataFrame(assigned_site_dicts)
            
            if not all_active_logging_sites.empty:
                all_active_logging_sites['sawmill'] = selected_sawmill_id

            valid_site_ids = all_active_logging_sites['site_id'].tolist() if not all_active_logging_sites.empty else []
            
            all_active_companies = company_data[company_data['logging_site'].isin(valid_site_ids)].copy()
            all_active_companies['sawmill'] = selected_sawmill_id

            # SAFETY NET: Companies
            existing_served_sites = set(all_active_companies['logging_site'].tolist())
            orphaned_sites = [s for s in valid_site_ids if s not in existing_served_sites]
            
            if orphaned_sites:
                safety_companies = []
                for site_id in orphaned_sites:
                    safety_companies.append({
                        'company_id': f"AUTO_CO_{site_id}", 'company_name': f"Auto Co {site_id}",
                        'sawmill': selected_sawmill_id, 'logging_site': site_id,
                        'num_trucks': 13, 'mean_truck_generate_interval': 0.000001
                    })
                all_active_companies = pd.concat([all_active_companies, pd.DataFrame(safety_companies)], ignore_index=True)

            active_company_ids = all_active_companies['company_id'].tolist()
            all_active_trucks = truck_data[truck_data['company_id'].isin(active_company_ids)].copy()

            # SAFETY NET: Trucks
            existing_truck_companies = set(all_active_trucks['company_id'].tolist())
            orphaned_companies = [c for c in active_company_ids if c not in existing_truck_companies]
            
            if orphaned_companies:
                safety_trucks = []
                for cid in orphaned_companies:
                    for t in range(1, 14): 
                        safety_trucks.append({'truck_id': f"{cid}_T{t}", 'company_id': cid, 'truck_capacity': 25})
                all_active_trucks = pd.concat([all_active_trucks, pd.DataFrame(safety_trucks)], ignore_index=True)

            active_travel_times = travel_times_data

        # 3. Run Simulation
        number_of_replications = 10
        with mp.Pool(mp.cpu_count()) as pool:
            replications = pool.starmap(
                run_replication,
                [
                    (
                        i, total_days, all_active_logging_sites, filtered_sawmill,
                        filtered_sawmill, 
                        all_active_companies, all_active_trucks,
                        active_travel_times,
                        breakdown_type, breakdown_gap, unload_mean_time,
                        scale_in_time, scale_out_time, truck_waiting_area,
                    )
                    for i in range(number_of_replications)
                ],
            )
        
        avg_result = aggregate_and_average_results(replications, number_of_replications)
        
        # 4. Process Results
        sid = selected_sawmill_id
        full_days = total_days - 1
        total_sim_time = full_days * 1440 + 1245
        if total_sim_time <= 0: total_sim_time = 1

        # Helper to ensure dictionary structure
        for key in ["scale_in_wait_times", "truck_wait_time_in_crane", "truck_turn_time_in_sawmill", "crane1_idle_time", "crane2_idle_time", "sawmill_queue_lengths", "crane1_unloading_time", "crane2_unloading_time", "sawmill_queue_times", "sawmill_queue_lengths_ts"]:
            avg_result.setdefault(key, {})

        s_scale_in = avg_result["scale_in_wait_times"].get(sid, [])
        s_crane = avg_result["truck_wait_time_in_crane"].get(sid, [])
        s_turn = avg_result["truck_turn_time_in_sawmill"].get(sid, [])
        c1_idle = avg_result["crane1_idle_time"].get(sid, [])
        c2_idle = avg_result["crane2_idle_time"].get(sid, [])

        avg_result["avg_wait_time_scalein"] = {sid: float(np.mean(s_scale_in)) if s_scale_in else 0.0}
        avg_result["avg_wait_time_crane"] = {sid: float(np.mean(s_crane)) if s_crane else 0.0}
        avg_result["avg_turn_time"] = {sid: float(np.mean(s_turn)) if s_turn else 0.0}
        avg_result["crane1_utilization"] = {sid: 1.0 - (sum(c1_idle) / total_sim_time if c1_idle else 0.0)}
        avg_result["crane2_utilization"] = {sid: 1.0 - (sum(c2_idle) / total_sim_time if c2_idle else 0.0)}

        os.makedirs("static/plots", exist_ok=True)
        save_plot(s_scale_in, "Scale In Wait Time", "Minutes", f"{sid}_scale_in_wait.png")
        save_plot(s_crane, "Crane Wait Time", "Minutes", f"{sid}_crane_wait_time.png")
        save_plot(avg_result["sawmill_queue_lengths"].get(sid, []), "Queue Lengths", "Trucks", f"{sid}_queue_lengths.png")
        save_plot(avg_result["crane1_idle_time"].get(sid, []), "Crane 1 Idle Time", "Minutes", f"{sid}_crane1_idle.png", "g")
        save_plot(avg_result["crane1_unloading_time"].get(sid, []), "Crane 1 Unload Time", "Minutes", f"{sid}_crane1_unload.png", "r")
        save_plot(avg_result["crane2_idle_time"].get(sid, []), "Crane 2 Idle Time", "Minutes", f"{sid}_crane2_idle.png", "g")
        save_plot(avg_result["crane2_unloading_time"].get(sid, []), "Crane 2 Unload Time", "Minutes", f"{sid}_crane2_unload.png", "r")
        save_plot(s_turn, "Truck Turn Time", "Minutes", f"{sid}_turn_time.png", "r")
        save_dual_series_plot(avg_result["crane1_idle_time"].get(sid, []), avg_result["crane1_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 1 — idle & unloading", "Minutes", f"{sid}_crane1_duo.png")
        save_dual_series_plot(avg_result["crane2_idle_time"].get(sid, []), avg_result["crane2_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 2 — idle & unloading", "Minutes", f"{sid}_crane2_duo.png")
        save_time_series_plot(avg_result["sawmill_queue_times"].get(sid, []), avg_result["sawmill_queue_lengths_ts"].get(sid, []), title="Waiting Area Queue Length vs Time", ylabel="Queue Length (no of trucks)", filename=f"{sid}_queue_len_vs_time.png")
        
        input_params = {
            "unload_mean_time": unload_mean_time, "scale_in_time": scale_in_time,
            "scale_out_time": scale_out_time, "truck_waiting_area": truck_waiting_area,
            "breakdown_type": breakdown_type, "breakdown_gap": breakdown_gap,
        }

        return render_template(
            "results.html",
            sawmill_id=selected_sawmill_id,
            sawmill_name=sawmill_name,
            total_days=total_days,
            number_of_replications=number_of_replications,
            input_params=input_params, 
            avg_result=avg_result,
            logging_sites=all_active_logging_sites.to_dict(orient="records"),
        )

    # --- GET Request ---
    selected_sawmill = None
    logging_sites = []
    default_softwood_ratio = 50 

    map_center = [32.815, -89.717]
    my_map = folium.Map(location=map_center, zoom_start=6.5)
    mississippi_geojson_path = "data/mississippi.geojson"
    if os.path.exists(mississippi_geojson_path):
        folium.GeoJson(mississippi_geojson_path, style_function=lambda x: {'fillColor': '#a9d6a9', 'color': '#1f6e2f', 'weight': 2, 'fillOpacity': 0.1}).add_to(my_map)

    for _, row in sawmill_data.iterrows():
        # FIX THE NaN BUG HERE!
        if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
            select_url = url_for('one_sawmill', sawmill_id=str(row['sawmill_id']).strip())
            popup_html = f'<a href="{select_url}" target="_top">Select {row["sawmill_name"]}</a>'
            folium.Marker([row['Latitude'], row['Longitude']], popup=popup_html, tooltip=row['sawmill_name']).add_to(my_map)
    map_html = my_map._repr_html_()

    raw_sawmill_id = request.args.get("sawmill_id")
    if raw_sawmill_id:
        # Strip the ID for the GET request too!
        sawmill_id = str(raw_sawmill_id).strip()
        sawmill_row = sawmill_data[sawmill_data["sawmill_id"] == sawmill_id]
        if not sawmill_row.empty:
            selected_sawmill = sawmill_row.iloc[0].to_dict()
            
            # Calculate Default Ratio from Demand
            s_dem = selected_sawmill.get('softwood_demand', 0) or 0
            h_dem = selected_sawmill.get('hardwood_demand', 0) or 0
            if (s_dem + h_dem) > 0:
                default_softwood_ratio = int((s_dem / (s_dem + h_dem)) * 100)

            logging_sites = _get_potential_sites_for_sawmill(sawmill_id)

    return render_template(
        "one_sawmill.html",
        selected_sawmill=selected_sawmill,
        logging_sites=logging_sites,
        map_html=map_html,
        default_softwood_ratio=default_softwood_ratio 
    )
# --- MULTI SAWMILL ROUTE (FIXED) ---
@app.route("/multi_sawmill", methods=["GET", "POST"])
@login_required
def multi_sawmill():
    if request.method == "POST":
        # 1. Collect Data & Clean IDs
        raw_sawmill_ids = request.form.getlist("sawmills")
        if not raw_sawmill_ids:
            flash("Please select at least one sawmill.", "error")
            return redirect(url_for("multi_sawmill"))

        # CLEAN IDs to prevent Pandas from dropping sawmills
        sawmill_ids = [str(sid).strip() for sid in raw_sawmill_ids]

        ls_source = request.form.get("ls_source", "database")
        unload = float(request.form.get("unload_mean_time", 15))
        scale_in = float(request.form.get("scale_in_time", 1))
        scale_out = float(request.form.get("scale_out_time", 1))
        wait_area = int(request.form.get("truck_waiting_area", 40))
        breakdown = request.form.get("breakdown_type", "none")
        breakdown_gap = int(request.form.get("breakdown_gap", 1))
        total_days = int(request.form.get("simulation_days", 1))

        input_params = {
            "unload_mean_time": unload, "scale_in_time": scale_in,
            "scale_out_time": scale_out, "truck_waiting_area": wait_area,
            "breakdown_type": breakdown, "breakdown_gap": breakdown_gap,
        }

        # 2. Filter Sawmills Safely
        sd_copy = sawmill_data.copy()
        sd_copy['clean_id'] = sd_copy['sawmill_id'].astype(str).str.strip()
        sd = sd_copy[sd_copy["clean_id"].isin(sawmill_ids)].copy()
        sd['sawmill_id'] = sd['clean_id'] # Override to guarantee clean match downstream
        
        sd.loc[:, "unload_time_mean"] = unload
        sd.loc[:, "scale_in_time"] = scale_in
        sd.loc[:, "scale_out_time"] = scale_out
        sd.loc[:, "truck_area_capacity"] = wait_area

        # --- DATA SOURCE BRANCHING LOGIC ---
        if ls_source == 'generated':
            # A. Load Generated Sites (Must pull from individual SM session keys!)
            gen_sites = []
            for sid in sawmill_ids:
                sites_for_mill = session.get(f"logging_sites_{sid}", [])
                gen_sites.extend(sites_for_mill)
                
            active_logging_sites = pd.DataFrame(gen_sites)

            # B. Create Dummy Companies and Trucks for Generated Sites
            comp_list = []
            truck_list = []
            t_idx = 1
            for site in gen_sites:
                cid = site.get('company_id', f"{site['site_id']}_CO")
                comp_list.append({
                    'company_id': cid,
                    'company_name': f"Company {cid}",
                    'logging_site': site['site_id'],
                    'num_trucks': 13,
                    'mean_truck_generate_interval': 0.000001,
                    'sawmill': site['sawmill']
                })
                for _ in range(13):
                    truck_list.append({'truck_id': f"TRK_GEN_{t_idx}", 'company_id': cid, 'truck_capacity': 25})
                    t_idx += 1
            
            active_companies = pd.DataFrame(comp_list)
            all_trucks = pd.DataFrame(truck_list)
            
        else:
            # --- USER'S ORIGINAL STATIC DATABASE LOGIC ---
            # 3. Assign Logging Sites (Demand-Based)
            all_sawmill_rows = [row for row in sd.itertuples()]
            assigned_logging_site_data = logging_site_data.copy()
            
            site_assignments = {}
            for row in logging_site_data.itertuples():
                ls_dict = row._asdict()
                ls_id = str(ls_dict['site_id'])
                ls_spec = str(ls_dict.get('species', 'mixed')).lower()
                ls_is_soft = 'soft' in ls_spec or 'mixed' in ls_spec
                ls_is_hard = 'hard' in ls_spec or 'mixed' in ls_spec
                best_sm_id = None
                min_score = float('inf') 
                for sm in all_sawmill_rows:
                    if not _check_compatibility(ls_dict, sm): continue
                    dist = _get_travel_time(str(sm.sawmill_id), ls_id)
                    if dist == float('inf'): continue
                    s_dem = getattr(sm, 'softwood_demand', 0) or 0
                    h_dem = getattr(sm, 'hardwood_demand', 0) or 0
                    relevant_demand = 0
                    if ls_is_soft: relevant_demand += s_dem
                    if ls_is_hard: relevant_demand += h_dem
                    if relevant_demand <= 0: relevant_demand = 1 
                    score = dist / relevant_demand
                    if score < min_score: min_score = score; best_sm_id = str(sm.sawmill_id)
                site_assignments[ls_id] = best_sm_id
            
            assigned_logging_site_data['sawmill'] = assigned_logging_site_data['site_id'].map(site_assignments)

            # Consolidate Sites
            all_ls_frames = [assigned_logging_site_data[assigned_logging_site_data["sawmill"].isin(sawmill_ids)]]
            for sid in sawmill_ids:
                session_ls = pd.DataFrame(session.get(f"logging_sites_{sid}", []))
                if not session_ls.empty:
                    if 'sawmill' not in session_ls.columns: session_ls['sawmill'] = sid
                    all_ls_frames.append(session_ls)
            active_logging_sites = pd.concat(all_ls_frames, ignore_index=True).drop_duplicates(subset="site_id")

            # 4. Companies & Trucks
            assigned_company_data = company_data.copy()
            if 'sawmill' not in assigned_company_data.columns:
                site_to_sm_map = dict(zip(assigned_logging_site_data['site_id'], assigned_logging_site_data['sawmill']))
                assigned_company_data['sawmill'] = assigned_company_data['logging_site'].map(site_to_sm_map)
            base_companies = assigned_company_data[assigned_company_data["sawmill"].isin(sawmill_ids)]
            session_companies = pd.DataFrame(session.get("company_data", []))
            active_companies = pd.concat([base_companies, session_companies], ignore_index=True)
            valid_site_ids = active_logging_sites['site_id'].tolist()
            active_companies = active_companies[active_companies['logging_site'].isin(valid_site_ids)].drop_duplicates(subset="company_id")

            # Safety Net (Companies)
            existing_served_sites = set(active_companies['logging_site'].tolist())
            orphaned_sites = [s for s in valid_site_ids if s not in existing_served_sites]
            if orphaned_sites:
                safety_companies = []
                for site_id in orphaned_sites:
                    sm_id = active_logging_sites.loc[active_logging_sites['site_id'] == site_id, 'sawmill'].values[0]
                    if pd.isna(sm_id): continue 
                    safety_companies.append({'company_id': f"AUTO_CO_{site_id}", 'company_name': f"Auto Co {site_id}", 'sawmill': sm_id, 'logging_site': site_id, 'num_trucks': 13, 'mean_truck_generate_interval': 0.000001})
                active_companies = pd.concat([active_companies, pd.DataFrame(safety_companies)], ignore_index=True)

            active_company_ids = active_companies["company_id"].tolist()
            base_trucks = truck_data[truck_data["company_id"].isin(active_company_ids)]
            session_trucks = pd.DataFrame(session.get("truck_data", []))
            if not session_trucks.empty: session_trucks = session_trucks[session_trucks["company_id"].isin(active_company_ids)]
            all_trucks = pd.concat([base_trucks, session_trucks], ignore_index=True).drop_duplicates(subset="truck_id")

            # Safety Net (Trucks)
            existing_truck_companies = set(all_trucks['company_id'].tolist())
            orphaned_companies = [c for c in active_company_ids if c not in existing_truck_companies]
            if orphaned_companies:
                safety_trucks = []
                for cid in orphaned_companies:
                    for t in range(1, 14): safety_trucks.append({'truck_id': f"{cid}_T{t}", 'company_id': cid, 'truck_capacity': 25})
                all_trucks = pd.concat([all_trucks, pd.DataFrame(safety_trucks)], ignore_index=True)

        # 5. Travel Times (Dynamically handles missing route KeyErrors)
        base_travel = travel_times_data
        new_travel = pd.DataFrame(session.get("new_travel_times", []))
        
        active_travel_times = pd.concat([base_travel, new_travel], ignore_index=True)
        if active_travel_times.empty:
            active_travel_times = pd.DataFrame(columns=['Sawmill', 'LoggingSite', 'Total_TruckTravelTime'])
            
        active_travel_times['Sawmill'] = active_travel_times['Sawmill'].astype(str)
        active_travel_times['LoggingSite'] = active_travel_times['LoggingSite'].astype(str)
        existing_pairs = set(zip(active_travel_times['Sawmill'], active_travel_times['LoggingSite']))
        
        missing_travel_rows = []
        for _, row in active_logging_sites.iterrows():
            s_id = str(row['sawmill'])
            l_id = str(row['site_id'])
            if pd.isna(s_id) or s_id == 'None': continue
            if (s_id, l_id) not in existing_pairs:
                t_time = row.get('travel_time', 60.0)
                if pd.isna(t_time): t_time = 60.0
                missing_travel_rows.append({'Sawmill': s_id, 'LoggingSite': l_id, 'Total_TruckTravelTime': float(t_time)})
                
        if missing_travel_rows: 
            active_travel_times = pd.concat([active_travel_times, pd.DataFrame(missing_travel_rows)], ignore_index=True)

        # 6. Run Simulation
        number_of_replications = 10
        with mp.Pool(mp.cpu_count()) as pool:
            replications = pool.starmap(run_replication, [(i, total_days, active_logging_sites, sd, sd, active_companies, all_trucks, active_travel_times, breakdown, breakdown_gap, unload, scale_in, scale_out, wait_area) for i in range(number_of_replications)])

        avg_result = aggregate_and_average_results(replications, number_of_replications)

        # 7. Process Results
        full_days = total_days - 1
        total_sim_time = full_days * 1440 + 1245
        if total_sim_time <= 0: total_sim_time = 1
        os.makedirs("static/plots", exist_ok=True)
        
        for key in ["scale_in_wait_times", "truck_wait_time_in_crane", "truck_turn_time_in_sawmill", "crane1_idle_time", "crane2_idle_time", "avg_wait_time_scalein", "avg_wait_time_crane", "avg_turn_time", "crane1_utilization", "crane2_utilization", "sawmill_queue_lengths", "crane1_unloading_time", "crane2_unloading_time", "sawmill_queue_times", "sawmill_queue_lengths_ts"]:
            avg_result.setdefault(key, {})
            
        for sid in sawmill_ids:
            s_scale_in = avg_result["scale_in_wait_times"].get(sid, [])
            s_crane = avg_result["truck_wait_time_in_crane"].get(sid, [])
            s_turn = avg_result["truck_turn_time_in_sawmill"].get(sid, [])
            c1_idle = avg_result["crane1_idle_time"].get(sid, [])
            c2_idle = avg_result["crane2_idle_time"].get(sid, [])

            avg_result["avg_wait_time_scalein"][sid] = float(np.mean(s_scale_in)) if s_scale_in else 0.0
            avg_result["avg_wait_time_crane"][sid] = float(np.mean(s_crane)) if s_crane else 0.0
            avg_result["avg_turn_time"][sid] = float(np.mean(s_turn)) if s_turn else 0.0
            avg_result["crane1_utilization"][sid] = 1.0 - (sum(c1_idle) / total_sim_time if c1_idle else 0.0)
            avg_result["crane2_utilization"][sid] = 1.0 - (sum(c2_idle) / total_sim_time if c2_idle else 0.0)

            # Generate Plots
            save_plot(s_scale_in, "Scale In Wait Time", "Minutes", f"{sid}_scale_in_wait.png")
            save_plot(s_crane, "Crane Wait Time", "Minutes", f"{sid}_crane_wait_time.png")
            save_plot(avg_result["sawmill_queue_lengths"].get(sid, []), "Queue Lengths", "Trucks", f"{sid}_queue_lengths.png")
            save_plot(avg_result["crane1_idle_time"].get(sid, []), "Crane 1 Idle Time", "Minutes", f"{sid}_crane1_idle.png", "g")
            save_plot(avg_result["crane1_unloading_time"].get(sid, []), "Crane 1 Unload Time", "Minutes", f"{sid}_crane1_unload.png", "r")
            save_plot(avg_result["crane2_idle_time"].get(sid, []), "Crane 2 Idle Time", "Minutes", f"{sid}_crane2_idle.png", "g")
            save_plot(avg_result["crane2_unloading_time"].get(sid, []), "Crane 2 Unload Time", "Minutes", f"{sid}_crane2_unload.png", "r")
            save_plot(s_turn, "Truck Turn Time", "Minutes", f"{sid}_turn_time.png", "r")
            save_dual_series_plot(avg_result["crane1_idle_time"].get(sid, []), avg_result["crane1_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 1 — idle & unloading", "Minutes", f"{sid}_crane1_duo.png")
            save_dual_series_plot(avg_result["crane2_idle_time"].get(sid, []), avg_result["crane2_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 2 — idle & unloading", "Minutes", f"{sid}_crane2_duo.png")
            save_time_series_plot(avg_result["sawmill_queue_times"].get(sid, []), avg_result["sawmill_queue_lengths_ts"].get(sid, []), title="Waiting Area Queue Length vs Time", ylabel="Queue Length (no of trucks)", filename=f"{sid}_queue_len_vs_time.png")

        # --- PREPARE DATA FOR TEMPLATE ---
        sawmill_names = {}
        sawmill_details = {}
        results_by_sawmill = {}

        for _, row in sd.iterrows():
            sid = str(row['sawmill_id'])
            sawmill_names[sid] = row['sawmill_name']
            
            sawmill_details[sid] = {
                'name': row['sawmill_name'],
                'soft_demand': row.get('softwood_demand', 0),
                'hard_demand': row.get('hardwood_demand', 0),
                'species': row.get('species', 'Mixed')
            }
            results_by_sawmill[sid] = avg_result

        return render_template(
            "multi_results.html",
            avg_result=results_by_sawmill,
            sawmill_names=sawmill_names,
            sawmill_details=sawmill_details,
            total_days=total_days,
            number_of_replications=number_of_replications,
            total_sawmills=len(sawmill_ids),
            total_logging_sites=len(active_logging_sites),
            input_params=input_params,
            logging_sites=active_logging_sites.to_dict(orient="records")
        )

    # --- GET Request ---
    first = sawmill_data.iloc[0].to_dict()
    default_values = {
        "unload_mean_time": first["unload_time_mean"],
        "scale_in_time": first["scale_in_time"],
        "scale_out_time": first["scale_out_time"],
        "truck_waiting_area": first["truck_area_capacity"],
        "breakdown_type": first.get("breakdown_type", "none"),
    }
    sawmills = sawmill_data[["sawmill_id", "sawmill_name", "species"]].to_dict(orient="records")
    map_df = sawmill_data.copy()
    map_df = map_df.rename(columns={"Latitude": "lat", "Longitude": "lng"})
    sawmills_list = map_df[["sawmill_id", "sawmill_name", "lat", "lng", "species"]].to_dict(orient="records")
    ms_geojson_url = url_for("static", filename="data/mississippi.geojson") if os.path.exists(os.path.join(app.static_folder, "data", "mississippi.geojson")) else None

    return render_template("multi_sawmill.html", default_values=default_values, sawmills=sawmills, sawmills_list=sawmills_list, ms_geojson_url=ms_geojson_url)


# --- ALL SAWMILL ROUTE ---
@app.route("/all_sawmill", methods=["GET", "POST"])
@login_required
def all_sawmill():
    if request.method == "POST":
        # 1. Collect Form Data
        ls_source = request.form.get("ls_source", "database")
        unload = float(request.form.get("unload_mean_time", 15))
        scale_in = float(request.form.get("scale_in_time", 1))
        scale_out = float(request.form.get("scale_out_time", 1))
        wait_area = int(request.form.get("truck_waiting_area", 40))
        breakdown = request.form.get("breakdown_type", "none")
        breakdown_gap = int(request.form.get("breakdown_gap", 1))
        total_days = int(request.form.get("simulation_days", 1))

        input_params = {
            "unload_mean_time": unload, "scale_in_time": scale_in,
            "scale_out_time": scale_out, "truck_waiting_area": wait_area,
            "breakdown_type": breakdown, "breakdown_gap": breakdown_gap,
        }

        # 2. Apply parameters
        sd = sawmill_data.copy()
        sd.loc[:, "unload_time_mean"] = unload
        sd.loc[:, "scale_in_time"] = scale_in
        sd.loc[:, "scale_out_time"] = scale_out
        sd.loc[:, "truck_area_capacity"] = wait_area

        # Ensure we use clean, strict string IDs for sawmills
        sd['clean_id'] = sd['sawmill_id'].astype(str).str.strip()
        sd['sawmill_id'] = sd['clean_id']
        sawmill_ids = sd["sawmill_id"].tolist()
        
        # --- DATA SOURCE BRANCHING LOGIC ---
        if ls_source == 'generated':
            # A. Load Generated Sites (Must pull from individual SM session keys)
            gen_sites = []
            for sid in sawmill_ids:
                sites_for_mill = session.get(f"logging_sites_{sid}", [])
                gen_sites.extend(sites_for_mill)
                
            active_logging_sites = pd.DataFrame(gen_sites)

            # B. Create Dummy Companies and Trucks for Generated Sites
            comp_list = []
            truck_list = []
            t_idx = 1
            for site in gen_sites:
                cid = site.get('company_id', f"{site['site_id']}_CO")
                comp_list.append({
                    'company_id': cid,
                    'company_name': f"Company {cid}",
                    'logging_site': site['site_id'],
                    'num_trucks': 13,
                    'mean_truck_generate_interval': 0.000001,
                    'sawmill': site['sawmill']
                })
                for _ in range(13):
                    truck_list.append({'truck_id': f"TRK_GEN_{t_idx}", 'company_id': cid, 'truck_capacity': 25})
                    t_idx += 1
            
            active_companies = pd.DataFrame(comp_list)
            all_trucks = pd.DataFrame(truck_list)
            
        else:
            # --- USER'S ORIGINAL STATIC DATABASE LOGIC ---
            # 3. Assign Logging Sites (Demand-Based Logic)
            all_sawmill_rows = [row for row in sd.itertuples()] 
            assigned_logging_site_data = logging_site_data.copy()
            
            site_assignments = {}
            for row in logging_site_data.itertuples():
                ls_dict = row._asdict()
                ls_id = str(ls_dict['site_id'])
                
                ls_spec = str(ls_dict.get('species', 'mixed')).lower()
                ls_is_soft = 'soft' in ls_spec or 'mixed' in ls_spec
                ls_is_hard = 'hard' in ls_spec or 'mixed' in ls_spec

                best_sm_id = None
                min_score = float('inf')
                
                for sm in all_sawmill_rows:
                    if not _check_compatibility(ls_dict, sm): continue
                    dist = _get_travel_time(str(sm.sawmill_id), ls_id)
                    if dist == float('inf'): continue

                    s_dem = getattr(sm, 'softwood_demand', 0) or 0
                    h_dem = getattr(sm, 'hardwood_demand', 0) or 0
                    relevant_demand = 0
                    if ls_is_soft: relevant_demand += s_dem
                    if ls_is_hard: relevant_demand += h_dem
                    if relevant_demand <= 0: relevant_demand = 1 

                    score = dist / relevant_demand
                    if score < min_score:
                        min_score = score
                        best_sm_id = str(sm.sawmill_id)
                site_assignments[ls_id] = best_sm_id
                
            assigned_logging_site_data['sawmill'] = assigned_logging_site_data['site_id'].map(site_assignments)

            # Consolidate Sites
            all_ls_frames = [assigned_logging_site_data[assigned_logging_site_data["sawmill"].isin(sawmill_ids)]]
            for sid in sawmill_ids:
                session_ls = pd.DataFrame(session.get(f"logging_sites_{sid}", []))
                if not session_ls.empty:
                    if 'sawmill' not in session_ls.columns: session_ls['sawmill'] = sid
                    all_ls_frames.append(session_ls)
            
            active_logging_sites = pd.concat(all_ls_frames, ignore_index=True).drop_duplicates(subset="site_id")
            
            # 4. Consolidate Companies & Trucks with Safety Net
            assigned_company_data = company_data.copy()
            if 'sawmill' not in assigned_company_data.columns:
                site_to_sm_map = dict(zip(assigned_logging_site_data['site_id'], assigned_logging_site_data['sawmill']))
                assigned_company_data['sawmill'] = assigned_company_data['logging_site'].map(site_to_sm_map)

            base_companies = assigned_company_data[assigned_company_data["sawmill"].isin(sawmill_ids)]
            session_companies = pd.DataFrame(session.get("company_data", []))
            active_companies = pd.concat([base_companies, session_companies], ignore_index=True)
            
            valid_site_ids = active_logging_sites['site_id'].tolist()
            active_companies = active_companies[active_companies['logging_site'].isin(valid_site_ids)].drop_duplicates(subset="company_id")

            existing_served_sites = set(active_companies['logging_site'].tolist())
            orphaned_sites = [s for s in valid_site_ids if s not in existing_served_sites]
            if orphaned_sites:
                safety_companies = []
                for site_id in orphaned_sites:
                    sm_id = active_logging_sites.loc[active_logging_sites['site_id'] == site_id, 'sawmill'].values[0]
                    if pd.isna(sm_id): continue 
                    safety_companies.append({
                        'company_id': f"AUTO_CO_{site_id}", 'company_name': f"Auto Co {site_id}",
                        'sawmill': sm_id, 'logging_site': site_id, 'num_trucks': 13, 'mean_truck_generate_interval': 0.000001
                    })
                active_companies = pd.concat([active_companies, pd.DataFrame(safety_companies)], ignore_index=True)

            active_company_ids = active_companies["company_id"].tolist()
            
            base_trucks = truck_data[truck_data["company_id"].isin(active_company_ids)]
            session_trucks = pd.DataFrame(session.get("truck_data", []))
            if not session_trucks.empty:
                session_trucks = session_trucks[session_trucks["company_id"].isin(active_company_ids)]
            all_trucks = pd.concat([base_trucks, session_trucks], ignore_index=True).drop_duplicates(subset="truck_id")

            existing_truck_companies = set(all_trucks['company_id'].tolist())
            orphaned_companies = [c for c in active_company_ids if c not in existing_truck_companies]
            if orphaned_companies:
                safety_trucks = []
                for cid in orphaned_companies:
                    for t in range(1, 14): 
                        safety_trucks.append({'truck_id': f"{cid}_T{t}", 'company_id': cid, 'truck_capacity': 25})
                all_trucks = pd.concat([all_trucks, pd.DataFrame(safety_trucks)], ignore_index=True)

        # 5. Travel Times & Safety Net (Dynamically handles missing route KeyErrors)
        base_travel = travel_times_data
        new_travel = pd.DataFrame(session.get("new_travel_times", []))
        
        active_travel_times = pd.concat([base_travel, new_travel], ignore_index=True)
        if active_travel_times.empty:
            active_travel_times = pd.DataFrame(columns=['Sawmill', 'LoggingSite', 'Total_TruckTravelTime'])

        active_travel_times['Sawmill'] = active_travel_times['Sawmill'].astype(str)
        active_travel_times['LoggingSite'] = active_travel_times['LoggingSite'].astype(str)
        existing_pairs = set(zip(active_travel_times['Sawmill'], active_travel_times['LoggingSite']))

        missing_travel_rows = []
        for _, row in active_logging_sites.iterrows():
            s_id = str(row['sawmill'])
            l_id = str(row['site_id'])
            if pd.isna(s_id) or s_id == 'None': continue
            if (s_id, l_id) not in existing_pairs:
                t_time = row.get('travel_time', 60.0)
                if pd.isna(t_time): t_time = 60.0
                missing_travel_rows.append({'Sawmill': s_id, 'LoggingSite': l_id, 'Total_TruckTravelTime': float(t_time)})
                
        if missing_travel_rows:
            active_travel_times = pd.concat([active_travel_times, pd.DataFrame(missing_travel_rows)], ignore_index=True)

        # 6. Run Simulation
        number_of_replications = 10
        with mp.Pool(mp.cpu_count()) as pool:
            replications = pool.starmap(
                run_replication,
                [
                    (
                        i, total_days, active_logging_sites, sd, sd, 
                        active_companies, all_trucks, active_travel_times, 
                        breakdown, breakdown_gap, unload, scale_in, scale_out, wait_area
                    )
                    for i in range(number_of_replications)
                ],
            )

        avg_result = aggregate_and_average_results(replications, number_of_replications)

        # 7. Process Results
        full_days = total_days - 1
        total_sim_time = full_days * 1440 + 1245
        if total_sim_time <= 0: total_sim_time = 1
        os.makedirs("static/plots", exist_ok=True)
        
        for key in ["scale_in_wait_times", "truck_wait_time_in_crane", "truck_turn_time_in_sawmill", "crane1_idle_time", "crane2_idle_time", "avg_wait_time_scalein", "avg_wait_time_crane", "avg_turn_time", "crane1_utilization", "crane2_utilization", "sawmill_queue_lengths", "crane1_unloading_time", "crane2_unloading_time", "sawmill_queue_times", "sawmill_queue_lengths_ts"]:
            avg_result.setdefault(key, {})
            
        for sid in sawmill_ids:
            s_scale_in = avg_result["scale_in_wait_times"].get(sid, [])
            s_crane = avg_result["truck_wait_time_in_crane"].get(sid, [])
            s_turn = avg_result["truck_turn_time_in_sawmill"].get(sid, [])
            c1_idle = avg_result["crane1_idle_time"].get(sid, [])
            c2_idle = avg_result["crane2_idle_time"].get(sid, [])

            avg_result["avg_wait_time_scalein"][sid] = float(np.mean(s_scale_in)) if s_scale_in else 0.0
            avg_result["avg_wait_time_crane"][sid] = float(np.mean(s_crane)) if s_crane else 0.0
            avg_result["avg_turn_time"][sid] = float(np.mean(s_turn)) if s_turn else 0.0
            avg_result["crane1_utilization"][sid] = 1.0 - (sum(c1_idle) / total_sim_time if c1_idle else 0.0)
            avg_result["crane2_utilization"][sid] = 1.0 - (sum(c2_idle) / total_sim_time if c2_idle else 0.0)

            save_plot(s_scale_in, "Scale In Wait Time", "Minutes", f"{sid}_scale_in_wait.png")
            save_plot(s_crane, "Crane Wait Time", "Minutes", f"{sid}_crane_wait_time.png")
            save_plot(avg_result["sawmill_queue_lengths"].get(sid, []), "Queue Lengths", "Trucks", f"{sid}_queue_lengths.png")
            save_plot(avg_result["crane1_idle_time"].get(sid, []), "Crane 1 Idle Time", "Minutes", f"{sid}_crane1_idle.png", "g")
            save_plot(avg_result["crane1_unloading_time"].get(sid, []), "Crane 1 Unload Time", "Minutes", f"{sid}_crane1_unload.png", "r")
            save_plot(avg_result["crane2_idle_time"].get(sid, []), "Crane 2 Idle Time", "Minutes", f"{sid}_crane2_idle.png", "g")
            save_plot(avg_result["crane2_unloading_time"].get(sid, []), "Crane 2 Unload Time", "Minutes", f"{sid}_crane2_unload.png", "r")
            save_plot(s_turn, "Truck Turn Time", "Minutes", f"{sid}_turn_time.png", "r")
            save_dual_series_plot(avg_result["crane1_idle_time"].get(sid, []), avg_result["crane1_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 1 — idle & unloading", "Minutes", f"{sid}_crane1_duo.png")
            save_dual_series_plot(avg_result["crane2_idle_time"].get(sid, []), avg_result["crane2_unloading_time"].get(sid, []), "Idle", "Unloading", "Crane 2 — idle & unloading", "Minutes", f"{sid}_crane2_duo.png")
            save_time_series_plot(avg_result["sawmill_queue_times"].get(sid, []), avg_result["sawmill_queue_lengths_ts"].get(sid, []), title="Waiting Area Queue Length vs Time", ylabel="Queue Length (no of trucks)", filename=f"{sid}_queue_len_vs_time.png")

        sawmill_names = {row["sawmill_id"]: row["sawmill_name"] for _, row in sd.iterrows()}
        avg_result_for_template = {sid: avg_result for sid in sawmill_names.keys()}

        return render_template(
            "all_results.html",
            avg_result=avg_result_for_template,
            sawmill_names=sawmill_names,
            total_days=total_days,
            number_of_replications=number_of_replications,
            total_sawmills=len(sawmill_names),
            total_logging_sites=len(active_logging_sites),
            input_params=input_params,
        )

    # --- GET Request ---
    first = sawmill_data.iloc[0].to_dict()
    default_values = {
        "unload_mean_time": first["unload_time_mean"],
        "scale_in_time": first["scale_in_time"],
        "scale_out_time": first["scale_out_time"],
        "truck_waiting_area": first["truck_area_capacity"],
        "breakdown_type": first.get("breakdown_type", "none"),
    }
    sawmills_list = sawmill_data[["sawmill_id", "sawmill_name"]].to_dict(orient="records")
    map_center = [32.815, -89.717]
    my_map = folium.Map(location=map_center, zoom_start=6.5)
    mississippi_geojson_path = "data/mississippi.geojson"
    if os.path.exists(mississippi_geojson_path):
        folium.GeoJson(mississippi_geojson_path, style_function=lambda x: {'fillColor': '#a9d6a9', 'color': '#1f6e2f', 'weight': 2, 'fillOpacity': 0.1}).add_to(my_map)
    for _, row in sawmill_data.iterrows():
        folium.Marker([row['Latitude'], row['Longitude']], tooltip=row['sawmill_name']).add_to(my_map)
    map_html = my_map._repr_html_()
    ms_geojson_url = url_for("static", filename="data/mississippi.geojson") if os.path.exists(os.path.join(app.static_folder, "data", "mississippi.geojson")) else None

    return render_template(
        "all_sawmill.html",
        default_values=default_values,
        map_html=map_html,
        sawmills_list=sawmills_list,
        ms_geojson_url=ms_geojson_url
    )


@app.template_filter("minute_to_time")
def minute_to_time(minutes):
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    return f"{hours:02d}:{mins:02d}"


@app.route("/update_single_logging_site", methods=["POST"])
@login_required
def update_single_logging_site():
    data = request.get_json()
    sawmill_id = data.get("sawmill")
    site_id_to_update = data.get("site_id")

    if not sawmill_id or not site_id_to_update:
        return jsonify({"error": "Missing sawmill or site_id from request"}), 400

    session_key = f"logging_sites_{sawmill_id}"
    if session_key not in session:
        return jsonify({"error": "Session data not found for this sawmill"}), 404

    current_sites = session[session_key]
    for site in current_sites:
        if str(site.get("site_id")) == str(site_id_to_update):
            site["avg_loading_time"] = float(data["avg_loading_time"])
            site["opening_time"] = int(data["opening_time"])
            site["closing_time"] = int(data["closing_time"])
            site["initial_log_capacity"] = int(data["initial_log_capacity"])
            
            # --- UPDATED FIELDS ---
            site["species"] = str(data.get("species", "mixed"))
            site["type"] = str(data.get("type", "other"))
            # ----------------------

            session[session_key] = current_sites
            session.modified = True
            return jsonify(success=True)

    return jsonify({"error": "Site ID not found in session for this sawmill"}), 404

@app.route("/delete_logging_site", methods=["POST"])
@login_required
def delete_logging_site():
    data = request.get_json()
    # Force string conversion to avoid int/float mismatch
    site_id = str(data.get("site_id")).strip()
    sawmill_id = str(data.get("sawmill_id")).strip()

    if not site_id or not sawmill_id:
        return jsonify({"error": "Missing site_id or sawmill_id"}), 400

    # 1. Add to Blacklist (The "Nuclear" Option)
    # This prevents the site from ever being loaded from Excel again
    session_deleted_key = f"deleted_sites_{sawmill_id}"
    session.setdefault(session_deleted_key, [])
    
    # Avoid duplicates
    if site_id not in session[session_deleted_key]:
        session[session_deleted_key].append(site_id)

    # 2. Remove from Active Session List (if it was a new site)
    session_key = f"logging_sites_{sawmill_id}"
    if session_key in session:
        current_sites = session[session_key]
        session[session_key] = [s for s in current_sites if str(s.get("site_id")).strip() != site_id]

    # 3. Cleanup Companies (Session only)
    if "company_data" in session:
        session["company_data"] = [
            c for c in session["company_data"] 
            if str(c.get("company_id")).strip() != site_id and str(c.get("logging_site")).strip() != site_id
        ]

    # 4. Cleanup Trucks (Session only)
    if "truck_data" in session:
        session["truck_data"] = [
            t for t in session["truck_data"] 
            if str(t.get("company_id")).strip() != site_id
        ]

    # 5. Cleanup Travel Times (Session only)
    if "new_travel_times" in session:
        session["new_travel_times"] = [
            tt for tt in session["new_travel_times"]
            if str(tt.get("LoggingSite")).strip() != site_id
        ]

    session.modified = True
    return jsonify({"message": "Deleted"}), 200


@app.route("/update_logging_sites", methods=["POST"])
@login_required
def update_logging_sites():
    data = request.get_json()
    sawmill_id = data["sawmill_id"]

    # Save logging sites
    session[f"logging_sites_{sawmill_id}"] = data["logging_sites"]

    # Save travel time data (merge)
    if "travel_times" in data:
        current_tt = session.get("travel_times_data", {})
        for src, targets in data["travel_times"].items():
            current_tt.setdefault(src, {}).update(targets)
        session["travel_times_data"] = current_tt

    # Save trucks for session (append)
    if "trucks" in data:
        existing_trucks = session.get("truck_data", [])
        existing_trucks.extend(data["trucks"])
        session["truck_data"] = existing_trucks

    session.modified = True
    return "", 204


@app.route('/update_all_logging_sites', methods=['POST'])
@login_required
def update_all_logging_sites():
    try:
        data = request.get_json()
        sawmill_id = data.get('sawmill_id')
        updated_sites = data.get('logging_sites', [])

        if not sawmill_id:
            return jsonify({"status": "error", "error": "Sawmill ID missing"}), 400

        session_key = f"generated_sites_{sawmill_id}"
        
        # 1. Update the Session (For dynamically generated sites)
        # Overwriting the session entirely handles both Edits AND Deletions
        session[session_key] = updated_sites
        session.modified = True

        # 2. (Optional) If you want to update the master DB dataframe as well:
        global logging_site_data
        for site_info in updated_sites:
            s_id = site_info['site_id']
            # If the site exists in the master list, update its values
            if s_id in logging_site_data['site_id'].values:
                idx = logging_site_data.index[logging_site_data['site_id'] == s_id].tolist()[0]
                logging_site_data.at[idx, 'avg_loading_time'] = site_info['avg_loading_time']
                logging_site_data.at[idx, 'opening_time'] = site_info['opening_time']
                logging_site_data.at[idx, 'closing_time'] = site_info['closing_time']
                logging_site_data.at[idx, 'initial_log_capacity'] = site_info['initial_log_capacity']
                logging_site_data.at[idx, 'hardwood_amount'] = site_info['hardwood_amount']
                logging_site_data.at[idx, 'softwood_amount'] = site_info['softwood_amount']

        return jsonify({"status": "success", "message": "Logging sites updated."}), 200

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    
    
@app.route("/add_logging_site", methods=["POST"])
@login_required
def add_logging_site():
    data = request.get_json()
    if not data: return jsonify({"error": "No data"}), 400

    site_id = data.get("site_id")
    sawmill_id = data.get("sawmill_id")
    
    # 1. Logic to create the new site object
    new_site = {
        "site_id": site_id,
        "company_id": site_id, # Simplified 1-to-1 mapping
        "avg_loading_time": float(data.get("avg_loading_time") or 15.0),
        "opening_time": int(data.get("opening_time") or 360),
        "closing_time": int(data.get("closing_time") or 960),
        "initial_log_capacity": int(data.get("initial_log_capacity") or 200000),
        "hardwood_amount": int(data.get("hardwood_amount") or 0),
        "softwood_amount": int(data.get("softwood_amount") or 0),
        "travel_time": float(data.get("travel_time_to_sawmill") or 0),
        "sawmill": sawmill_id,
        
        # SAVE THE NEW FIELDS
        "species": data.get("species"),
        "type": data.get("type")
    }

    # 2. Save to Session (Generated List)
    session_key = f"generated_sites_{sawmill_id}"
    
    # Initialize list if it doesn't exist
    if session_key not in session:
        session[session_key] = []
        
    # Check duplicate
    if any(s["site_id"] == site_id for s in session[session_key]):
        return jsonify({"error": "Site ID already exists"}), 400
        
    session[session_key].append(new_site)
    session.modified = True

    return jsonify({"message": "Site added successfully!"})

# -----------------------------------------------------------------------------
# About/Contact
# -----------------------------------------------------------------------------
@app.route("/about")
def about_simulation():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# -----------------------------------------------------------------------------
# PDF Helpers & Routes
# -----------------------------------------------------------------------------
RESULTS_PDF_DIR = Path(app.root_path) / "results_pdfs"
RESULTS_PDF_DIR.mkdir(parents=True, exist_ok=True)


def _make_filename(tag: str):
    """Create a sanitized, timestamped filename."""
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", tag or "results")
    return f"{safe}_{ts}.pdf"


def get_pdfkit_config():
    """
    Find wkhtmltopdf executable and build a pdfkit configuration.
    On Windows, returns None if not found (caller handles gracefully).
    """
    env_path = os.getenv("WKHTMLTOPDF_PATH")
    if env_path and Path(env_path).exists():
        return pdfkit.configuration(wkhtmltopdf=env_path)

    which = shutil.which("wkhtmltopdf")
    if which:
        return pdfkit.configuration(wkhtmltopdf=which)

    if platform.system() == "Windows":
        guesses = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        ]
        for g in guesses:
            if Path(g).exists():
                return pdfkit.configuration(wkhtmltopdf=g)

    return None


@app.route("/save_results_pdf_client", methods=["POST"])
@login_required
def save_results_pdf_client():
    html = request.form.get("html", "")
    tag = request.form.get("tag", "results")

    username = session.get("username")
    if not username:
        flash("Could not identify user. Please log in again.", "error")
        return redirect(url_for("results_dashboard"))

    if not html.strip():
        flash("Nothing to save: empty HTML.", "error")
        return redirect(url_for("results_dashboard"))

    user_pdf_dir = RESULTS_PDF_DIR / username
    user_pdf_dir.mkdir(parents=True, exist_ok=True)
    outfile = user_pdf_dir / _make_filename(tag)

    options = {"quiet": "", "print-media-type": None, "load-error-handling": "ignore"}
    cfg = get_pdfkit_config()

    if cfg is None and platform.system() == "Windows":
        flash(
            "wkhtmltopdf is not installed or not found. "
            "Install it and/or set WKHTMLTOPDF_PATH to the executable.",
            "error",
        )
        return redirect(url_for("results_dashboard"))

    try:
        if cfg:
            pdfkit.from_string(html, str(outfile), options=options, configuration=cfg)
        else:
            pdfkit.from_string(html, str(outfile), options=options)

        flash(f"Saved to dashboard as {outfile.name}", "success")
        app.logger.info(f"User '{username}' saved PDF -> {outfile}")
    except Exception as e:
        app.logger.exception("PDF save failed: %s", e)
        flash(f"Failed to save PDF: {e}", "error")

    return redirect(url_for("results_dashboard"))


@app.route("/results_dashboard")
@login_required
def results_dashboard():
    pdfs = []
    username = session.get('username')

    # If for some reason there's no username, redirect to login to be safe.
    if not username:
        flash("Your session has expired. Please log in again.", "login")
        return redirect(url_for('login'))

    # Load all users and get the specific info for the logged-in user.
    users = load_users()
    user_info = users.get(username, {})

    # ** KEY UPDATE HERE **
    # Add the username to the user_info dictionary so the template can access it.
    user_info['username'] = username

    # Find and list all PDF files in the user's specific directory.
    user_pdf_dir = RESULTS_PDF_DIR / username
    if user_pdf_dir.is_dir():
        for p in sorted(user_pdf_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
            size = p.stat().st_size
            pdfs.append({
                "filename": p.name,
                "display_name": p.stem.replace('_', ' '),
                "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)),
                "size_readable": (f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"),
            })
            
    # Pass both the list of PDFs and the user's info to the template.
    return render_template("dashboard.html", pdfs=pdfs, user_info=user_info)


@app.route("/results_pdfs/<username>/<path:filename>")
@login_required
def serve_result_pdf(username, filename):
    if "username" not in session or session["username"] != username:
        abort(403)

    user_pdf_dir = RESULTS_PDF_DIR / username
    return send_from_directory(user_pdf_dir, filename, as_attachment=False)


@app.route("/delete_result_pdf", methods=["POST"])
@login_required
def delete_result_pdf():
    filename = request.form.get("filename")
    username = session.get("username")

    if not filename or not username:
        flash("Invalid request. Could not delete file.", "error")
        return redirect(url_for("results_dashboard"))

    user_pdf_dir = RESULTS_PDF_DIR / username
    file_to_delete = user_pdf_dir / filename

    try:
        if not file_to_delete.is_file() or not str(file_to_delete.resolve()).startswith(
            str(user_pdf_dir.resolve())
        ):
            flash("File not found or permission denied.", "error")
            return redirect(url_for("results_dashboard"))

        file_to_delete.unlink()
        flash(f"Successfully deleted report: {filename}", "success")
        app.logger.info(f"User '{username}' deleted PDF: {file_to_delete}")
    except Exception as e:
        flash(f"An error occurred while deleting the file: {e}", "error")
        app.logger.error(
            f"Error deleting file for user '{username}': {file_to_delete}. Error: {e}"
        )

    return redirect(url_for("results_dashboard"))
# In app.py

def save_all_users(users_dict):
    """Saves the entire dictionary of users back to the Excel file."""
    user_list = []
    for uname, data in users_dict.items():
        user_list.append({'username': uname, 'password': data['password'], 'email': data['email']})
    df = pd.DataFrame(user_list)
    df.to_excel(USER_FILE, index=False)


# In app.py, add this new route

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    current_username = session['username']
    users = load_users()
    current_user_data = users[current_username]

    # Get form data
    new_email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # --- Update Email ---
    if new_email and new_email != current_user_data['email']:
        # Check if the new email is already taken by another user
        for username, data in users.items():
            if username != current_username and data['email'] == new_email:
                flash('That email address is already in use.', 'error')
                return redirect(url_for('results_dashboard'))
        users[current_username]['email'] = new_email
        flash('Email updated successfully.', 'success')

    # --- Update Password ---
    if new_password:
        if not current_password or not check_password_hash(current_user_data['password'], current_password):
            flash('Your current password was incorrect.', 'error')
            return redirect(url_for('results_dashboard'))
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('results_dashboard'))
        
        users[current_username]['password'] = generate_password_hash(new_password)
        flash('Password updated successfully.', 'success')

    # Save all changes back to the file
    save_all_users(users)
    return redirect(url_for('results_dashboard'))


# -----------------------------------------------------------------------------
# Main Entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
