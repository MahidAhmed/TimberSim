import simpy

class gb:

  ALL_LOGGING_SITES=[]
  FILLED_SAWMILL_AMOUNT = 0
  crane_process_ends_time = 0 #initial value
  ALL_SAWMILLS=[]
  ALL_COMPANY = []
  truck_create = 0
  trucks_no_of_travel_in_sawmill1 = []
  trucks_no_of_travel_in_sawmill2 = []

##Logging Company

class LoggingCompany:
  def __init__(self, env, company_id, num_trucks, sawmill, logging_site, mean_truck_generate_interval, **kwargs):
    self.env = env
    self.company_id = company_id
    self.num_trucks = num_trucks
    self.sawmills = sawmill
    self.logging_sites = logging_site
    self.mean_truck_generate_interval = mean_truck_generate_interval

    self.trucks = []


##Truck

class Truck:
  def __init__(self, env, truck_id, company_id, truck_capacity, **kwargs):
    self.env = env
    self.truck_id = truck_id
    self.company_id = company_id
    self.truck_capacity = truck_capacity
    self.truck_travels_in_sawmill = 0



##Sawmill

class Sawmill:
  def __init__(self, env, sawmill_id, sawmill_name, sawmill_location,sawmill_opening_time, sawmill_closing_time, sawmill_capacity, sawmill_total_crane, truck_area_capacity, scale_in_time, scale_out_time, scale_in_to_unload_time, unload_to_scale_out_time, unload_time_mean,  breakdown_start, breakdown_end,  **kwargs):
    self.env = env
    self.sawmill_id = sawmill_id
    self.sawmill_name = sawmill_name
    self.sawmill_location = sawmill_location
    self.sawmill_opening_time = sawmill_opening_time
    self.sawmill_closing_time = sawmill_closing_time
    self.sawmill_capacity = sawmill_capacity
    self.sawmill_total_crane = sawmill_total_crane
    self.truck_area_capacity = truck_area_capacity
    self.scale_in_time = scale_in_time
    self.scale_out_time = scale_out_time
    self.scale_in_to_unload_time = scale_in_to_unload_time
    self.unload_to_scale_out_time = unload_to_scale_out_time
    self.unload_time_mean = unload_time_mean
    self.breakdown_start = breakdown_start
    self.breakdown_end = breakdown_end

    self.crane1_operational = True
    self.crane2_operational = True
    self.breakdown_schedule = [(self.breakdown_start, self.breakdown_end)]  # Breakdown start and ending time


    self.truck_diverted_from_sawmill = 0
    self.breakdown_number = 0
    self.breakdown_countdown = 0
    self.missed_breakdown = 0

    self.filled_amount = simpy.Container(env, init = 0, capacity = sawmill_capacity)
    self.cranes_in_sawmill = simpy.Resource(self.env, capacity= self.sawmill_total_crane)
    self.scale_in = simpy.Resource(self.env, capacity =1)
    self.scale_out = simpy.Resource(self.env, capacity =1)
    self.truck_waiting_area = simpy.Resource(env, capacity=truck_area_capacity)
    self.crane1_unloading_end = sawmill_opening_time
    self.crane2_unloading_end = sawmill_opening_time
    self.previous_truck = None

    #Output metrics
    self.Number_of_Trucks_Unloaded = 0
    self.Total_Amount_Unloaded_in_Tons = 0
    self.sawmill_wait_time = []
    self.sawmill_queue_lengths = []
    self.FILLED_SAWMILL_AMOUNT = 0
    self.scale_in_wait_times = []
    self.truck_wait_time_in_crane = []
    self.scale_out_wait_times = []
    self.scale_in_to_crane_times = []
    self.crane_to_scale_out_times = []
    self.truck_turn_time_in_sawmill = []
    self.truck_number_per_day_in_sawmill = []

    #Crane data
    self.crane1_idle_time = []
    self.crane2_idle_time = []
    self.crane1_unloading_time = []
    self.crane2_unloading_time = []
    self.crane1_over_time = []
    self.crane2_over_time = []
    self.crane1_processed_truck = 0
    self.crane2_processed_truck = 0
    self.crane1_processed_truck_on_overtime = 0
    self.crane2_processed_truck_on_overtime = 0
    self.truck_arrived = 0
    self.truck_departed = 0

    #Data for all iteration
    self.all_Number_of_Trucks_Unloaded = 0
    self.all_Total_Amount_Unloaded_in_Tons = 0
    self.all_sawmill_wait_time = []
    self.all_sawmill_queue_lengths = []
    self.all_FILLED_SAWMILL_AMOUNT = 0
    self.all_scale_in_wait_times = []
    self.all_truck_wait_time_in_crane = []
    self.all_scale_out_wait_times = []
    self.all_scale_in_to_crane_times = []
    self.all_crane_to_scale_out_times = []

    #Crane data
    self.all_crane1_idle_time = []
    self.all_crane2_idle_time = []
    self.all_crane1_unloading_time = []
    self.all_crane2_unloading_time = []
    self.all_crane1_over_time = []
    self.all_crane2_over_time = []
    self.all_crane1_processed_truck = 0
    self.all_crane2_processed_truck = 0
    self.all_truck_arrived = 0
    self.all_truck_departed = 0

    self.crane_usage = {i: False for i in range(sawmill_total_crane)}

  def assign_crane(self):
        for crane_id, in_use in self.crane_usage.items():
            if not in_use:
                if self.sawmill_id == 'SM1' and crane_id=='0':
                  current_time = self.env.now
                  for start, end in self.breakdown_schedule:
                      if start <= current_time < end:
                          self.crane_usage[0] = True
                          return None
                      else:
                        self.crane_usage[0] = False

                self.crane_usage[crane_id] = True
                return crane_id
        return None  # Return None if no cranes are available


  def release_crane(self, crane_id):
        if crane_id in self.crane_usage:
            self.crane_usage[crane_id] = False

  def is_sawmill_open(self):
    return self.sawmill_opening_time <= (self.env.now % 1440) <= self.sawmill_closing_time




