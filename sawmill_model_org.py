# import simpy
# import numpy as np

# from entities import LoggingSite, Sawmill, LoggingCompany, Truck
# import global_variables as gb
# from sawmill_utilities import add_lists_with_padding

# class Model:
#     def __init__(self, env, logging_site_data, sawmill_data, company_data, truck_data, travel_times_data, mtbf, mttr ):
#         self.env = env
#         # Initialize dictionaries to hold instances
#         self.sawmills = {}
#         self.logging_sites = {}
#         self.companies = {}
#         self.trucks = []
#         self.travel_times = travel_times_data
#         self.total_truck_generated = 0
#         self.mtbf = mtbf
#         self.mttr = mttr


#         # Creating Sawmill instances
#         for sawmill_row in sawmill_data.itertuples():
#           sawmill_id = str(sawmill_row.sawmill_id)
#           sawmill_name = sawmill_row.sawmill_name
#           sawmill_location = sawmill_row.sawmill_location
#           sawmill_opening_time = sawmill_row.sawmill_opening_time
#           sawmill_closing_time = sawmill_row.sawmill_closing_time
#           sawmill_capacity = sawmill_row.sawmill_capacity
#           sawmill_total_crane = sawmill_row.sawmill_total_crane
#           truck_area_capacity = sawmill_row.truck_area_capacity
#           scale_in_time = sawmill_row.scale_in_time
#           scale_out_time = sawmill_row.scale_out_time
#           scale_in_to_unload_time = sawmill_row.scale_in_to_unload_time
#           unload_to_scale_out_time = sawmill_row.unload_to_scale_out_time
#           unload_time_mean = sawmill_row.unload_time_mean
#           breakdown_start = sawmill_row.breakdown_start
#           breakdown_end = sawmill_row.breakdown_end
#           # breakdown_start = np.random.exponential(scale=self.mtbf)
#           # breakdown_end = breakdown_start + np.random.exponential(scale=self.mttr)


#           self.sawmills[sawmill_id] = Sawmill(
#               env,
#               sawmill_id=sawmill_id,
#               sawmill_name=sawmill_name,
#               sawmill_location=sawmill_location,
#               sawmill_opening_time=sawmill_opening_time,
#               sawmill_closing_time=sawmill_closing_time,
#               sawmill_capacity=sawmill_capacity,
#               sawmill_total_crane=sawmill_total_crane,
#               truck_area_capacity=truck_area_capacity,
#               scale_in_time = int(scale_in_time),
#               scale_out_time = int(scale_out_time),
#               scale_in_to_unload_time = int(scale_in_to_unload_time),
#               unload_to_scale_out_time = int(unload_to_scale_out_time),
#               unload_time_mean = int(unload_time_mean),
#               breakdown_start = breakdown_start,
#               breakdown_end = breakdown_end
#           )
#           # self.env.process(self.crane_breakdown_process(self.sawmills[sawmill_id]))




#         # Creating LoggingSite instances and associating them with Sawmills
#         for logging_site_row in logging_site_data.itertuples():
#             site_id = str(getattr(logging_site_row, 'site_id'))
#             sawmill_id = str(getattr(logging_site_row, 'sawmill', None))
#             company_id = str(getattr(logging_site_row, 'company_id', None))

#             self.logging_sites[site_id] = LoggingSite(
#                 env,
#                 site_id=site_id,
#                 sawmill=self.sawmills.get(sawmill_id),
#                 company_id=company_id,
#                 latitude=logging_site_row.latitude,
#                 longitude=logging_site_row.longitude,
#                 avg_loading_time=logging_site_row.avg_loading_time,
#                 opening_time=logging_site_row.opening_time,
#                 closing_time=logging_site_row.closing_time,
#                 site_cranes=logging_site_row.site_cranes,
#                 initial_log_capacity=logging_site_row.initial_log_capacity
#             )



#         # Creating Company instances
#         for _, company_row in company_data.iterrows():
#             company_id = str(company_row['company_id'])
#             self.companies[company_id] = LoggingCompany(
#                 env,
#                 company_id=company_id,
#                 num_trucks=company_row['num_trucks'],
#                 sawmill=self.sawmills[company_row['sawmill']] if company_row['sawmill'] in self.sawmills else None,
#                 logging_site=self.logging_sites[company_row['logging_site']] if company_row['logging_site'] in self.logging_sites else None,
#                 mean_truck_generate_interval = company_row['mean_truck_generate_interval']
#             )


#         # Create instances of trucks
#         for _, truck_row in truck_data.iterrows():
#             truck_id = str(truck_row['truck_id'])
#             company_id = str(truck_row['company_id'])
#             truck_capacity = truck_row['truck_capacity']  # Make sure this column exists in your dataframe

#             # Check if the company exists before trying to add the truck to it
#             if company_id in self.companies:
#                 company = self.companies[company_id]
#             else:
#                 #print(f"Company with ID {company_id} not found for truck {truck_id}.")
#                 company = None

#             truck = Truck(env, truck_id, company_id, truck_capacity)  # Pass all required arguments to the Truck constructor
#             self.trucks.append(truck)

#             # Append the truck to the company's truck list if the company exists
#             if company:
#                 company.trucks.append(truck)



#     #-----------------------Functions------------------------------

