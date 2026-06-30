from flask import Flask, render_template, request
import pandas as pd
import simpy
import numpy as np
import multiprocessing as mp
import matplotlib.pyplot as plt
import os
# sawmill_model.py
from sawmill_model_org import Model

from sawmill_utilities import add_lists_with_padding, average_elements_with_count
from run_replication import run_replication

app = Flask(__name__)

# Load Data
data = pd.ExcelFile('data/timber_59_sawmill.xlsx')
logging_site_data = pd.read_excel(data, 'LoggingSite')
sawmill_data = pd.read_excel(data, 'Sawmill')
company_data = pd.read_excel(data, 'Company')
truck_data = pd.read_excel(data, 'Truck')
travel_times_data = pd.read_excel(data, 'Travel_times')


@app.route('/', methods=['GET', 'POST'])
def index():
    # sawmills = sawmill_data['sawmill_id'].unique()
    sawmills = sawmill_data[['sawmill_id', 'sawmill_name']]


    if request.method == 'POST':
        # selected_sawmill = request.form['sawmill']
        selected_sawmill = request.form['sawmill'] # Convert string "4" to integer 4

        print(selected_sawmill)
        filtered_sawmill = sawmill_data[sawmill_data['sawmill_id'] == selected_sawmill]

        # Filter datasets for the selected sawmill
        filtered_logging_sites = logging_site_data[logging_site_data['sawmill'] == selected_sawmill]
        print(filtered_logging_sites.head())
        filtered_companies = company_data[company_data['sawmill'] == selected_sawmill]
        filtered_trucks = truck_data[truck_data['company_id'].isin(filtered_companies['company_id'])]

        number_of_replications = 2
        total_days = 7

        # Run multiprocessed simulations
        with mp.Pool(mp.cpu_count()) as pool:
            replication_results = pool.starmap(
                run_replication,
                [(i, total_days, filtered_logging_sites, filtered_sawmill,
                #   sawmill_data[sawmill_data['sawmill_id'] == selected_sawmill], 
                  filtered_companies, filtered_trucks, travel_times_data)
                 for i in range(number_of_replications)]
            )

        from sawmill_utilities import aggregate_and_average_results
        average_result = aggregate_and_average_results(replication_results, number_of_replications)

        # Plotting for selected site and sawmill
        # Create directory for plots
        save_dir = 'static/plots'
        os.makedirs(save_dir, exist_ok=True)

        def plot_and_save(data_list, title, y_label, filename):
            if not data_list or all(v is None or (hasattr(v, '__len__') and len(v) == 0) for v in data_list):
                print(f"[WARNING] Skipping empty plot for: {title}")
                return 
            plt.figure(figsize=(10, 5))
            plt.plot(data_list, marker='.')
            plt.title(title)
            plt.xlabel('Truck Index')
            plt.ylabel(y_label)
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(os.path.join(save_dir, filename))
            plt.close()

        # Plot for each logging site assigned to the selected sawmill
        filtered_sites = logging_site_data[logging_site_data['sawmill'] == selected_sawmill]
        for site_id in filtered_sites['site_id']:
            if site_id in average_result['queue_lengths']:
                plot_and_save(average_result['queue_lengths'][site_id], f'Queue at {site_id}', 'Queue Length', f'queue_{site_id}.png')
            if site_id in average_result['site_wait_time']:
                plot_and_save(average_result['site_wait_time'][site_id], f'Wait at {site_id}', 'Wait Time', f'wait_{site_id}.png')
            if site_id in average_result['total_loading_time']:
                plot_and_save(average_result['total_loading_time'][site_id], f'Loading at {site_id}', 'Loading Time', f'loading_{site_id}.png')
            if site_id in average_result['loader_idle_time']:
                plot_and_save(average_result['loader_idle_time'][site_id], f'Idle at {site_id}', 'Idle Time', f'idle_{site_id}.png')

        # Plot for selected sawmill
        if selected_sawmill in average_result['sawmill_queue_lengths']:
            plot_and_save(average_result['sawmill_queue_lengths'][selected_sawmill], f'Crane Queue at {selected_sawmill}', 'Queue Length', f'queue_sawmill_{selected_sawmill}.png')
        if selected_sawmill in average_result['scale_in_wait_times']:
            plot_and_save(average_result['scale_in_wait_times'][selected_sawmill], f'Scale-in Wait at {selected_sawmill}', 'Wait Time', f'scalein_{selected_sawmill}.png')
        if selected_sawmill in average_result['truck_wait_time_in_crane']:
            plot_and_save(average_result['truck_wait_time_in_crane'][selected_sawmill], f'Crane Wait at {selected_sawmill}', 'Wait Time', f'crane_wait_{selected_sawmill}.png')

        return render_template('results.html',
                               sawmill_id=selected_sawmill,
                               avg_result=average_result,
                               number_of_replications=number_of_replications,
                               total_days=total_days)

    return render_template('index.html', sawmills=sawmills)

if __name__ == '__main__':
    app.run(debug=True)
