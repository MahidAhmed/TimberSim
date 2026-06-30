import simpy
import numpy as np

from entities import LoggingSite, Sawmill, LoggingCompany, Truck
import global_variables as gb
from sawmill_utilities import add_lists_with_padding

class Model:
    def __init__(self, env, logging_site_data, filtered_sawmill, sawmill_data, company_data, truck_data, travel_times_data, breakdown_type, breakdown_gap, unload_mean_time, scale_in_time, scale_out_time, truck_waiting_area, mtbf, mttr):
        self.env = env
        self.sawmills = {}
        self.logging_sites = {}
        self.companies = {}
        self.trucks = []
        self.travel_times = travel_times_data
        self.total_truck_generated = 0
        self.mtbf = breakdown_gap * mtbf
        self.mttr = mttr
        self.breakdown_type = breakdown_type
        self.sawmill_queue_times = []
        self.sawmill_queue_lengths_ts = []

        # ---------------------------------------------------------
        # 1. Create Sawmills
        # ---------------------------------------------------------
        for sawmill_row in sawmill_data.itertuples():
            sawmill_id = str(sawmill_row.sawmill_id)
            
            raw_species = str(getattr(sawmill_row, 'species', 'mixed')).lower().strip()
            sawmill_species = raw_species 
            
            mill_type = str(getattr(sawmill_row, 'mill_type', 'pulp/paper')).lower().strip()

            sm = Sawmill(
                env,
                sawmill_id=sawmill_id,
                sawmill_name=sawmill_row.sawmill_name,
                sawmill_location=sawmill_row.sawmill_location,
                sawmill_opening_time=sawmill_row.sawmill_opening_time,
                sawmill_closing_time=sawmill_row.sawmill_closing_time,
                sawmill_capacity=sawmill_row.sawmill_capacity,
                sawmill_total_crane=sawmill_row.sawmill_total_crane,
                truck_area_capacity=truck_waiting_area,
                scale_in_time=int(scale_in_time),
                scale_out_time=int(scale_out_time),
                scale_in_to_unload_time=int(sawmill_row.scale_in_to_unload_time),
                unload_to_scale_out_time=int(sawmill_row.unload_to_scale_out_time),
                unload_time_mean=unload_mean_time,
                breakdown_start=sawmill_row.breakdown_start,
                breakdown_end=sawmill_row.breakdown_end
            )
            
            sm.sawmill_queue_times = []
            sm.sawmill_queue_lengths_ts = []
            
            sm.species = sawmill_species
            sm.mill_type = mill_type

            # --- NEW: Capture Demands using CORRECT COLUMN NAMES ---
            # Using getattr with defaults to handle potential missing values
            sm.soft_demand = getattr(sawmill_row, 'softwood_demand', 0) or 0
            sm.hard_demand = getattr(sawmill_row, 'hardwood_demand', 0) or 0
            
            sm.softwood_received = 0
            sm.hardwood_received = 0
            
            # Add coordinates for dynamic distance calculation
            sm.lat = float(getattr(sawmill_row, 'Latitude', 0.0))
            sm.lng = float(getattr(sawmill_row, 'Longitude', 0.0))

            self.sawmills[sawmill_id] = sm

        # ---------------------------------------------------------
        # 2. Create Logging Sites
        # ---------------------------------------------------------
        for logging_site_row in logging_site_data.itertuples():
            site_id = str(getattr(logging_site_row, 'site_id'))
            company_id = str(getattr(logging_site_row, 'company_id', None))

            raw_cranes = getattr(logging_site_row, 'site_cranes', 1)
            try:
                safe_site_cranes = int(raw_cranes) if raw_cranes == raw_cranes else 1 
            except (ValueError, TypeError):
                safe_site_cranes = 1
            if safe_site_cranes < 1: safe_site_cranes = 1

            # Determine Species and Amounts
            h_val = getattr(logging_site_row, 'hardwood_amount', 0) or 0
            s_val = getattr(logging_site_row, 'softwood_amount', 0) or 0
            
            raw_ls_species = str(getattr(logging_site_row, 'species', '')).lower().strip()
            if raw_ls_species and raw_ls_species != 'nan':
                if 'mixed' in raw_ls_species or '/' in raw_ls_species:
                    ls_species = 'mixed'
                else:
                    ls_species = raw_ls_species
            else:
                if h_val > 0 and s_val > 0: ls_species = 'mixed'
                elif h_val > 0: ls_species = 'hard'
                elif s_val > 0: ls_species = 'soft'
                else: ls_species = 'mixed'

            raw_type = str(getattr(logging_site_row, 'type', 'other')).lower().strip()

            ls_instance = LoggingSite(
                env,
                site_id=site_id,
                sawmill=None, 
                company_id=company_id,
                avg_loading_time=logging_site_row.avg_loading_time,
                opening_time=logging_site_row.opening_time,
                closing_time=logging_site_row.closing_time,
                site_cranes=safe_site_cranes,
                initial_log_capacity=logging_site_row.initial_log_capacity
            )
            
            ls_instance.hardwood_amount = h_val
            ls_instance.softwood_amount = s_val
            ls_instance.species = ls_species
            ls_instance.timber_type = raw_type
            # Add coordinates for dynamic distance calculation
            ls_instance.lat = float(getattr(logging_site_row, 'lat', 0.0))
            ls_instance.lng = float(getattr(logging_site_row, 'lng', 0.0))

            # --- DYNAMIC ASSIGNMENT LOGIC ---
            best_sawmill = None
            min_travel_time = float('inf')

            for sm_id, sm_obj in self.sawmills.items():
                if not self.check_compatibility(ls_instance, sm_obj):
                    continue
                
                t_time = self.get_travel_time(sm_id, site_id)
                if t_time < min_travel_time:
                    min_travel_time = t_time
                    best_sawmill = sm_obj
            
            ls_instance.sawmill = best_sawmill
            self.logging_sites[site_id] = ls_instance

        # ---------------------------------------------------------
        # 3. Create Companies & Trucks
        # ---------------------------------------------------------
        for _, company_row in company_data.iterrows():
            company_id = str(company_row['company_id'])
            ls_id = str(company_row['logging_site'])
            assigned_sm = None
            if ls_id in self.logging_sites:
                assigned_sm = self.logging_sites[ls_id].sawmill

            self.companies[company_id] = LoggingCompany(
                env,
                company_id=company_id,
                num_trucks=company_row['num_trucks'],
                sawmill=assigned_sm, 
                logging_site=self.logging_sites.get(ls_id),
                mean_truck_generate_interval=company_row['mean_truck_generate_interval']
            )

        for _, truck_row in truck_data.iterrows():
            truck_id = str(truck_row['truck_id'])
            company_id = str(truck_row['company_id'])
            truck_capacity = truck_row['truck_capacity']

            company = self.companies.get(company_id)
            truck = Truck(env, truck_id, company_id, truck_capacity)
            self.trucks.append(truck)

            if company:
                company.trucks.append(truck)

        # ---------------------------------------------------------
        # 4. Create Dummy Sawmill (For 0% Capacity Diversions)
        # ---------------------------------------------------------
        self.dummy_sawmill = Sawmill(
            env,
            sawmill_id="DUMMY_SINK",
            sawmill_name="Emergency Relief Sawmill",
            sawmill_location="Unknown",
            sawmill_opening_time=0,
            sawmill_closing_time=1440, # Always open
            sawmill_capacity=999999999, # Infinite capacity
            sawmill_total_crane=10, # Plenty of cranes, no wait time
            truck_area_capacity=9999,
            scale_in_time=1,
            scale_out_time=1,
            scale_in_to_unload_time=1,
            unload_to_scale_out_time=1,
            unload_time_mean=10,
            breakdown_start=float('inf'), # Never breaks down
            breakdown_end=float('inf')
        )
        self.dummy_sawmill.sawmill_queue_times = []
        self.dummy_sawmill.sawmill_queue_lengths_ts = []
        self.dummy_sawmill.species = 'mixed'
        self.dummy_sawmill.mill_type = 'pulp/paper'
        self.dummy_sawmill.soft_demand = 1
        self.dummy_sawmill.hard_demand = 1
        self.dummy_sawmill.softwood_received = 0
        self.dummy_sawmill.hardwood_received = 0
    # ---------------------------------------------------------
    # Helper Functions
    # ---------------------------------------------------------

    def check_compatibility(self, ls, sm):
        if 'saw' in ls.timber_type: 
            if sm.mill_type != 'lumber': return False
        else: 
            if sm.mill_type == 'lumber': return False

        ls_species = ls.species
        sm_species = sm.species

        if 'mixed' in sm_species or '/' in sm_species: return True
        if 'mixed' in ls_species or '/' in ls_species: return True
        return ls_species == sm_species

    # def get_travel_time(self, sawmill_loc, logging_site_loc):
    #     travel_times_data = self.travel_times
    #     filtered = travel_times_data[(travel_times_data['Sawmill'] == sawmill_loc) & (travel_times_data['LoggingSite'] == logging_site_loc)]
    #     if filtered.empty:
    #         return float('inf') 
    #     return filtered['Total_TruckTravelTime'].sum()

    # def find_effective_sawmill(self, logging_site_id, assigned_sawmill_id):
    #     lowest_time = float('inf')
    #     effective_sawmill = self.sawmills[assigned_sawmill_id]
    #     ls_obj = self.logging_sites[logging_site_id]

    #     for sawmill_id, sawmill in self.sawmills.items():
    #         if sawmill_id == assigned_sawmill_id: continue
    #         if not self.check_compatibility(ls_obj, sawmill): continue
    #         if not (sawmill.crane1_operational and sawmill.crane2_operational): continue
            
    #         travel_time = self.get_travel_time(sawmill_id, logging_site_id)
    #         if travel_time < lowest_time:
    #             lowest_time = travel_time
    #             effective_sawmill = sawmill

    #     return effective_sawmill
    


    #----------------------------------------------------------#
    #----- Next two function get_travel_time and find effective  sawmill is for finding the location based nearest sawmill
    #----------------------------------------------------------#

    def get_travel_time(self, sawmill_loc, logging_site_loc):
        import math
        # 1. Check for Dummy Sawmill
        if sawmill_loc == "DUMMY_SINK":
            return 30.0  # Exactly 30 minutes away from ALL logging sites
            
        # 2. Check the static database (for pre-existing routes)
        travel_times_data = self.travel_times
        filtered = travel_times_data[(travel_times_data['Sawmill'] == sawmill_loc) & (travel_times_data['LoggingSite'] == logging_site_loc)]
        if not filtered.empty:
            return filtered['Total_TruckTravelTime'].sum()
            
        # 3. Dynamic Calculation (For generated sites rerouting to alternative sawmills)
        if sawmill_loc in self.sawmills and logging_site_loc in self.logging_sites:
            sm = self.sawmills[sawmill_loc]
            ls = self.logging_sites[logging_site_loc]
            
            # Calculate Euclidean distance in degrees
            euclidean_deg = math.sqrt((ls.lng - sm.lng)**2 + (ls.lat - sm.lat)**2)
            
            # Convert to miles (1 degree is approx 69 miles)
            euclidean_miles = euclidean_deg * 69.0
            
            # Apply 20% conversion factor for winding roads
            real_miles = euclidean_miles * 1.20
            
            # Convert miles to minutes (Assuming a truck drives average 45 mph -> 1.33 mins per mile)
            travel_minutes = real_miles * 1.333
            
            return travel_minutes

        return float('inf')
    
    def find_effective_sawmill(self, logging_site_id, assigned_sawmill_id):
        import math
        lowest_distance = float('inf')
        effective_sawmill = self.sawmills[assigned_sawmill_id]
        ls_obj = self.logging_sites[logging_site_id]

        for sawmill_id, sawmill in self.sawmills.items():
            if sawmill_id == assigned_sawmill_id: continue # Skip the broken one
            if sawmill_id == "DUMMY_SINK": continue # Skip the dummy in the main check
            if not self.check_compatibility(ls_obj, sawmill): continue
            if not (sawmill.crane1_operational and sawmill.crane2_operational): continue
            
            # Calculate Euclidean distance between the logging site and this sawmill
            euclidean_distance = math.sqrt((ls_obj.lat - sawmill.lat)**2 + (ls_obj.lng - sawmill.lng)**2)
            
            if euclidean_distance < lowest_distance:
                lowest_distance = euclidean_distance
                effective_sawmill = sawmill

        # If no real alternative was found (e.g., all others are broken or it's a 1-sawmill simulation)
        # Fall back to the Dummy Sawmill to keep the simulation running
        if effective_sawmill.sawmill_id == assigned_sawmill_id:
            effective_sawmill = self.dummy_sawmill

        return effective_sawmill
    

    def monitor_scale_in_queues(self, duration, every=1.0):
        while self.env.now < duration:
            for sm in self.sawmills.values():
                q_len = len(sm.scale_in.queue) if hasattr(sm, "scale_in") else 0
                sm.sawmill_queue_times.append(self.env.now)
                sm.sawmill_queue_lengths_ts.append(q_len)
            yield self.env.timeout(every)

    def truck_generate(self, duration):
        if not self.companies: return
        max_trucks = max(len(company.trucks) for company in self.companies.values())
        
        while self.env.now < duration:
            for n in range(max_trucks):
                for company in self.companies.values():
                    if n < len(company.trucks):
                        truck = company.trucks[n]
                        if company.logging_sites and company.logging_sites.sawmill:
                            self.total_truck_generated += 1
                            self.env.process(self.truck_process(truck, company.logging_sites, duration))
            
                yield self.env.timeout(company.mean_truck_generate_interval)
                if self.env.now >= duration: break
            break

    def truck_process(self, truck_itr, logging_site, duration):
        while True:
            gb.truck_create += 1

            if not logging_site.is_site_open():
                if (self.env.now % 1440) <= logging_site.opening_time:
                    yield self.env.timeout(logging_site.opening_time - (self.env.now % 1440))
                elif (self.env.now % 1440) > logging_site.closing_time:
                    yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
                yield self.env.process(self.logging_process(truck_itr, logging_site, duration))
            else:
                yield self.env.process(self.logging_process(truck_itr, logging_site, duration))

            if logging_site.sawmill is None:
                return

            assigned_sawmill = logging_site.sawmill
            effective_sawmill = assigned_sawmill

            current_time = self.env.now
            if assigned_sawmill.breakdown_start is not None and assigned_sawmill.breakdown_end is not None:
                # print(f"breakdown start at {assigned_sawmill.breakdown_start} and type is {self.breakdown_type}")
                for start, end in assigned_sawmill.breakdown_schedule:
                    
                    
                    if start <= current_time < end:
                        # print(f"breakdown start at {start} and end in {end} , current time {current_time} and type is {self.breakdown_type}")
                        
                        if self.breakdown_type == 'none':
                            assigned_sawmill.crane1_operational = True
                            assigned_sawmill.crane2_operational = True
                        elif self.breakdown_type == 'one_crane':
                            assigned_sawmill.crane1_operational = False
                            assigned_sawmill.crane2_operational = True
                            print(f"One crane breakdown happens in the sawmill {assigned_sawmill.sawmill_id}")
                        elif self.breakdown_type == 'two_crane':
                            assigned_sawmill.crane1_operational = False
                            assigned_sawmill.crane2_operational = False
                            print(f"Two crane breakdown happens in the sawmill {assigned_sawmill.sawmill_id}")
                    else:
                        assigned_sawmill.crane1_operational = True
                        assigned_sawmill.crane2_operational = True

                if not assigned_sawmill.crane1_operational and not assigned_sawmill.crane2_operational:
                    effective_sawmill = self.find_effective_sawmill(logging_site.site_id, assigned_sawmill.sawmill_id)
                    if effective_sawmill is assigned_sawmill:
                        yield self.env.timeout(assigned_sawmill.breakdown_end - self.env.now)
                        print("No alternative sawmill found")
                        effective_sawmill = assigned_sawmill 
                    else:
                        assigned_sawmill.truck_diverted_from_sawmill += 1
                        print("Truck diverted")

            travel_time_to_sawmill = self.get_travel_time(effective_sawmill.sawmill_id, logging_site.site_id)
            if travel_time_to_sawmill == float('inf'):
                 return 

            yield self.env.timeout(travel_time_to_sawmill)

            if not effective_sawmill.is_sawmill_open():
                if (self.env.now % 1440) <= effective_sawmill.sawmill_opening_time:
                    yield self.env.timeout(effective_sawmill.sawmill_opening_time - (self.env.now % 1440))
                elif (self.env.now % 1440) > effective_sawmill.sawmill_closing_time:
                    yield self.env.timeout(1440 - (self.env.now % 1440) + effective_sawmill.sawmill_opening_time)
                elif self.env.now > duration:
                    return

            yield self.env.process(self.sawmill_process(truck_itr, logging_site, effective_sawmill, duration))
            
            travel_time_to_logging_site = self.get_travel_time(effective_sawmill.sawmill_id, logging_site.site_id)
            yield self.env.timeout(travel_time_to_logging_site)

            yield self.env.process(self.truck_process(truck_itr, logging_site, duration))

    
    def logging_process(self, truck_itr, logging_site, duration):
      logging_site_start_time = self.env.now

      if logging_site.log_cap_limit.level < truck_itr.truck_capacity:
          return

      with logging_site.cranes.request() as crane_request:
          yield crane_request

          if logging_site_start_time % 1440  > logging_site.closing_time:
              logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

          if logging_site_start_time//1440 < self.env.now//1440:
              logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

          queue_length = len(logging_site.cranes.queue)
          logging_site.queue_lengths.append(queue_length)
          
          site_waiting_period_end = self.env.now
          waiting_time = site_waiting_period_end - logging_site_start_time
          logging_site.site_wait_time.append(waiting_time)

          if self.env.now % 1440 < logging_site_start_time % 1440:
              logging_site_start_time = ((logging_site_start_time // 1440) + 1) * 1440 + logging_site.opening_time

          mean_loading_time = logging_site.avg_loading_time
          loading_time = np.random.uniform(low=mean_loading_time-(mean_loading_time/2), high=mean_loading_time+(mean_loading_time/2))

          logging_site.loaded_truck_count += 1

          yield logging_site.log_cap_limit.get(truck_itr.truck_capacity)

          loading_processing_start = self.env.now

          if logging_site.logging_processing_end // 1440 < self.env.now  // 1440 : 
              logging_site.logging_processing_end = (self.env.now // 1440) * 1440 + logging_site.opening_time

          logging_site.loader_idle_time.append(loading_processing_start - logging_site.logging_processing_end)

          logging_site.total_loading_time.append(loading_time)
          yield self.env.timeout(loading_time)
          logging_site.logging_processing_end = self.env.now

          logging_site.amount_loaded += truck_itr.truck_capacity

          logging_site.truck_turn_time_in_logging_site.append(logging_site.logging_processing_end - logging_site_start_time)


    def sawmill_process(self, truck_itr, logging_site,assigned_sawmill,duration):
      sawmill_start_time = self.env.now
      sawmill = assigned_sawmill

      truck_itr.truck_travels_in_sawmill += 1
      sawmill.truck_arrived += 1

      if sawmill.filled_amount.level + truck_itr.truck_capacity > sawmill.filled_amount.capacity:
          return
      if ((self.env.now % 1440) < sawmill.sawmill_opening_time):
            yield self.env.timeout(sawmill.sawmill_opening_time - (self.env.now % 1440))
            sawmill_start_time = self.env.now

      with sawmill.truck_waiting_area.request() as truck_waiting_area_request:
            yield truck_waiting_area_request
            in_system = len(sawmill.truck_waiting_area.users) + len(sawmill.truck_waiting_area.queue)
            sawmill.sawmill_queue_lengths.append(in_system)


      with sawmill.scale_in.request() as scale_in_request:
            yield scale_in_request
            wait_time_scale_in = self.env.now - sawmill_start_time
            sawmill.scale_in_wait_times.append(wait_time_scale_in)
            yield self.env.timeout( sawmill.scale_in_time)

      scale_in_end_time = self.env.now
      yield self.env.timeout(sawmill.scale_in_to_unload_time)
      
      sawmill.scale_in_to_crane_times.append(self.env.now -scale_in_end_time)

      with assigned_sawmill.truck_waiting_area.request() as waiting_request:
          yield waiting_request

      with sawmill.cranes_in_sawmill.request() as crane_request:
            yield crane_request
            crane_id = sawmill.assign_crane()
            
            q_len = len(sawmill.scale_in.queue)
            sawmill.sawmill_queue_lengths.append(q_len)
            sawmill.sawmill_queue_times.append(self.env.now)
            sawmill.sawmill_queue_lengths_ts.append(q_len)

            wait_time_crane = self.env.now - scale_in_end_time
            sawmill.truck_wait_time_in_crane.append(wait_time_crane)


            #Next block is for missing brakdown
            if self.breakdown_type in ['one_crane', 'two_crane']:
                if sawmill.breakdown_end < self.env.now:
                    sawmill.breakdown_number += 1
                    sawmill.missed_breakdown += 1
                    sawmill.breakdown_start = self.env.now + np.random.exponential(scale=self.mtbf)
                    sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)

            if crane_id == 0:
                if sawmill.crane1_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane1_unloading_end % 1440 > sawmill.sawmill_closing_time:
                    sawmill.crane1_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time
            elif crane_id == 1:
                if sawmill.crane2_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane2_unloading_end % 1440 > sawmill.sawmill_closing_time:
                    sawmill.crane2_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time

            unload_time_mean = sawmill.unload_time_mean
            unload_time = np.random.uniform(low=unload_time_mean-(unload_time_mean/2), high=unload_time_mean+(unload_time_mean/2))


            # for breakdown
            if self.breakdown_type == 'one_crane':
                if((sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end)):
                    if (crane_id == 0 and sawmill.breakdown_countdown == 0):
                        sawmill.breakdown_countdown = 1
                        yield self.env.timeout(sawmill.breakdown_end - self.env.now)

                elif sawmill.breakdown_start <= (self.env.now+unload_time) <= sawmill.breakdown_end:
                    if (crane_id == 0 and sawmill.breakdown_countdown == 0):
                        sawmill.breakdown_countdown =  1
                        yield self.env.timeout(sawmill.breakdown_end - self.env.now)

                if sawmill.breakdown_countdown == 1:
                    sawmill.breakdown_number += 1
                    sawmill.breakdown_countdown = 0
                    # As it checked the current breakdown and processed the action, now new breakdown schedule is assigned
                    sawmill.breakdown_start = sawmill.breakdown_end + np.random.exponential(scale=self.mtbf)
                    sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
                    print(f"New breakdown will happen from {sawmill.breakdown_start} to {sawmill.breakdown_end}")
                    # sawmill.breakdown_start = sawmill.breakdown_start + 1440
                    # sawmill.breakdown_end = sawmill.breakdown_end + 1440

            if self.breakdown_type == 'two_crane':
                if((sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end)):
                    if (crane_id == 0 and sawmill.breakdown_countdown == 1):
                        sawmill.breakdown_countdown = 2
                    elif (crane_id == 1 and sawmill.breakdown_countdown == 1):
                        sawmill.breakdown_countdown = 2
                    else:
                        sawmill.breakdown_countdown = 0
                    yield self.env.timeout(sawmill.breakdown_end - self.env.now)

                # if(((sawmill.breakdown_start <= (self.env.now+unload_time)) and ((self.env.now+unload_time) >= sawmill.breakdown_end))):
                elif sawmill.breakdown_start <= (self.env.now + unload_time) <= sawmill.breakdown_end:
                    if (crane_id == 0 and sawmill.breakdown_countdown == 1):
                        sawmill.breakdown_countdown = 2
                    elif (crane_id == 1 and sawmill.breakdown_countdown == 1):
                        sawmill.breakdown_countdown = 2
                    else:
                        sawmill.breakdown_countdown = 0
                    yield self.env.timeout(sawmill.breakdown_end - self.env.now)

                if sawmill.breakdown_countdown == 2:
                    sawmill.breakdown_number += 1
                    sawmill.breakdown_countdown = 0
                    # As it checked the current breakdown and processed the action, now new breakdown schedule is assigned
                    sawmill.breakdown_start = sawmill.breakdown_end + np.random.exponential(scale=self.mtbf)
                    sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
                    # sawmill.breakdown_start = sawmill.breakdown_start + 1440
                    # sawmill.breakdown_end = sawmill.breakdown_end + 1440
            
            

            if(crane_id == 0):
              crane1_unloading_start = self.env.now
            else:
              crane2_unloading_start = self.env.now

            if ((self.env.now % 1440) < sawmill.sawmill_closing_time):
              if(crane_id == 0): 
                crane1_idle = crane1_unloading_start - sawmill.crane1_unloading_end
                sawmill.crane1_idle_time.append( crane1_idle )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                yield self.env.timeout(unload_time)
                sawmill.crane1_unloading_time.append(unload_time)
                sawmill.crane1_processed_truck += 1
                sawmill.crane1_unloading_end = self.env.now
              else: 
                crane2_idle = crane2_unloading_start - sawmill.crane2_unloading_end
                sawmill.crane2_idle_time.append(crane2_idle )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                yield self.env.timeout(unload_time)
                sawmill.crane2_unloading_time.append(unload_time)
                sawmill.crane2_processed_truck += 1
                sawmill.crane2_unloading_end = self.env.now
            else: 
              if(crane_id == 0): 
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                yield self.env.timeout(unload_time)
                sawmill.crane1_over_time.append(unload_time)
                sawmill.crane1_processed_truck_on_overtime += 1
                sawmill.crane1_unloading_end = self.env.now
              else: 
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                yield self.env.timeout(unload_time)
                sawmill.crane2_over_time.append(unload_time)
                sawmill.crane2_processed_truck_on_overtime += 1
                sawmill.crane2_unloading_end = self.env.now

            sawmill.Number_of_Trucks_Unloaded += 1
            sawmill.Total_Amount_Unloaded_in_Tons += truck_itr.truck_capacity

            # --- TRACK SPECIES & AMOUNT (UPDATED LOGIC) ---
            # Calculates split based on SAWMILL DEMAND (softwood_demand / hardwood_demand)
            amount = truck_itr.truck_capacity
            
            # 1. Determine Target Ratio based on Sawmill Demand
            s_dem = assigned_sawmill.soft_demand
            h_dem = assigned_sawmill.hard_demand
            total_dem = s_dem + h_dem
            
            target_soft_ratio = 0.5 # Default
            if total_dem > 0:
                target_soft_ratio = s_dem / total_dem
            
            # 2. Check Physical Constraints of Logging Site
            ls_spec = getattr(logging_site, 'species', 'mixed')
            
            if ls_spec == 'soft':
                # Site only has Softwood
                assigned_sawmill.softwood_received += amount
            elif ls_spec == 'hard':
                # Site only has Hardwood
                assigned_sawmill.hardwood_received += amount
            else:
                # Mixed Site: Can fulfill exact demand ratio of the Sawmill
                assigned_sawmill.softwood_received += (amount * target_soft_ratio)
                assigned_sawmill.hardwood_received += (amount * (1.0 - target_soft_ratio))
            # ------------------------------------------

            assigned_sawmill.release_crane(crane_id)

      # Scale out process
      crane_end_time = self.env.now
      yield self.env.timeout(sawmill.unload_to_scale_out_time)
      sawmill.crane_to_scale_out_times.append(self.env.now - crane_end_time)

      scale_out_waiting_start = self.env.now
      with sawmill.scale_out.request() as scale_out_request:
            yield scale_out_request
            wait_time_scale_out = self.env.now -scale_out_waiting_start
            sawmill.scale_out_wait_times.append(wait_time_scale_out)
            yield self.env.timeout(sawmill.scale_out_time)
            sawmill.truck_departed += 1

      turn_time = self.env.now - sawmill_start_time
      sawmill.truck_turn_time_in_sawmill.append(turn_time)


    def start_simulation(self, duration):
        self.env.process(self.truck_generate(duration))
        self.env.process(self.monitor_scale_in_queues(duration, every=1.0))
        self.env.run(until=duration)

        for truck in self.trucks:
            gb.trucks_no_of_travel_in_sawmill1.append(truck.truck_travels_in_sawmill)

        if len(gb.trucks_no_of_travel_in_sawmill2) == 0:
            gb.trucks_no_of_travel_in_sawmill2 = gb.trucks_no_of_travel_in_sawmill1[:]
            gb.trucks_no_of_travel_count = [1] * len(gb.trucks_no_of_travel_in_sawmill1)
        else:
            gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_count = add_lists_with_padding(
                gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_in_sawmill1,
                gb.trucks_no_of_travel_count, [1] * len(gb.trucks_no_of_travel_in_sawmill1)
            )

        gb.trucks_no_of_travel_in_sawmill1 = []