#     # A function to lookup travel time between two locations
#     # def get_travel_time(self, sawmill_location, logging_site_location):
#     #   filtered_df = travel_times_data[(travel_times_data['Sawmill'] == sawmill_location) & (travel_times_data['LoggingSite'] == logging_site_location)]

#     #   # Calculate the total time
#     #   total_time = filtered_df['Total_TruckTravelTime'].sum()
#     #   return total_time
#     def get_travel_time(self, sawmill_location, logging_site_location):
#         filtered_df = self.travel_times[
#             (self.travel_times['Sawmill'] == sawmill_location) & 
#             (self.travel_times['LoggingSite'] == logging_site_location)
#         ]
#         total_time = filtered_df['Total_TruckTravelTime'].sum()
#         return total_time


#     # A function to find the sawmill with the lowest travel time
#     def find_effective_sawmill(self, logging_site_id, assigned_sawmill_id):
#         lowest_time = float('inf')
#         effective_sawmill = None

#         for sawmill_id, sawmill in self.sawmills.items():
#             if sawmill_id == assigned_sawmill_id:
#                 continue  # Skip the assigned sawmill

#             # Check if both cranes are operational
#             if not (sawmill.crane1_operational and sawmill.crane2_operational) or len(sawmill.scale_in.queue) >= 20:
#                 continue
#             try:
#                 travel_time = self.get_travel_time(logging_site_id, sawmill_id)
#                 if travel_time < lowest_time:
#                     lowest_time = travel_time
#                     effective_sawmill = sawmill
#             except ValueError:
#                 continue  # Skip if no travel time data available

#         # if effective_sawmill is None:
#         #     raise ValueError(f"No alternative sawmill found for logging site {logging_site_id}")

#         return effective_sawmill


#     def truck_generate(self, duration):
#       # Calculate the maximum number of trucks any company has
#       # max_trucks = max(len(company.trucks) for company in self.companies.values())

#       if not self.companies:
#           print("No companies found. Skipping truck generation.")
#           return

#       for company in self.companies:
#           # your logic here (e.g., assigning trucks)
#           print(f"Trucks generated for Company {company}")


#       max_trucks = max((len(company.trucks) for company in self.companies.values()), default=0)
#       # print(f"{max_trucks} was generated for Company {company}")
#       # if max_trucks == 0:
#       #     print("No trucks assigned to any company. Skipping truck generation.")
#       #     return


#       # Keep generating trucks until the simulation ends
#       while self.env.now < duration:
#           # Generate the nth truck for each company simultaneously
#           for n in range(max_trucks):
#               for company in self.companies.values():
#                   if n < len(company.trucks):  # Check if the company has an nth truck
#                       truck = company.trucks[n]
#                       logging_site = company.logging_sites  # Assuming one logging site per company
#                       self.total_truck_generated += 1
#                       self.env.process(self.truck_process(truck, logging_site, duration))

#               # After starting a truck for each company, wait for the next generation interval
#               # yield self.env.timeout(np.random.exponential(scale=company.mean_truck_generate_interval))
#               yield self.env.timeout(company.mean_truck_generate_interval)

#               # Check if duration of the simulation is reached, if so break the loop
#               if self.env.now >= duration:
#                   #print(f"Simulation ended at {self.env.now} with {self.total_truck_generated} trucks generated.")
#                   break
#           #print(f"***********************Total trucks generated in this interval: {self.total_truck_generated}********************")
#           break

#     def truck_process(self, truck_itr, logging_site, duration):
#       while True:
#           gb.truck_create += 1

#           # if logging_site.site_id == 'LS2':
#           #     print(f"{self.env.now:.2f}: TP, {truck_itr.truck_id} started truck processing ")

#           # Wait if logging site is not open
#           if not logging_site.is_site_open():
#               # if logging_site.site_id == 'LS2':
#               #   print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is closed. Waiting for opening time. Have to wait for {(1440 - (self.env.now % 1440) + logging_site.opening_time):.2f} minutes")
#               yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
#               yield self.env.process(self.logging_process(truck_itr, logging_site, duration))
#           else:
#               # print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is open.")
#               yield self.env.process(self.logging_process(truck_itr, logging_site, duration))

#           # Ensure logging site has an associated sawmill
#           if logging_site.sawmill is None:
#               print(f"No sawmill associated with logging site {logging_site.site_id}")
#               return

#           assigned_sawmill = logging_site.sawmill
#           effective_sawmill = assigned_sawmill  # Default sawmill is the assigned one
#           site_location = logging_site

#           # Check crane operational status during breakdown
#           current_time = self.env.now
#           if assigned_sawmill.breakdown_start is not None and assigned_sawmill.breakdown_end is not None:

#               #The next for loop check when the current time is between breakdown schedule the crane will assign as inactive
#               # otherwise it will remain active. This will be checked every time for a truck process

#               for start, end in assigned_sawmill.breakdown_schedule:
#                   if start <= current_time < end:
#                       assigned_sawmill.crane1_operational = True
#                       assigned_sawmill.crane2_operational = True

#                   else:
#                       assigned_sawmill.crane1_operational = True
#                       assigned_sawmill.crane2_operational = True

#               #The next logic check when the both crane is inactive it will find the new effective sawmill

