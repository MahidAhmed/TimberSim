# TimberSim: Sawmill Logistics Simulation

TimberSim is a data-driven, Flask-based simulation framework designed to model the day-to-day logistics of timber supply chains. Using discrete-event simulation, it analyzes truck routing, logging site output, and sawmill crane utilization, providing dynamic visual dashboards and PDF reporting for performance bottlenecks.

## 🛠️ Tech Stack

**Backend:** Python 3.12.1, Flask 3.1.0 

**Simulation Engine:** SimPy 

**Data Processing:** Pandas, NumPy 

**Visualization:** Matplotlib, Folium 

**Reporting:** PDFKit / wkhtmltopdf 



## 📂 Core Project Structure

**app.py**: The main Flask application handling routing, user authentication, and web interface rendering.

**entities.py**: Defines the primary simulation objects (`LoggingSite`, `Sawmill`, `LoggingCompany`, `Truck`).

**sawmill_model.py**: Contains the core `Model` class that orchestrates the SimPy environment and logic.

**run_replication.py**: Handles multiprocessing for running parallel simulation replications.

**sawmill_utilities.py**: Helper functions for data aggregation and alternative sawmill routing.

**global_variables.py**: Tracks global state and simulation travel metrics.

**data/**: Contains the master `timber_59_sawmill.xlsx` dataset and regional geospatial data (`mississippi.geojson`).



---

## 🚀 Running the Application from GitHub

To run this simulation framework on your local machine, follow these steps:

**1. Clone the repository:**
Download or clone this repository to your local machine using your terminal:

```bash
git clone https://github.com/MahidAhmed/TimberSim.git
cd TimberSim

```

**2. Set up a virtual environment (Recommended):**

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On macOS/Linux

```

**3. Install Dependencies:**
Install the required Python packages using the requirements file:

```bash
pip install -r requirements.txt

```

**4. wkhtmltopdf Dependency (For PDF Generation):**
To generate PDF dashboard results, you must have `wkhtmltopdf` installed on your system.

**Windows:** Ensure it is installed in `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe` or add its executable path to your system's `WKHTMLTOPDF_PATH` environment variable.



**5. Start the Application:**
Once the dependencies are installed, start the Flask application by running:

```bash
python app.py

```

Open your web browser and navigate to `http://localhost:5000` to access the simulation dashboard.
