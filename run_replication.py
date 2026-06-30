import simpy
from sawmill_model import Model
import global_variables as gb

def run_replication(
    replication_id, total_days,
    logging_site_data, filtered_sawmill, sawmill_data, company_data, truck_data,
    travel_times_data, breakdown_type, breakdown_gap, unload_mean_time, scale_in_time, scale_out_time,
    truck_waiting_area, mtbf=1440, mttr=60
):
    env = simpy.Environment()
    print(f"Replication {replication_id} started.")

    model = Model(
        env, logging_site_data, filtered_sawmill, sawmill_data,
        company_data, truck_data, travel_times_data,
        breakdown_type, breakdown_gap, unload_mean_time, scale_in_time, scale_out_time,
        truck_waiting_area, mtbf, mttr
    )

    full_days = total_days - 1
    total_sim_time = full_days * 1440 + 1245
    # print(f'Total simulation time: {total_sim_time}')

    # Start queue monitor if present
    if hasattr(model, "monitor_scale_in_queues"):
        env.process(model.monitor_scale_in_queues(duration=total_sim_time, every=1.0))

    model.start_simulation(duration=total_sim_time)

    # Build results
    result = {
        # --- Logging site outputs ---
        "loaded_truck_count": {sid: site.loaded_truck_count for sid, site in model.logging_sites.items()},
        "amount_loaded": {sid: site.amount_loaded for sid, site in model.logging_sites.items()},
        "queue_lengths": {sid: site.queue_lengths for sid, site in model.logging_sites.items()},
        "site_wait_time": {sid: site.site_wait_time for sid, site in model.logging_sites.items()},
        "loader_idle_time": {sid: site.loader_idle_time for sid, site in model.logging_sites.items()},
        "total_loading_time": {sid: site.total_loading_time for sid, site in model.logging_sites.items()},
        "truck_turn_time_in_logging_site": {sid: site.truck_turn_time_in_logging_site for sid, site in model.logging_sites.items()},

        # --- Sawmill outputs ---
        "Number_of_Trucks_Unloaded": {smid: sm.Number_of_Trucks_Unloaded for smid, sm in model.sawmills.items()},
        "sawmill_queue_lengths": {smid: sm.sawmill_queue_lengths for smid, sm in model.sawmills.items()},
        "scale_in_wait_times": {smid: sm.scale_in_wait_times for smid, sm in model.sawmills.items()},
        "truck_wait_time_in_crane": {smid: sm.truck_wait_time_in_crane for smid, sm in model.sawmills.items()},
        "truck_departed": {smid: sm.truck_departed for smid, sm in model.sawmills.items()},
        "crane1_idle_time": {smid: sm.crane1_idle_time for smid, sm in model.sawmills.items()},
        "crane1_unloading_time": {smid: sm.crane1_unloading_time for smid, sm in model.sawmills.items()},
        "crane1_over_time": {smid: sm.crane1_over_time for smid, sm in model.sawmills.items()},
        "crane1_processed_truck": {smid: sm.crane1_processed_truck for smid, sm in model.sawmills.items()},
        "crane1_processed_truck_on_overtime": {smid: sm.crane1_processed_truck_on_overtime for smid, sm in model.sawmills.items()},
        "crane2_idle_time": {smid: sm.crane2_idle_time for smid, sm in model.sawmills.items()},
        "crane2_unloading_time": {smid: sm.crane2_unloading_time for smid, sm in model.sawmills.items()},
        "crane2_over_time": {smid: sm.crane2_over_time for smid, sm in model.sawmills.items()},
        "crane2_processed_truck": {smid: sm.crane2_processed_truck for smid, sm in model.sawmills.items()},
        "crane2_processed_truck_on_overtime": {smid: sm.crane2_processed_truck_on_overtime for smid, sm in model.sawmills.items()},
        "truck_turn_time_in_sawmill": {smid: sm.truck_turn_time_in_sawmill for smid, sm in model.sawmills.items()},
        "truck_diverted_from_sawmill": {smid: sm.truck_diverted_from_sawmill for smid, sm in model.sawmills.items()},
        "breakdown_number": {smid: sm.breakdown_number for smid, sm in model.sawmills.items()},
        "missed_breakdown_number": {smid: sm.missed_breakdown for smid, sm in model.sawmills.items()},
        "truck_arrived_per_day": {smid: sm.truck_number_per_day_in_sawmill for smid, sm in model.sawmills.items()},
        
        # --- NEW: Species Metrics ---
        "softwood_received": {smid: sm.softwood_received for smid, sm in model.sawmills.items()},
        "hardwood_received": {smid: sm.hardwood_received for smid, sm in model.sawmills.items()},
    }

    # Return time-stamped queue series for plotting
    if model.sawmills and hasattr(list(model.sawmills.values())[0], "sawmill_queue_times"):
        result["sawmill_queue_times"] = {smid: sm.sawmill_queue_times for smid, sm in model.sawmills.items()}
    if model.sawmills and hasattr(list(model.sawmills.values())[0], "sawmill_queue_lengths_ts"):
        result["sawmill_queue_lengths_ts"] = {smid: sm.sawmill_queue_lengths_ts for smid, sm in model.sawmills.items()}

    return result