#               if not assigned_sawmill.crane1_operational and not assigned_sawmill.crane2_operational:
#                 effective_sawmill = self.find_effective_sawmill(logging_site.site_id, assigned_sawmill.sawmill_id)
#                 if effective_sawmill is None:
#                     #print(f"Sawmill: {assigned_sawmill.sawmill_id} Breakdown start time {assigned_sawmill.breakdown_start} and end time {assigned_sawmill.breakdown_end} and none of the sawmill was found to transfer the truck")
#                     yield self.env.timeout(assigned_sawmill.breakdown_end - self.env.now)
#                     effective_sawmill = assigned_sawmill  # Reassign to original sawmill after waiting
#                 else:
#                     assigned_sawmill.truck_diverted_from_sawmill += 1

#           # Calculate and wait for travel time to the effective sawmill
#           travel_time_to_sawmill = self.get_travel_time(effective_sawmill.sawmill_id,logging_site.site_id)
#           # if logging_site.site_id == 'LS2':
#           #   print(f"{self.env.now:.2f}: TP, {truck_itr.truck_id} completed LP, it will take {travel_time_to_sawmill:.2f} to go the the SM")
#           yield self.env.timeout(travel_time_to_sawmill)

#           # Process at the effective sawmill
#           if not effective_sawmill.is_sawmill_open():
#               if (self.env.now % 1440) <= effective_sawmill.sawmill_opening_time:
#                   yield self.env.timeout(effective_sawmill.sawmill_opening_time - (self.env.now % 1440))
#               elif (self.env.now % 1440) > effective_sawmill.sawmill_closing_time:
#                   yield self.env.timeout(1440 - (self.env.now % 1440) + effective_sawmill.sawmill_opening_time)
#               elif self.env.now > duration:
#                   return

#           yield self.env.process(self.sawmill_process(truck_itr, logging_site, effective_sawmill, duration))
#           travel_time_to_logging_site = self.get_travel_time(effective_sawmill.sawmill_id,logging_site.site_id)

#           yield self.env.timeout(travel_time_to_logging_site)

#           # print(f"{self.env.now:.2f}: {truck_itr.truck_id} starts another processing from {logging_site.site_id}")
#           yield self.env.process(self.truck_process(truck_itr, logging_site, duration))

#     def logging_process(self, truck_itr, logging_site, duration):
#       logging_site_start_time = self.env.now

#       # if logging_site.site_id == 'LS2':
#       #         print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} came to the logging site and waiting for the crane ")

#       # Check if logging site has enough wood capacity
#       if logging_site.log_cap_limit.level < truck_itr.truck_capacity:
#           print(f"{self.env.now:.2f}: Not enough wood at logging site {logging_site.site_id}.")
#           return

#       # Calculate time until the end of the day (closing time)
#       time_until_closing = logging_site.closing_time - (self.env.now % 1440)



#       with logging_site.cranes.request() as crane_request:
#           yield crane_request

#           if not logging_site.is_site_open():
#               # if logging_site.site_id == 'LS2':
#               #   print(f"{self.env.now:.2f}: {truck_itr.truck_id} got the crane access but Logging site {logging_site.site_id} is closed. Waiting for opening time.")
#               yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
#               logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

#           # If the truck arrives at the LS after the closing time in the previous day, then the logging start time needs to change
#           if logging_site_start_time % 1440  > logging_site.closing_time:
#               logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

#           if logging_site_start_time//1440 < self.env.now//1440:
#               logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time



#           # Print the number of trucks waiting in the queue
#           queue_length = len(logging_site.cranes.queue)
#           logging_site.queue_lengths.append(queue_length)
#           crane_start_time = self.env.now

#           # Calculate and store the waiting time for the truck
#           site_waiting_period_end = self.env.now
#           waiting_time = site_waiting_period_end - logging_site_start_time
#           logging_site.site_wait_time.append(waiting_time)

#           # if logging_site.site_id == 'LS2':
#           #     print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} got the crane access and {queue_length} trucks are in the queue")

#           # Adjust the start time if the crane is accessed the next day
#           if self.env.now % 1440 < logging_site_start_time % 1440:
#               logging_site_start_time = ((logging_site_start_time // 1440) + 1) * 1440 + logging_site.opening_time

#           mean_loading_time = logging_site.avg_loading_time
#           loading_time = np.random.uniform(low=mean_loading_time-(mean_loading_time/2), high=mean_loading_time+(mean_loading_time/2))
#           # loading_time = mean_loading_time



#           logging_site.loaded_truck_count += 1

#           # Decrease wood capacity
#           yield logging_site.log_cap_limit.get(truck_itr.truck_capacity)

#           loading_processing_start = self.env.now

#           if logging_site.logging_processing_end // 1440 < self.env.now  // 1440 : #or logging_site.logging_processing_end % 1440 > logging_site.closing_time
#               logging_site.logging_processing_end = (self.env.now // 1440) * 1440 + logging_site.opening_time

#           logging_site.loader_idle_time.append(loading_processing_start - logging_site.logging_processing_end)

#           logging_site.total_loading_time.append(loading_time)
#           yield self.env.timeout(loading_time)
#           logging_site.logging_processing_end = self.env.now

#           # Finish loading
#           logging_site.amount_loaded += truck_itr.truck_capacity