##Logging site

class LoggingSite:

  def __init__(self, env, site_id, company_id, avg_loading_time, opening_time, closing_time, site_cranes,initial_log_capacity, sawmill, **kwargs):
    self.env = env
    self.site_id = site_id
    self.company_id = company_id
    # self.latitude = latitude
    # self.longitude = longitude
    self.avg_loading_time = avg_loading_time
    self.opening_time = opening_time
    self.closing_time = closing_time
    self.site_cranes = site_cranes
    self.sawmill = sawmill
    
    # Retrieve wood type amounts from kwargs (default to 0 if not present)
    # CHANGED: 'pulpwood_amount' -> 'hardwood_amount'
    self.hardwood_amt = kwargs.get('hardwood_amount', 0)
    self.softwood_amt = kwargs.get('softwood_amount', 0)

    # Initialize the cranes resource
    self.cranes = simpy.Resource(env, capacity=self.site_cranes)
    
    # Existing total log capacity
    self.log_cap_limit = simpy.Container(env, init = initial_log_capacity, capacity=initial_log_capacity)

    # CHANGED: Hardwood and Softwood containers
    # Ensure capacity is at least 1 to avoid SimPy errors if amount is 0
    hardwood_cap = self.hardwood_amt if self.hardwood_amt > 0 else 1
    softwood_cap = self.softwood_amt if self.softwood_amt > 0 else 1

    self.hardwood_capacity = simpy.Container(env, init=self.hardwood_amt, capacity=hardwood_cap)
    self.softwood_capacity = simpy.Container(env, init=self.softwood_amt, capacity=softwood_cap)

    #Output metrics
    self.queue_lengths = []  # Store the queue lengths over time
    self.site_wait_time = []   #waiting time for each truck in the logging site
    self.loaded_truck_count = 0
    self.amount_loaded = 0
    self.logging_processing_end = opening_time
    self.loader_idle_time = []
    self.total_loading_time = []
    self.truck_turn_time_in_logging_site = []

    #Data for all iteration
    self.all_queue_lengths = []
    self.all_site_wait_time = []
    self.all_loaded_truck_count = 0
    self.all_amount_loaded = 0
    self.all_loader_idle_time = []
    self.all_total_loading_time = []

  def is_site_open(self):
    return self.opening_time <= (self.env.now % 1440)  <= self.closing_time