#           logging_site.truck_turn_time_in_logging_site.append(logging_site.logging_processing_end - logging_site_start_time)
#           # if logging_site.site_id == 'LS2':
#           #     print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} finished loading")



#     def sawmill_process(self, truck_itr, logging_site, assigned_sawmill, duration):
#       sawmill_start_time = self.env.now
#       sawmill = assigned_sawmill


#       truck_itr.truck_travels_in_sawmill += 1
#       sawmill.truck_arrived += 1
      

#       # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#       #     print(f"{self.env.now:.2f}: SM, Truck {truck_itr.truck_id} just arrived at the sawmill, On basis on arrival truck position: {sawmill.truck_arrived}")


#       # if sawmill.truck_arrived == 1:
#       #   print(f" starting breakdown time for {sawmill.sawmill_id} is {sawmill.breakdown_start} to {sawmill.breakdown_end}")

#       # Check if logging site has enough wood capacity
#       if sawmill.filled_amount.level + truck_itr.truck_capacity > sawmill.filled_amount.capacity:
#           #print(f"{self.env.now:.2f}: Not enough space in sawmill {sawmill.sawmill_id}. Truck {truck_itr.truck_id} cannot unload.")
#           return
#       if ((self.env.now % 1440) < sawmill.sawmill_opening_time):
#             yield self.env.timeout(sawmill.sawmill_opening_time - (self.env.now % 1440))
#             sawmill_start_time = self.env.now


#       with sawmill.scale_in.request() as scale_in_request:
#             yield scale_in_request
#             queue_length = len(sawmill.scale_in.queue)
#             sawmill.sawmill_queue_lengths.append(queue_length)

#             wait_time_scale_in = self.env.now - sawmill_start_time
#             sawmill.scale_in_wait_times.append(wait_time_scale_in)

#             # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#             #   print(f"{self.env.now:.2f}: SM, scale in for truck {truck_itr.truck_id} and in the scale in queue we have {queue_length} trucks")


#             yield self.env.timeout( sawmill.scale_in_time)
#             # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#             #   print(f"{self.env.now:.2f}: scale in completed for truck {truck_itr.truck_id}")

#       scale_in_end_time = self.env.now
#       yield self.env.timeout(sawmill.scale_in_to_unload_time)
#       # yield self.env.timeout(sawmill.scale_in_to_unload_time)
#       sawmill.scale_in_to_crane_times.append(self.env.now -scale_in_end_time)


#       # Crane process for unloading
#       crane_wait_start_time = self.env.now
#       with assigned_sawmill.truck_waiting_area.request() as waiting_request:
#           yield waiting_request


#       # if (sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end):
#       #   if(sawmill.crane1_operational == False and sawmill.crane2_operational == False):
#       #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)





#       with sawmill.cranes_in_sawmill.request() as crane_request:
#             yield crane_request
#             crane_id = sawmill.assign_crane()  # Attempt to assign a crane
#             queue_length_crane = len(sawmill.cranes_in_sawmill.queue)
#             #wait_time_crane = self.env.now - crane_wait_start_time

#             wait_time_crane = self.env.now - scale_in_end_time
#             sawmill.truck_wait_time_in_crane.append(wait_time_crane)
#             # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#             #     print(f"{self.env.now:.2f}:  {truck_itr.truck_id} got the crane access after {(self.env.now-scale_in_end_time):.2f} time and got the crane {crane_id+1} access and {queue_length_crane} trucks are in the crane queue")

#             # if sawmill.breakdown_end < self.env.now:
#             #   sawmill.breakdown_number += 1
#             #   sawmill.missed_breakdown += 1
#             #   # sawmill.breakdown_countdown = 0
#             #   # sawmill.breakdown_start = self.env.now + np.random.exponential(scale=self.mtbf)
#             #   # sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
#             #   sawmill.breakdown_start = sawmill.breakdown_start + 1440
#             #   sawmill.breakdown_end = sawmill.breakdown_end + 1440
#             #   # if sawmill.sawmill_id == 'SM1':
#             #   #   print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: previous breakdown happened when the sawmill was close")
#             #   # print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: Next breakdown will be happended from {sawmill.breakdown_start:.2f} to {sawmill.breakdown_end:.2f}")




#             # # If the previous crane unloading happend the previous day then it will be assigned as current time
#             if crane_id == 0:
#                 # Check if the unloading happened on the previous day or the time exceeds the closing time
#                 if sawmill.crane1_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane1_unloading_end % 1440 > sawmill.sawmill_closing_time:
#                     # Adjust the unloading time to the current day's opening time
#                     pre_crane1_unloading_end = sawmill.crane1_unloading_end
#                     sawmill.crane1_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time
#                     # print(f"{self.env.now:.2f}: For truck {truck_itr.truck_id}, Crane 1 unloading time adjusted from {pre_crane1_unloading_end:.2f} to {sawmill.crane1_unloading_end:.2f}")

#             elif crane_id == 1:
#                 # Same check for crane 2
#                 if sawmill.crane2_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane2_unloading_end % 1440 > sawmill.sawmill_closing_time:
#                     pre_crane2_unloading_end = sawmill.crane2_unloading_end
#                     sawmill.crane2_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time
#                     # print(f"{self.env.now:.2f}: For truck {truck_itr.truck_id}, Crane 2 unloading time adjusted from {pre_crane2_unloading_end:.2f} to {sawmill.crane2_unloading_end:.2f}")


#             # If the breakdown happend when unloading, then the truck cannot unload the timbers
#             # thats why we will check if the breakdown will happend on unloading or not. If we find the breakdown will
#             # happend during the unloading then we will stop unloading for that truck

#             unload_time_mean = sawmill.unload_time_mean
#             unload_time = np.random.uniform(low=unload_time_mean-(unload_time_mean/2), high=unload_time_mean+(unload_time_mean/2))

#             # if((sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end)):
#             #   if (crane_id == 0 and sawmill.breakdown_countdown == 0):
#             #     sawmill.breakdown_countdown = 1
#             #     # if sawmill.sawmill_id == 'SM1':
#             #     #   print(f"{self.env.now:.2f}: Breakdown happeneded")
#             #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)

#             # if sawmill.breakdown_start <= (self.env.now+unload_time) <= sawmill.breakdown_end:
#             #   if (crane_id == 0 and sawmill.breakdown_countdown == 0):
#             #     sawmill.breakdown_countdown =  1
#             #     # if sawmill.sawmill_id == 'SM1':
#             #     #   print(f"{self.env.now:.2f}: Breakdown happeneded")
#             #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)



#             # if sawmill.breakdown_countdown == 1:
#             #   sawmill.breakdown_number += 1
#             #   sawmill.breakdown_countdown = 0
#             #   # As it checked the current breakdown and processed the action, now new breakdown schedule is assigned
#             #   # sawmill.breakdown_start = sawmill.breakdown_end + np.random.exponential(scale=self.mtbf)
#             #   # sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
#             #   sawmill.breakdown_start = sawmill.breakdown_start + 1440
#             #   sawmill.breakdown_end = sawmill.breakdown_end + 1440

#             #   # print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: Next breakdown will be happended from {sawmill.breakdown_start:.2f} to {sawmill.breakdown_end:.2f}")

#             # crane_unloading_start = self.env.now
#             if(crane_id == 0):
#               crane1_unloading_start = self.env.now
#             else:
#               crane2_unloading_start = self.env.now

#             if ((self.env.now % 1440) < sawmill.sawmill_closing_time):

#               if(crane_id == 0): #Crane 1's data for processing is in here
#                 crane1_idle = crane1_unloading_start - sawmill.crane1_unloading_end
#                 sawmill.crane1_idle_time.append( crane1_idle )
#                 yield sawmill.filled_amount.put(truck_itr.truck_capacity)
#                 yield self.env.timeout(unload_time)
#                 sawmill.crane1_unloading_time.append(unload_time)
#                 sawmill.crane1_processed_truck += 1
#                 # if(sawmill.sawmill_id == 'SM1' and crane1_idle > 100):
#                 #   print(f"{self.env.now:.2f}: Crane 1 idle time greater than 100 for {truck_itr.truck_id}, unloading start time was {crane1_unloading_start:.2f} and previous unloading end was {sawmill.crane1_unloading_end:.2f} and idle time is {crane1_idle:.2f}")
#                 #   print(f"truck in the queue: {queue_length}")

#                 sawmill.crane1_unloading_end = self.env.now
#                 # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#                 #     print(f"{self.env.now:.2f}: Crane 1 unloading finished for {truck_itr.truck_id}")


#               else: #Crane 2's data for processing is in here
#                 crane2_idle = crane2_unloading_start - sawmill.crane2_unloading_end
#                 sawmill.crane2_idle_time.append(crane2_idle )
#                 yield sawmill.filled_amount.put(truck_itr.truck_capacity)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
#                 yield self.env.timeout(unload_time)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
#                 sawmill.crane2_unloading_time.append(unload_time)
#                 sawmill.crane2_processed_truck += 1
#                 # if(sawmill.sawmill_id == 'SM1' and crane2_idle > 100):
#                 #   print(f"{self.env.now:.2f}: Crane 2 idle time greater than 100 for {truck_itr.truck_id}, unloading start time was {crane2_unloading_start:.2f} and previous unloading end was {sawmill.crane2_unloading_end:.2f} and idle time is {crane2_idle:.2f}")
#                 #   print(f"truck in the queue: {queue_length}")

#                 sawmill.crane2_unloading_end = self.env.now
#                 # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#                 #     print(f"{self.env.now:.2f}: Crane 2 unloading finished for {truck_itr.truck_id}")

#             else: #Overtime data will be in here
#               if(crane_id == 0): #Crane 1's data for processing is in here
#                 #Crane's idle time will not be counted as it is overtime
#                 # sawmill.crane1_idle_time.append(crane_unloading_start - sawmill.crane1_unloading_end )
#                 yield sawmill.filled_amount.put(truck_itr.truck_capacity)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
#                 yield self.env.timeout(unload_time)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
#                 sawmill.crane1_over_time.append(unload_time)

#                 sawmill.crane1_processed_truck_on_overtime += 1

#                 sawmill.crane1_unloading_end = self.env.now
#                 # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#                 #     print(f"{self.env.now:.2f}: Crane 1 overtime unloading finished for {truck_itr.truck_id}")

#               else: #Crane 1's data for processing is in here
#                 #Crane's idle time will not be counted as it is overtime
#                 # sawmill.crane1_idle_time.append(crane_unloading_start - sawmill.crane1_unloading_end )
#                 yield sawmill.filled_amount.put(truck_itr.truck_capacity)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
#                 yield self.env.timeout(unload_time)
#                 #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
#                 sawmill.crane2_over_time.append(unload_time)

#                 sawmill.crane2_processed_truck_on_overtime += 1

#                 sawmill.crane2_unloading_end = self.env.now
#                 # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#                 #     print(f"{self.env.now:.2f}: Crane 2 overtime unloading finished for {truck_itr.truck_id}")


#             # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#             #   print(f"{self.env.now:.2f}: Truck {truck_itr.truck_id} has unloaded at sawmill {sawmill.sawmill_id}.")
#             sawmill.Number_of_Trucks_Unloaded += 1
#             sawmill.Total_Amount_Unloaded_in_Tons += truck_itr.truck_capacity

#             assigned_sawmill.release_crane(crane_id)



#       # Fixed unloading to scale out traveling time
#       crane_end_time = self.env.now
#       yield self.env.timeout(sawmill.unload_to_scale_out_time)
#       # yield self.env.timeout(sawmill.unload_to_scale_out_time)
#       sawmill.crane_to_scale_out_times.append(self.env.now - crane_end_time)

#       # Scale out process
#       scale_out_waiting_start = self.env.now
#       with sawmill.scale_out.request() as scale_out_request:
#             yield scale_out_request

#             wait_time_scale_out = self.env.now -scale_out_waiting_start
#             sawmill.scale_out_wait_times.append(wait_time_scale_out)
#             # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#             #   print(f"{self.env.now:.2f} : Truck:{truck_itr.truck_id} got out after scale out")
#             # Fixed time at scale out
#             # yield self.env.timeout(np.random.exponential(scale=sawmill.scale_out_time))
#             yield self.env.timeout(sawmill.scale_out_time)
#             sawmill.truck_departed += 1

#       turn_time = self.env.now - sawmill_start_time
#       sawmill.truck_turn_time_in_sawmill.append(turn_time)
#       # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
#       #   print(f"{self.env.now:.2f} : SM, Crane : {crane_id} Truck:{truck_itr.truck_id} Truck position: {sawmill.Number_of_Trucks_Unloaded} Queue length: {queue_length} Sc.Wait: {wait_time_scale_in:.2f} Crane wait : {wait_time_crane:.2f} Turn time: {turn_time:.2f}")


#     def start_simulation(self, duration):
#         self.env.process(self.truck_generate(duration))
#         self.env.run(until=duration)

#         for truck in self.trucks:
#             gb.trucks_no_of_travel_in_sawmill1.append(truck.truck_travels_in_sawmill)

#         # Update gb.trucks_no_of_travel_in_sawmill2 using add_lists_with_padding
#         if len(gb.trucks_no_of_travel_in_sawmill2) == 0:
#             gb.trucks_no_of_travel_in_sawmill2 = gb.trucks_no_of_travel_in_sawmill1[:]
#             gb.trucks_no_of_travel_count = [1] * len(gb.trucks_no_of_travel_in_sawmill1)  # Initialize the count list
#         else:
#             gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_count = add_lists_with_padding(
#                 gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_in_sawmill1,
#                 gb.trucks_no_of_travel_count, [1] * len(gb.trucks_no_of_travel_in_sawmill1)
#             )

#         gb.trucks_no_of_travel_in_sawmill1 = []  # Reset the temporary list









import simpy
import numpy as np

from entities import LoggingSite, Sawmill, LoggingCompany, Truck
import global_variables as gb
from sawmill_utilities import add_lists_with_padding

class Model1:
    def __init__(self, env, logging_site_data, sawmill_data, company_data, truck_data, travel_times_data, mtbf, mttr):
        self.env = env
        self.sawmills = {}
        self.logging_sites = {}
        self.companies = {}
        self.trucks = []
        self.travel_times = travel_times_data
        self.total_truck_generated = 0
        self.mtbf = mtbf
        self.mttr = mttr

        # Initialize Sawmill instances
        for row in sawmill_data.itertuples():
            sawmill_id = str(row.sawmill_id)
            sawmill_obj = Sawmill(
                env,
                sawmill_id=sawmill_id,
                sawmill_name=row.sawmill_name,
                sawmill_location=row.sawmill_location,
                sawmill_opening_time=row.sawmill_opening_time,
                sawmill_closing_time=row.sawmill_closing_time,
                sawmill_capacity=row.sawmill_capacity,
                sawmill_total_crane=row.sawmill_total_crane,
                truck_area_capacity=row.truck_area_capacity,
                scale_in_time=float(row.scale_in_time),
                scale_out_time=float(row.scale_out_time),
                scale_in_to_unload_time=float(row.scale_in_to_unload_time),
                unload_to_scale_out_time=float(row.unload_to_scale_out_time),
                unload_time_mean=float(row.unload_time_mean),
                breakdown_start=row.breakdown_start,
                breakdown_end=row.breakdown_end
            )
            sawmill_obj.crane1_operational = True
            sawmill_obj.crane2_operational = True
            sawmill_obj.breakdown_schedule = [(row.breakdown_start, row.breakdown_end)]
            self.sawmills[sawmill_id] = sawmill_obj

        # Initialize LoggingSite instances
        for row in logging_site_data.itertuples():
            site_id = str(getattr(row, 'site_id'))
            sawmill_id = str(getattr(row, 'sawmill', None))
            company_id = str(getattr(row, 'company_id', None))

            self.logging_sites[site_id] = LoggingSite(
                env,
                site_id=site_id,
                sawmill=self.sawmills.get(sawmill_id),
                company_id=company_id,
                latitude=row.latitude,
                longitude=row.longitude,
                avg_loading_time=row.avg_loading_time,
                opening_time=row.opening_time,
                closing_time=row.closing_time,
                site_cranes=row.site_cranes,
                initial_log_capacity=row.initial_log_capacity
            )

        # Initialize Company instances
        for _, row in company_data.iterrows():
            company_id = str(row['company_id'])
            company = LoggingCompany(
                env,
                company_id=company_id,
                num_trucks=row['num_trucks'],
                sawmill=self.sawmills.get(row['sawmill']),
                logging_site=self.logging_sites.get(row['logging_site']),
                mean_truck_generate_interval=row['mean_truck_generate_interval']
            )
            company.logging_sites = self.logging_sites.get(row['logging_site'])
            self.companies[company_id] = company

        # Initialize Truck instances
        for _, row in truck_data.iterrows():
            truck_id = str(row['truck_id'])
            company_id = str(row['company_id'])
            truck_capacity = row['truck_capacity']

            company = self.companies.get(company_id)
            truck = Truck(env, truck_id, company_id, truck_capacity)
            self.trucks.append(truck)
            if company:
                company.trucks.append(truck)

    def get_travel_time(self, sawmill_loc, logging_site_loc):
        travel_times_data = self.travel_times
        filtered = travel_times_data[(travel_times_data['Sawmill'] == sawmill_loc) & (travel_times_data['LoggingSite'] == logging_site_loc)]
        return filtered['Total_TruckTravelTime'].sum() if not filtered.empty else 0

    def find_effective_sawmill(self, logging_site_id, assigned_sawmill_id):
        lowest_time = float('inf')
        effective_sawmill = None

        for sawmill_id, sawmill in self.sawmills.items():
            if sawmill_id == assigned_sawmill_id:
                continue
            if not (sawmill.crane1_operational and sawmill.crane2_operational):
                continue
            if len(sawmill.scale_in.queue) >= 20:
                continue
            try:
                travel_time = self.get_travel_time(logging_site_id, sawmill_id)
                if travel_time < lowest_time:
                    lowest_time = travel_time
                    effective_sawmill = sawmill
            except Exception:
                continue
        return effective_sawmill

    def truck_generate(self, duration):
        if not self.companies:
            print("No companies found. Skipping truck generation.")
            return

        max_trucks = max((len(company.trucks) for company in self.companies.values()), default=0)

        while self.env.now < duration:
            for n in range(max_trucks):
                for company in self.companies.values():
                    if n < len(company.trucks):
                        truck = company.trucks[n]
                        logging_site = company.logging_sites
                        self.total_truck_generated += 1
                        self.env.process(self.truck_process(truck, logging_site, duration))
                yield self.env.timeout(company.mean_truck_generate_interval)
                if self.env.now >= duration:
                    break
            break

    def truck_process(self, truck, logging_site, duration):
        while self.env.now < duration:
            if not logging_site.is_site_open():
              # if logging_site.site_id == 'LS2':
              #   print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is closed. Waiting for opening time. Have to wait for {(1440 - (self.env.now % 1440) + logging_site.opening_time):.2f} minutes")
              yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
              yield self.env.process(self.logging_process(truck, logging_site, duration))
            else:
                # print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is open.")
                yield self.env.process(self.logging_process(truck, logging_site, duration))

            assigned_sawmill = logging_site.sawmill
            effective_sawmill = assigned_sawmill

            #Based on the breakdown type the following will be change;
            #For this time we are working for no breakdown
            for start, end in assigned_sawmill.breakdown_schedule:
                current_time = self.env.now
                if start <= current_time < end:
                    assigned_sawmill.crane1_operational = True
                    assigned_sawmill.crane2_operational = True
                else:
                    assigned_sawmill.crane1_operational = True
                    assigned_sawmill.crane2_operational = True


            if not assigned_sawmill.crane1_operational and not assigned_sawmill.crane2_operational:
                effective_sawmill = self.find_effective_sawmill(logging_site.site_id, assigned_sawmill.sawmill_id)
                if effective_sawmill is None:
                    #print(f"Sawmill: {assigned_sawmill.sawmill_id} Breakdown start time {assigned_sawmill.breakdown_start} and end time {assigned_sawmill.breakdown_end} and none of the sawmill was found to transfer the truck")
                    yield self.env.timeout(assigned_sawmill.breakdown_end - self.env.now)
                    effective_sawmill = assigned_sawmill  # Reassign to original sawmill after waiting
                else:
                    assigned_sawmill.truck_diverted_from_sawmill += 1

            travel_time_to_sawmill = self.get_travel_time(effective_sawmill.sawmill_id, logging_site.site_id)
            yield self.env.timeout(travel_time_to_sawmill)

            if not effective_sawmill.is_sawmill_open():
                now = self.env.now % 1440
                if now <= effective_sawmill.sawmill_opening_time:
                    yield self.env.timeout(effective_sawmill.sawmill_opening_time - now)
                elif now > effective_sawmill.sawmill_closing_time:
                    yield self.env.timeout(1440 - now + effective_sawmill.sawmill_opening_time)

            yield self.env.process(self.sawmill_process(truck, logging_site, effective_sawmill, duration))
            yield self.env.timeout(self.get_travel_time(effective_sawmill.sawmill_id, logging_site.site_id))#This time is travel time from SM to LS

    def logging_process(self, truck, logging_site, duration):
        logging_site_start_time = self.env.now
        if not logging_site.is_site_open():
            yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)

        with logging_site.cranes.request() as request:
            yield request
            wait_time = 0
            wait_time_for_ls = 0 
            if not logging_site.is_site_open():
                wait_time_for_ls = 1440 - (self.env.now % 1440) + logging_site.opening_time
                yield self.env.timeout(wait_time_for_ls)
                logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

            # If the truck arrives at the LS after the closing time in the previous day, then the logging start time needs to change
            if logging_site_start_time % 1440  > logging_site.closing_time:
                logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

            if logging_site_start_time//1440 < self.env.now//1440:
                logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

            site_waiting_period_end = self.env.now
            wait_time = site_waiting_period_end - logging_site_start_time
            logging_site.queue_lengths.append(len(logging_site.cranes.queue))
            logging_site.site_wait_time.append(wait_time)
            
            # Adjust the start time if the crane is accessed the next day
            if self.env.now % 1440 < logging_site_start_time % 1440:
                logging_site_start_time = ((logging_site_start_time // 1440) + 1) * 1440 + logging_site.opening_time

            loading_time = np.random.uniform(
                low=logging_site.avg_loading_time / 2,
                high=logging_site.avg_loading_time * 1.5
            )
            logging_site.total_loading_time.append(loading_time)
            yield self.env.timeout(loading_time)
            logging_site.amount_loaded += truck.truck_capacity
            logging_site.loaded_truck_count += 1

    def sawmill_process(self, truck, logging_site, sawmill, duration):
        if sawmill.filled_amount.level + truck.truck_capacity > sawmill.filled_amount.capacity:
            return

        with sawmill.scale_in.request() as scale_in_request:
            yield scale_in_request
            sawmill.sawmill_queue_lengths.append(len(sawmill.scale_in.queue))
            sawmill.scale_in_wait_times.append(self.env.now)
            yield self.env.timeout(sawmill.scale_in_time)

        yield self.env.timeout(sawmill.scale_in_to_unload_time)

        with sawmill.truck_waiting_area.request():
            with sawmill.cranes_in_sawmill.request() as crane_request:
                yield crane_request
                crane_id = sawmill.assign_crane()
                wait_time = self.env.now
                sawmill.truck_wait_time_in_crane.append(wait_time)
                unload_time = np.random.uniform(
                    low=sawmill.unload_time_mean / 2,
                    high=sawmill.unload_time_mean * 1.5
                )

                if crane_id == 0:
                    sawmill.crane1_idle_time.append(self.env.now - sawmill.crane1_unloading_end)
                    sawmill.crane1_unloading_time.append(unload_time)
                    sawmill.crane1_unloading_end = self.env.now + unload_time
                    sawmill.crane1_processed_truck += 1
                else:
                    sawmill.crane2_idle_time.append(self.env.now - sawmill.crane2_unloading_end)
                    sawmill.crane2_unloading_time.append(unload_time)
                    sawmill.crane2_unloading_end = self.env.now + unload_time
                    sawmill.crane2_processed_truck += 1

                yield sawmill.filled_amount.put(truck.truck_capacity)
                yield self.env.timeout(unload_time)

        yield self.env.timeout(sawmill.unload_to_scale_out_time)

        with sawmill.scale_out.request() as scale_out_request:
            yield scale_out_request
            sawmill.scale_out_wait_times.append(self.env.now)
            yield self.env.timeout(sawmill.scale_out_time)
            sawmill.truck_departed += 1
            sawmill.truck_turn_time_in_sawmill.append(self.env.now)

    def start_simulation(self, duration):
        self.env.process(self.truck_generate(duration))
        self.env.run(until=duration)

        for truck in self.trucks:
            gb.trucks_no_of_travel_in_sawmill1.append(truck.truck_travels_in_sawmill)

        if not gb.trucks_no_of_travel_in_sawmill2:
            gb.trucks_no_of_travel_in_sawmill2 = gb.trucks_no_of_travel_in_sawmill1[:]
            gb.trucks_no_of_travel_count = [1] * len(gb.trucks_no_of_travel_in_sawmill1)
        else:
            gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_count = add_lists_with_padding(
                gb.trucks_no_of_travel_in_sawmill2,
                gb.trucks_no_of_travel_in_sawmill1,
                gb.trucks_no_of_travel_count,
                [1] * len(gb.trucks_no_of_travel_in_sawmill1)
            )

        gb.trucks_no_of_travel_in_sawmill1 = []
