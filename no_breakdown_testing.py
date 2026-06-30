#**No crane** broken Parallel processing for 4 sawmill- 30 days - Fixed breakdown time, with uniform random time- 1 replication

##Package install

#  !pip install simpy

import simpy
import random
import numpy as np
import matplotlib.pyplot as plt
from itertools import cycle

import pandas as pd

##Data

data = pd.ExcelFile('timber_59_sawmill.xlsx')
# logging_site_data = pd.read_excel(data, 'LoggingSite')
# sawmill_data = pd.read_excel(data, 'Sawmill')
# company_data = pd.read_excel(data, 'Company')
# truck_data = pd.read_excel(data, 'Truck')
# travel_times_data = pd.read_excel(data, 'Travel_times')

all_logging_site_data = pd.read_excel(data, 'LoggingSite')
all_sawmill_data = pd.read_excel(data, 'Sawmill')
all_company_data = pd.read_excel(data, 'Company')
all_truck_data = pd.read_excel(data, 'Truck')
travel_times_data = pd.read_excel(data, 'Travel_times')

sawmill_number = input("Enter the Sawmill number as SM1, SM2 and so on: ")

logging_site_data = all_logging_site_data[all_logging_site_data['sawmill'] == sawmill_number]
sawmill_data = all_sawmill_data[all_sawmill_data['sawmill_id'] == sawmill_number]
company_data = all_company_data[all_company_data['sawmill'] == sawmill_number]
# Get all company IDs related to this sawmill
company_ids = company_data['company_id'].unique()

# Now filter the trucks for those company_ids
truck_data = all_truck_data[all_truck_data['company_id'].isin(company_ids)]



travel_times_data.head()

# Update the code to use the correct column name
filtered_df = travel_times_data[(travel_times_data['Sawmill'] == 'SM1') & (travel_times_data['LoggingSite'] == 'LS8')]

# Calculate the total time
total_time = filtered_df['Total_TruckTravelTime'].sum()

# Print the element:
print(total_time)

logging_site_data

sawmill_data

company_data

truck_data

##Global Variables

#Global variables
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
    self.truck_waiting_area = simpy.Resource(env, capacity=8)
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

  def __init__(self, env, site_id, company_id, latitude, longitude, avg_loading_time, opening_time, closing_time, site_cranes,initial_log_capacity, sawmill, **kwargs):
    self.env = env
    self.site_id = site_id
    self.company_id = company_id
    self.latitude = latitude
    self.longitude = longitude
    self.avg_loading_time = avg_loading_time
    self.opening_time = opening_time
    self.closing_time = closing_time
    self.site_cranes = site_cranes
    self.sawmill = sawmill


    # Initialize the cranes resource
    self.cranes = simpy.Resource(env, capacity=self.site_cranes)
    self.log_cap_limit = simpy.Container(env, init = initial_log_capacity, capacity=initial_log_capacity)

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

print(logging_site_data.columns)

print(sawmill_data.columns)

##Function

# def add_lists_in_place(list1, list2):
#     """Adds elements between two lists, padding with zeros for different lengths,
#     modifying the first list in-place.

#     Args:
#         list1: The first list (will be modified).
#         list2: The second list.

#     Returns:
#         The modified list1 containing the sum of corresponding elements with padding.
#     """

#     # Handle potential integers (convert to lists if necessary)
#     if isinstance(list1, int):
#         list1 = [list1]
#     if isinstance(list2, int):
#         list2 = [list2]

#     # Get the maximum length of the two lists
#     max_length = max(len(list1), len(list2))

#     # Extend the shorter list with zeros
#     if len(list1) < max_length:
#         list1.extend([0] * (max_length - len(list1)))
#     if len(list2) < max_length:
#         list2.extend([0] * (max_length - len(list2)))

#     # Add corresponding elements
#     for i in range(max_length):
#         list1[i] += list2[i]

#     return list1


# def average_elements(summed_list, num_iterations):
#     """Calculates the average of each element in a summed list by the number of iterations.

#     Args:
#         summed_list: A list containing the summed values of elements from multiple iterations.
#         num_iterations: The number of iterations that contributed to the summed_list.

#     Returns:
#         A list containing the average of each element.
#     """
#     if num_iterations == 0:
#         raise ValueError("Number of iterations must be greater than zero.")

#     return [element / num_iterations for element in summed_list]

# def add_and_average(list1, list2):
#     """Adds elements between two lists, padding with zeros for different lengths,
#     and calculates the average based on how many times each position was added.

#     Args:
#         list1: The first list.
#         list2: The second list.

#     Returns:
#         A list containing the average of each element.
#     """

#     # Get the maximum length of the two lists
#     max_length = max(len(list1), len(list2))

#     # Extend the shorter list with zeros
#     if len(list1) < max_length:
#         list1.extend([0] * (max_length - len(list1)))
#     if len(list2) < max_length:
#         list2.extend([0] * (max_length - len(list2)))

#     # Add corresponding elements and count occurrences
#     summed_list = []
#     counts = []
#     for i in range(max_length):
#         summed_value = list1[i] + list2[i]
#         count = (1 if list1[i] != 0 else 0) + (1 if list2[i] != 0 else 0)
#         summed_list.append(summed_value)
#         counts.append(count)

#     # Calculate averages
#     averaged_list = [summed_list[i] / counts[i] if counts[i] != 0 else 0 for i in range(max_length)]

#     return averaged_list



##Model

class Model:
    def __init__(self, env, logging_site_data, sawmill_data, company_data, truck_data, travel_times_data, mtbf, mttr ):
        self.env = env
        # Initialize dictionaries to hold instances
        self.sawmills = {}
        self.logging_sites = {}
        self.companies = {}
        self.trucks = []
        self.travel_times = travel_times_data
        self.total_truck_generated = 0
        self.mtbf = mtbf
        self.mttr = mttr


        # Creating Sawmill instances
        for sawmill_row in sawmill_data.itertuples():
          sawmill_id = str(sawmill_row.sawmill_id)
          sawmill_name = sawmill_row.sawmill_name
          sawmill_location = sawmill_row.sawmill_location
          sawmill_opening_time = sawmill_row.sawmill_opening_time
          sawmill_closing_time = sawmill_row.sawmill_closing_time
          sawmill_capacity = sawmill_row.sawmill_capacity
          sawmill_total_crane = sawmill_row.sawmill_total_crane
          truck_area_capacity = sawmill_row.truck_area_capacity
          scale_in_time = sawmill_row.scale_in_time
          scale_out_time = sawmill_row.scale_out_time
          scale_in_to_unload_time = sawmill_row.scale_in_to_unload_time
          unload_to_scale_out_time = sawmill_row.unload_to_scale_out_time
          unload_time_mean = sawmill_row.unload_time_mean
          breakdown_start = sawmill_row.breakdown_start
          breakdown_end = sawmill_row.breakdown_end
          # breakdown_start = np.random.exponential(scale=self.mtbf)
          # breakdown_end = breakdown_start + np.random.exponential(scale=self.mttr)


          self.sawmills[sawmill_id] = Sawmill(
              env,
              sawmill_id=sawmill_id,
              sawmill_name=sawmill_name,
              sawmill_location=sawmill_location,
              sawmill_opening_time=sawmill_opening_time,
              sawmill_closing_time=sawmill_closing_time,
              sawmill_capacity=sawmill_capacity,
              sawmill_total_crane=sawmill_total_crane,
              truck_area_capacity=truck_area_capacity,
              scale_in_time = int(scale_in_time),
              scale_out_time = int(scale_out_time),
              scale_in_to_unload_time = int(scale_in_to_unload_time),
              unload_to_scale_out_time = int(unload_to_scale_out_time),
              unload_time_mean = int(unload_time_mean),
              breakdown_start = breakdown_start,
              breakdown_end = breakdown_end
          )
          # self.env.process(self.crane_breakdown_process(self.sawmills[sawmill_id]))




        # Creating LoggingSite instances and associating them with Sawmills
        for logging_site_row in logging_site_data.itertuples():
            site_id = str(getattr(logging_site_row, 'site_id'))
            sawmill_id = str(getattr(logging_site_row, 'sawmill', None))
            company_id = str(getattr(logging_site_row, 'company_id', None))

            self.logging_sites[site_id] = LoggingSite(
                env,
                site_id=site_id,
                sawmill=self.sawmills.get(sawmill_id),
                company_id=company_id,
                latitude=logging_site_row.latitude,
                longitude=logging_site_row.longitude,
                avg_loading_time=logging_site_row.avg_loading_time,
                opening_time=logging_site_row.opening_time,
                closing_time=logging_site_row.closing_time,
                site_cranes=logging_site_row.site_cranes,
                initial_log_capacity=logging_site_row.initial_log_capacity
            )



        # Creating Company instances
        for _, company_row in company_data.iterrows():
            company_id = str(company_row['company_id'])
            self.companies[company_id] = LoggingCompany(
                env,
                company_id=company_id,
                num_trucks=company_row['num_trucks'],
                sawmill=self.sawmills[company_row['sawmill']] if company_row['sawmill'] in self.sawmills else None,
                logging_site=self.logging_sites[company_row['logging_site']] if company_row['logging_site'] in self.logging_sites else None,
                mean_truck_generate_interval = company_row['mean_truck_generate_interval']
            )


        # Create instances of trucks
        for _, truck_row in truck_data.iterrows():
            truck_id = str(truck_row['truck_id'])
            company_id = str(truck_row['company_id'])
            truck_capacity = truck_row['truck_capacity']  # Make sure this column exists in your dataframe

            # Check if the company exists before trying to add the truck to it
            if company_id in self.companies:
                company = self.companies[company_id]
            else:
                #print(f"Company with ID {company_id} not found for truck {truck_id}.")
                company = None

            truck = Truck(env, truck_id, company_id, truck_capacity)  # Pass all required arguments to the Truck constructor
            self.trucks.append(truck)

            # Append the truck to the company's truck list if the company exists
            if company:
                company.trucks.append(truck)



    #-----------------------Functions------------------------------

    # A function to lookup travel time between two locations
    def get_travel_time(self, sawmill_location, logging_site_location):
      filtered_df = travel_times_data[(travel_times_data['Sawmill'] == sawmill_location) & (travel_times_data['LoggingSite'] == logging_site_location)]

      # Calculate the total time
      total_time = filtered_df['Total_TruckTravelTime'].sum()
      return total_time

    # A function to find the sawmill with the lowest travel time
    def find_effective_sawmill(self, logging_site_id, assigned_sawmill_id):
        lowest_time = float('inf')
        effective_sawmill = None

        for sawmill_id, sawmill in self.sawmills.items():
            if sawmill_id == assigned_sawmill_id:
                continue  # Skip the assigned sawmill

            # Check if both cranes are operational
            if not (sawmill.crane1_operational and sawmill.crane2_operational) or len(sawmill.scale_in.queue) >= 20:
                continue
            try:
                travel_time = self.get_travel_time(logging_site_id, sawmill_id)
                if travel_time < lowest_time:
                    lowest_time = travel_time
                    effective_sawmill = sawmill
            except ValueError:
                continue  # Skip if no travel time data available

        # if effective_sawmill is None:
        #     raise ValueError(f"No alternative sawmill found for logging site {logging_site_id}")

        return effective_sawmill


    def truck_generate(self, duration):
      # Calculate the maximum number of trucks any company has
      max_trucks = max(len(company.trucks) for company in self.companies.values())

      # Keep generating trucks until the simulation ends
      while self.env.now < duration:
          # Generate the nth truck for each company simultaneously
          for n in range(max_trucks):
              for company in self.companies.values():
                  if n < len(company.trucks):  # Check if the company has an nth truck
                      truck = company.trucks[n]
                      logging_site = company.logging_sites  # Assuming one logging site per company
                      self.total_truck_generated += 1
                      self.env.process(self.truck_process(truck, logging_site, duration))

              # After starting a truck for each company, wait for the next generation interval
              # yield self.env.timeout(np.random.exponential(scale=company.mean_truck_generate_interval))
              yield self.env.timeout(company.mean_truck_generate_interval)

              # Check if duration of the simulation is reached, if so break the loop
              if self.env.now >= duration:
                  #print(f"Simulation ended at {self.env.now} with {self.total_truck_generated} trucks generated.")
                  break
          #print(f"***********************Total trucks generated in this interval: {self.total_truck_generated}********************")
          break

    def truck_process(self, truck_itr, logging_site, duration):
      while True:
          gb.truck_create += 1

          # if logging_site.site_id == 'LS2':
          #     print(f"{self.env.now:.2f}: TP, {truck_itr.truck_id} started truck processing ")

          # Wait if logging site is not open
          if not logging_site.is_site_open():
              # if logging_site.site_id == 'LS2':
              #   print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is closed. Waiting for opening time. Have to wait for {(1440 - (self.env.now % 1440) + logging_site.opening_time):.2f} minutes")
              yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
              yield self.env.process(self.logging_process(truck_itr, logging_site, duration))
          else:
              # print(f"{self.env.now:.2f}: {truck_itr.truck_id} Logging site {logging_site.site_id} is open.")
              yield self.env.process(self.logging_process(truck_itr, logging_site, duration))

          # Ensure logging site has an associated sawmill
          if logging_site.sawmill is None:
              print(f"No sawmill associated with logging site {logging_site.site_id}")
              return

          assigned_sawmill = logging_site.sawmill
          effective_sawmill = assigned_sawmill  # Default sawmill is the assigned one
          site_location = logging_site

          # Check crane operational status during breakdown
          current_time = self.env.now
          if assigned_sawmill.breakdown_start is not None and assigned_sawmill.breakdown_end is not None:

              #The next for loop check when the current time is between breakdown schedule the crane will assign as inactive
              # otherwise it will remain active. This will be checked every time for a truck process
            
            #Change here for web interface 
              for start, end in assigned_sawmill.breakdown_schedule:
                  if start <= current_time < end:
                      assigned_sawmill.crane1_operational = True
                      assigned_sawmill.crane2_operational = True

                  else:
                      assigned_sawmill.crane1_operational = True
                      assigned_sawmill.crane2_operational = True

              #The next logic check when the both crane is inactive it will find the new effective sawmill

              if not assigned_sawmill.crane1_operational and not assigned_sawmill.crane2_operational:
                effective_sawmill = self.find_effective_sawmill(logging_site.site_id, assigned_sawmill.sawmill_id)
                if effective_sawmill is None:
                    #print(f"Sawmill: {assigned_sawmill.sawmill_id} Breakdown start time {assigned_sawmill.breakdown_start} and end time {assigned_sawmill.breakdown_end} and none of the sawmill was found to transfer the truck")
                    yield self.env.timeout(assigned_sawmill.breakdown_end - self.env.now)
                    effective_sawmill = assigned_sawmill  # Reassign to original sawmill after waiting
                else:
                    assigned_sawmill.truck_diverted_from_sawmill += 1

          # Calculate and wait for travel time to the effective sawmill
          travel_time_to_sawmill = self.get_travel_time(effective_sawmill.sawmill_id,logging_site.site_id)
          # if logging_site.site_id == 'LS2':
          #   print(f"{self.env.now:.2f}: TP, {truck_itr.truck_id} completed LP, it will take {travel_time_to_sawmill:.2f} to go the the SM")
          yield self.env.timeout(travel_time_to_sawmill)

          # Process at the effective sawmill
          if not effective_sawmill.is_sawmill_open():
              if (self.env.now % 1440) <= effective_sawmill.sawmill_opening_time:
                  yield self.env.timeout(effective_sawmill.sawmill_opening_time - (self.env.now % 1440))
              elif (self.env.now % 1440) > effective_sawmill.sawmill_closing_time:
                  yield self.env.timeout(1440 - (self.env.now % 1440) + effective_sawmill.sawmill_opening_time)
              elif self.env.now > duration:
                  return

          yield self.env.process(self.sawmill_process(truck_itr, logging_site, effective_sawmill, duration))
          travel_time_to_logging_site = self.get_travel_time(effective_sawmill.sawmill_id,logging_site.site_id)

          yield self.env.timeout(travel_time_to_logging_site)

          # print(f"{self.env.now:.2f}: {truck_itr.truck_id} starts another processing from {logging_site.site_id}")
          yield self.env.process(self.truck_process(truck_itr, logging_site, duration))

    def logging_process(self, truck_itr, logging_site, duration):
      logging_site_start_time = self.env.now

      # if logging_site.site_id == 'LS2':
      #         print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} came to the logging site and waiting for the crane ")

      # Check if logging site has enough wood capacity
      if logging_site.log_cap_limit.level < truck_itr.truck_capacity:
          print(f"{self.env.now:.2f}: Not enough wood at logging site {logging_site.site_id}.")
          return

      # Calculate time until the end of the day (closing time)
      time_until_closing = logging_site.closing_time - (self.env.now % 1440)



      with logging_site.cranes.request() as crane_request:
          yield crane_request

          if not logging_site.is_site_open():
              # if logging_site.site_id == 'LS2':
              #   print(f"{self.env.now:.2f}: {truck_itr.truck_id} got the crane access but Logging site {logging_site.site_id} is closed. Waiting for opening time.")
              yield self.env.timeout(1440 - (self.env.now % 1440) + logging_site.opening_time)
              logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

          # If the truck arrives at the LS after the closing time in the previous day, then the logging start time needs to change
          if logging_site_start_time % 1440  > logging_site.closing_time:
              logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time

          if logging_site_start_time//1440 < self.env.now//1440:
              logging_site_start_time = ((self.env.now+1) // 1440) * 1440 + logging_site.opening_time



          # Print the number of trucks waiting in the queue
          queue_length = len(logging_site.cranes.queue)
          logging_site.queue_lengths.append(queue_length)
          crane_start_time = self.env.now

          # Calculate and store the waiting time for the truck
          site_waiting_period_end = self.env.now
          waiting_time = site_waiting_period_end - logging_site_start_time
          logging_site.site_wait_time.append(waiting_time)

          # if logging_site.site_id == 'LS2':
          #     print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} got the crane access and {queue_length} trucks are in the queue")

          # Adjust the start time if the crane is accessed the next day
          if self.env.now % 1440 < logging_site_start_time % 1440:
              logging_site_start_time = ((logging_site_start_time // 1440) + 1) * 1440 + logging_site.opening_time

          mean_loading_time = logging_site.avg_loading_time
          loading_time = np.random.uniform(low=mean_loading_time-(mean_loading_time/2), high=mean_loading_time+(mean_loading_time/2))
          # loading_time = mean_loading_time



          logging_site.loaded_truck_count += 1

          # Decrease wood capacity
          yield logging_site.log_cap_limit.get(truck_itr.truck_capacity)

          loading_processing_start = self.env.now

          if logging_site.logging_processing_end // 1440 < self.env.now  // 1440 : #or logging_site.logging_processing_end % 1440 > logging_site.closing_time
              logging_site.logging_processing_end = (self.env.now // 1440) * 1440 + logging_site.opening_time

          logging_site.loader_idle_time.append(loading_processing_start - logging_site.logging_processing_end)

          logging_site.total_loading_time.append(loading_time)
          yield self.env.timeout(loading_time)
          logging_site.logging_processing_end = self.env.now

          # Finish loading
          logging_site.amount_loaded += truck_itr.truck_capacity

          logging_site.truck_turn_time_in_logging_site.append(logging_site.logging_processing_end - logging_site_start_time)
          # if logging_site.site_id == 'LS2':
          #     print(f"{self.env.now:.2f}: LS, {truck_itr.truck_id} finished loading")



    def sawmill_process(self, truck_itr, logging_site,assigned_sawmill,duration):
      sawmill_start_time = self.env.now
      sawmill = assigned_sawmill


      truck_itr.truck_travels_in_sawmill += 1
      sawmill.truck_arrived += 1

    #   if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
    #       print(f"{self.env.now:.2f}: SM, Truck {truck_itr.truck_id} just arrived at the sawmill, On basis on arrival truck position: {sawmill.truck_arrived}")


      # if sawmill.truck_arrived == 1:
      #   print(f" starting breakdown time for {sawmill.sawmill_id} is {sawmill.breakdown_start} to {sawmill.breakdown_end}")

      # Check if logging site has enough wood capacity
      if sawmill.filled_amount.level + truck_itr.truck_capacity > sawmill.filled_amount.capacity:
          #print(f"{self.env.now:.2f}: Not enough space in sawmill {sawmill.sawmill_id}. Truck {truck_itr.truck_id} cannot unload.")
          return
      if ((self.env.now % 1440) < sawmill.sawmill_opening_time):
            yield self.env.timeout(sawmill.sawmill_opening_time - (self.env.now % 1440))
            sawmill_start_time = self.env.now


      with sawmill.scale_in.request() as scale_in_request:
            yield scale_in_request

            queue_length = len(sawmill.scale_in.queue)
            sawmill.sawmill_queue_lengths.append(queue_length)

            wait_time_scale_in = self.env.now - sawmill_start_time
            
            
            sawmill.scale_in_wait_times.append(wait_time_scale_in)

            # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
            #   print(f"{self.env.now:.2f}: SM, scale in for truck {truck_itr.truck_id} and in the scale in queue we have {queue_length} trucks")


            yield self.env.timeout( sawmill.scale_in_time)
            # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
            #   print(f"{self.env.now:.2f}: scale in completed for truck {truck_itr.truck_id}")

      scale_in_end_time = self.env.now
      yield self.env.timeout(sawmill.scale_in_to_unload_time)
      # yield self.env.timeout(sawmill.scale_in_to_unload_time)
      
      sawmill.scale_in_to_crane_times.append(self.env.now -scale_in_end_time)


      # Crane process for unloading
      crane_wait_start_time = self.env.now
      with assigned_sawmill.truck_waiting_area.request() as waiting_request:
          yield waiting_request


      # if (sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end):
      #   if(sawmill.crane1_operational == False and sawmill.crane2_operational == False):
      #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)





      with sawmill.cranes_in_sawmill.request() as crane_request:
            yield crane_request
            crane_id = sawmill.assign_crane()  # Attempt to assign a crane
            queue_length_crane = len(sawmill.cranes_in_sawmill.queue)
            #wait_time_crane = self.env.now - crane_wait_start_time

            wait_time_crane = self.env.now - scale_in_end_time
            sawmill.truck_wait_time_in_crane.append(wait_time_crane)
            # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
            #     print(f"{self.env.now:.2f}:  {truck_itr.truck_id} got the crane access after {(self.env.now-scale_in_end_time):.2f} time and got the crane {crane_id+1} access and {queue_length_crane} trucks are in the crane queue")


            #This is for breakdown. If there is no breakdown it will be remain commented

            # if sawmill.breakdown_end < self.env.now:
            #   sawmill.breakdown_number += 1
            #   sawmill.missed_breakdown += 1
            #   # sawmill.breakdown_countdown = 0
            #   # sawmill.breakdown_start = self.env.now + np.random.exponential(scale=self.mtbf)
            #   # sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
            #   sawmill.breakdown_start = sawmill.breakdown_start + 1440
            #   sawmill.breakdown_end = sawmill.breakdown_end + 1440
            #   # if sawmill.sawmill_id == 'SM1':
            #   #   print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: previous breakdown happened when the sawmill was close")
            #   # print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: Next breakdown will be happended from {sawmill.breakdown_start:.2f} to {sawmill.breakdown_end:.2f}")




            # # If the previous crane unloading happend the previous day then it will be assigned as current time
            if crane_id == 0:
                # Check if the unloading happened on the previous day or the time exceeds the closing time
                if sawmill.crane1_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane1_unloading_end % 1440 > sawmill.sawmill_closing_time:
                    # Adjust the unloading time to the current day's opening time
                    pre_crane1_unloading_end = sawmill.crane1_unloading_end
                    sawmill.crane1_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time
                    # print(f"{self.env.now:.2f}: For truck {truck_itr.truck_id}, Crane 1 unloading time adjusted from {pre_crane1_unloading_end:.2f} to {sawmill.crane1_unloading_end:.2f}")

            elif crane_id == 1:
                # Same check for crane 2
                if sawmill.crane2_unloading_end // 1440 < self.env.now // 1440 or sawmill.crane2_unloading_end % 1440 > sawmill.sawmill_closing_time:
                    pre_crane2_unloading_end = sawmill.crane2_unloading_end
                    sawmill.crane2_unloading_end = (self.env.now // 1440) * 1440 + sawmill.sawmill_opening_time
                    # print(f"{self.env.now:.2f}: For truck {truck_itr.truck_id}, Crane 2 unloading time adjusted from {pre_crane2_unloading_end:.2f} to {sawmill.crane2_unloading_end:.2f}")


            # If the breakdown happend when unloading, then the truck cannot unload the timbers
            # thats why we will check if the breakdown will happend on unloading or not. If we find the breakdown will
            # happend during the unloading then we will stop unloading for that truck

            unload_time_mean = sawmill.unload_time_mean
            unload_time = np.random.uniform(low=unload_time_mean-(unload_time_mean/2), high=unload_time_mean+(unload_time_mean/2))


            # for breakdown
            # if((sawmill.breakdown_start<=self.env.now<=sawmill.breakdown_end)):
            #   if (crane_id == 0 and sawmill.breakdown_countdown == 0):
            #     sawmill.breakdown_countdown = 1
            #     # if sawmill.sawmill_id == 'SM1':
            #     #   print(f"{self.env.now:.2f}: Breakdown happeneded")
            #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)

            # if sawmill.breakdown_start <= (self.env.now+unload_time) <= sawmill.breakdown_end:
            #   if (crane_id == 0 and sawmill.breakdown_countdown == 0):
            #     sawmill.breakdown_countdown =  1
            #     # if sawmill.sawmill_id == 'SM1':
            #     #   print(f"{self.env.now:.2f}: Breakdown happeneded")
            #     yield self.env.timeout(sawmill.breakdown_end - self.env.now)



            # if sawmill.breakdown_countdown == 1:
            #   sawmill.breakdown_number += 1
            #   sawmill.breakdown_countdown = 0
            #   # As it checked the current breakdown and processed the action, now new breakdown schedule is assigned
            #   # sawmill.breakdown_start = sawmill.breakdown_end + np.random.exponential(scale=self.mtbf)
            #   # sawmill.breakdown_end = sawmill.breakdown_start + np.random.exponential(scale=self.mttr)
            #   sawmill.breakdown_start = sawmill.breakdown_start + 1440
            #   sawmill.breakdown_end = sawmill.breakdown_end + 1440

            #   # print(f"{self.env.now:.2f}: {sawmill.sawmill_id}: Next breakdown will be happended from {sawmill.breakdown_start:.2f} to {sawmill.breakdown_end:.2f}")

            # crane_unloading_start = self.env.now
            if(crane_id == 0):
              crane1_unloading_start = self.env.now
            else:
              crane2_unloading_start = self.env.now

            if ((self.env.now % 1440) < sawmill.sawmill_closing_time):

              if(crane_id == 0): #Crane 1's data for processing is in here
                crane1_idle = crane1_unloading_start - sawmill.crane1_unloading_end
                sawmill.crane1_idle_time.append( crane1_idle )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                yield self.env.timeout(unload_time)
                sawmill.crane1_unloading_time.append(unload_time)
                sawmill.crane1_processed_truck += 1
                # if(sawmill.sawmill_id == 'SM1' and crane1_idle > 100):
                #   print(f"{self.env.now:.2f}: Crane 1 idle time greater than 100 for {truck_itr.truck_id}, unloading start time was {crane1_unloading_start:.2f} and previous unloading end was {sawmill.crane1_unloading_end:.2f} and idle time is {crane1_idle:.2f}")
                #   print(f"truck in the queue: {queue_length}")

                sawmill.crane1_unloading_end = self.env.now
                # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
                #     print(f"{self.env.now:.2f}: Crane 1 unloading finished for {truck_itr.truck_id}")


              else: #Crane 2's data for processing is in here
                crane2_idle = crane2_unloading_start - sawmill.crane2_unloading_end
                sawmill.crane2_idle_time.append(crane2_idle )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
                yield self.env.timeout(unload_time)
                #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
                sawmill.crane2_unloading_time.append(unload_time)
                sawmill.crane2_processed_truck += 1
                # if(sawmill.sawmill_id == 'SM1' and crane2_idle > 100):
                #   print(f"{self.env.now:.2f}: Crane 2 idle time greater than 100 for {truck_itr.truck_id}, unloading start time was {crane2_unloading_start:.2f} and previous unloading end was {sawmill.crane2_unloading_end:.2f} and idle time is {crane2_idle:.2f}")
                #   print(f"truck in the queue: {queue_length}")

                sawmill.crane2_unloading_end = self.env.now
                # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
                #     print(f"{self.env.now:.2f}: Crane 2 unloading finished for {truck_itr.truck_id}")

            else: #Overtime data will be in here
              if(crane_id == 0): #Crane 1's data for processing is in here
                #Crane's idle time will not be counted as it is overtime
                # sawmill.crane1_idle_time.append(crane_unloading_start - sawmill.crane1_unloading_end )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
                yield self.env.timeout(unload_time)
                #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
                sawmill.crane1_over_time.append(unload_time)

                sawmill.crane1_processed_truck_on_overtime += 1

                sawmill.crane1_unloading_end = self.env.now
                # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
                #     print(f"{self.env.now:.2f}: Crane 1 overtime unloading finished for {truck_itr.truck_id}")

              else: #Crane 1's data for processing is in here
                #Crane's idle time will not be counted as it is overtime
                # sawmill.crane1_idle_time.append(crane_unloading_start - sawmill.crane1_unloading_end )
                yield sawmill.filled_amount.put(truck_itr.truck_capacity)
                #print(f"{self.env.now}: {truck_itr.truck_id} start unloading at {self.env.now}")
                yield self.env.timeout(unload_time)
                #print(f"{self.env.now}: {truck_itr.truck_id} unloaded for {unload_time} ")
                sawmill.crane2_over_time.append(unload_time)

                sawmill.crane2_processed_truck_on_overtime += 1

                sawmill.crane2_unloading_end = self.env.now
                # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
                #     print(f"{self.env.now:.2f}: Crane 2 overtime unloading finished for {truck_itr.truck_id}")


            # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
            #   print(f"{self.env.now:.2f}: Truck {truck_itr.truck_id} has unloaded at sawmill {sawmill.sawmill_id}.")
            sawmill.Number_of_Trucks_Unloaded += 1
            sawmill.Total_Amount_Unloaded_in_Tons += truck_itr.truck_capacity

            assigned_sawmill.release_crane(crane_id)



      # Fixed unloading to scale out traveling time
      crane_end_time = self.env.now
      yield self.env.timeout(sawmill.unload_to_scale_out_time)
      # yield self.env.timeout(sawmill.unload_to_scale_out_time)
      sawmill.crane_to_scale_out_times.append(self.env.now - crane_end_time)

      # Scale out process
      scale_out_waiting_start = self.env.now
      with sawmill.scale_out.request() as scale_out_request:
            yield scale_out_request

            wait_time_scale_out = self.env.now -scale_out_waiting_start
            sawmill.scale_out_wait_times.append(wait_time_scale_out)
            # if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
            #   print(f"{self.env.now:.2f} : Truck:{truck_itr.truck_id} got out after scale out")
            # Fixed time at scale out
            # yield self.env.timeout(np.random.exponential(scale=sawmill.scale_out_time))
            yield self.env.timeout(sawmill.scale_out_time)
            sawmill.truck_departed += 1

      turn_time = self.env.now - sawmill_start_time
      sawmill.truck_turn_time_in_sawmill.append(turn_time)
    #   if(sawmill.sawmill_id == 'SM1' and 14*1440<= self.env.now < 15*1440):
    #     print(f"{self.env.now:.2f} : SM, Crane : {crane_id} Truck:{truck_itr.truck_id} Truck position: {sawmill.Number_of_Trucks_Unloaded} Queue length: {queue_length} Sc.Wait: {wait_time_scale_in:.2f} Crane wait : {wait_time_crane:.2f} Turn time: {turn_time:.2f}")


    def start_simulation(self, duration):
        self.env.process(self.truck_generate(duration))
        self.env.run(until=duration)

        for truck in self.trucks:
            gb.trucks_no_of_travel_in_sawmill1.append(truck.truck_travels_in_sawmill)

        # Update gb.trucks_no_of_travel_in_sawmill2 using add_lists_with_padding
        if len(gb.trucks_no_of_travel_in_sawmill2) == 0:
            gb.trucks_no_of_travel_in_sawmill2 = gb.trucks_no_of_travel_in_sawmill1[:]
            gb.trucks_no_of_travel_count = [1] * len(gb.trucks_no_of_travel_in_sawmill1)  # Initialize the count list
        else:
            gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_count = add_lists_with_padding(
                gb.trucks_no_of_travel_in_sawmill2, gb.trucks_no_of_travel_in_sawmill1,
                gb.trucks_no_of_travel_count, [1] * len(gb.trucks_no_of_travel_in_sawmill1)
            )

        gb.trucks_no_of_travel_in_sawmill1 = []  # Reset the temporary list







# print(np.random.uniform(low=8,high=22))

##Simulation

###Final result


import multiprocessing as mp
import numpy as np
import matplotlib.pyplot as plt

def add_lists_with_padding(list1, list2, counts1, counts2):
    max_length = max(len(list1), len(list2))

    # Extend the shorter list and counts with zeros
    if len(list1) < max_length:
        list1.extend([0] * (max_length - len(list1)))
        counts1.extend([0] * (max_length - len(counts1)))
    if len(list2) < max_length:
        list2.extend([0] * (max_length - len(list2)))
        counts2.extend([0] * (max_length - len(counts2)))

    summed_list = []
    counts = []

    for i in range(max_length):
        summed_value = list1[i] + list2[i]
        count = counts1[i] + counts2[i]  # Add the counts
        summed_list.append(summed_value)
        counts.append(count)

    return summed_list, counts

def average_elements_with_count(summed_list, counts):
    averages = []
    for summed_value, count in zip(summed_list, counts):
        if count != 0:
            averages.append(summed_value / count)
        else:
            averages.append(0)  # If no counts, the average is set to 0
    return averages

number_of_replication = 2
total_days = 10


def run_replication(replication_id, total_days):
    env = simpy.Environment()
    print(f"Replication {replication_id} started.")

    mtbf = 720  # Mean time between failures in minutes (e.g., once every 24 hours)
    mttr = 60   # Mean time to repair in minutes (e.g., 1 hour)

    # Assuming Model and data objects are predefined
    model = Model(env, logging_site_data, sawmill_data, company_data, truck_data, travel_times_data, mtbf, mttr)
    full_days = total_days - 1
    model.start_simulation(duration=(full_days * 1440 + 765))

    result = {
        "loaded_truck_count": {site_id: site.loaded_truck_count for site_id, site in model.logging_sites.items()},
        "amount_loaded": {site_id: site.amount_loaded for site_id, site in model.logging_sites.items()},
        "queue_lengths": {site_id: site.queue_lengths for site_id, site in model.logging_sites.items()},
        "site_wait_time": {site_id: site.site_wait_time for site_id, site in model.logging_sites.items()},
        "loader_idle_time": {site_id: site.loader_idle_time for site_id, site in model.logging_sites.items()},
        "total_loading_time": {site_id: site.total_loading_time for site_id, site in model.logging_sites.items()},
        "truck_turn_time_in_logging_site": {site_id: site.truck_turn_time_in_logging_site for site_id, site in model.logging_sites.items()},
        "Number_of_Trucks_Unloaded": {sawmill_id: sawmill.Number_of_Trucks_Unloaded for sawmill_id, sawmill in model.sawmills.items()},
        "sawmill_queue_lengths": {sawmill_id: sawmill.sawmill_queue_lengths for sawmill_id, sawmill in model.sawmills.items()},
        "scale_in_wait_times": {sawmill_id: sawmill.scale_in_wait_times for sawmill_id, sawmill in model.sawmills.items()},
        "truck_wait_time_in_crane": {sawmill_id: sawmill.truck_wait_time_in_crane for sawmill_id, sawmill in model.sawmills.items()},
        "truck_departed": {sawmill_id: sawmill.truck_departed for sawmill_id, sawmill in model.sawmills.items()},
        "crane1_idle_time": {sawmill_id: sawmill.crane1_idle_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane1_unloading_time": {sawmill_id: sawmill.crane1_unloading_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane1_over_time": {sawmill_id: sawmill.crane1_over_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane1_processed_truck": {sawmill_id: sawmill.crane1_processed_truck for sawmill_id, sawmill in model.sawmills.items()},
        "crane1_processed_truck_on_overtime": {sawmill_id: sawmill.crane1_processed_truck_on_overtime for sawmill_id, sawmill in model.sawmills.items()},
        "crane2_idle_time": {sawmill_id: sawmill.crane2_idle_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane2_unloading_time": {sawmill_id: sawmill.crane2_unloading_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane2_over_time": {sawmill_id: sawmill.crane2_over_time for sawmill_id, sawmill in model.sawmills.items()},
        "crane2_processed_truck": {sawmill_id: sawmill.crane2_processed_truck for sawmill_id, sawmill in model.sawmills.items()},
        "crane2_processed_truck_on_overtime": {sawmill_id: sawmill.crane2_processed_truck_on_overtime for sawmill_id, sawmill in model.sawmills.items()},
        "truck_turn_time_in_sawmill": {sawmill_id: sawmill.truck_turn_time_in_sawmill for sawmill_id, sawmill in model.sawmills.items()},
        "truck_diverted_from_sawmill": {sawmill_id: sawmill.truck_diverted_from_sawmill for sawmill_id, sawmill in model.sawmills.items()},
        "breakdown_number": {sawmill_id: sawmill.breakdown_number for sawmill_id, sawmill in model.sawmills.items()},
        "missed_breakdown_number": {sawmill_id: sawmill.missed_breakdown for sawmill_id, sawmill in model.sawmills.items()},
        "truck_arrived_per_day": {sawmill_id: sawmill.truck_number_per_day_in_sawmill for sawmill_id, sawmill in model.sawmills.items()}

    }
    return result


pool = mp.Pool(mp.cpu_count())
replication_results = pool.starmap(run_replication, [(i, total_days) for i in range(number_of_replication)])

# Initialize structures for aggregation
aggregated_result = {}
count_result = {}

for i, replication_result in enumerate(replication_results):
    if i == 0:
        aggregated_result = replication_result
        # Initialize count_result to store counts for averaging later
        count_result = {
            "queue_lengths": {site_id: [1] * len(replication_result["queue_lengths"][site_id]) for site_id in replication_result["queue_lengths"].keys()},
            "site_wait_time": {site_id: [1] * len(replication_result["site_wait_time"][site_id]) for site_id in replication_result["site_wait_time"].keys()},
            "loader_idle_time": {site_id: [1] * len(replication_result["loader_idle_time"][site_id]) for site_id in replication_result["loader_idle_time"].keys()},
            "total_loading_time": {site_id: [1] * len(replication_result["total_loading_time"][site_id]) for site_id in replication_result["total_loading_time"].keys()},
            "truck_turn_time_in_logging_site": {site_id: [1] * len(replication_result["truck_turn_time_in_logging_site"][site_id]) for site_id in replication_result["truck_turn_time_in_logging_site"].keys()},
            "sawmill_queue_lengths": {sawmill_id: [1] * len(replication_result["sawmill_queue_lengths"][sawmill_id]) for sawmill_id in replication_result["sawmill_queue_lengths"].keys()},
            "scale_in_wait_times": {sawmill_id: [1] * len(replication_result["scale_in_wait_times"][sawmill_id]) for sawmill_id in replication_result["scale_in_wait_times"].keys()},
            "truck_wait_time_in_crane": {sawmill_id: [1] * len(replication_result["truck_wait_time_in_crane"][sawmill_id]) for sawmill_id in replication_result["truck_wait_time_in_crane"].keys()},
            "crane1_idle_time": {sawmill_id: [1] * len(replication_result["crane1_idle_time"][sawmill_id]) for sawmill_id in replication_result["crane1_idle_time"].keys()},
            "crane1_unloading_time": {sawmill_id: [1] * len(replication_result["crane1_unloading_time"][sawmill_id]) for sawmill_id in replication_result["crane1_unloading_time"].keys()},
            "crane1_over_time": {sawmill_id: [1] * len(replication_result["crane1_over_time"][sawmill_id]) for sawmill_id in replication_result["crane1_over_time"].keys()},
            "crane2_idle_time": {sawmill_id: [1] * len(replication_result["crane2_idle_time"][sawmill_id]) for sawmill_id in replication_result["crane2_idle_time"].keys()},
            "crane2_unloading_time": {sawmill_id: [1] * len(replication_result["crane2_unloading_time"][sawmill_id]) for sawmill_id in replication_result["crane2_unloading_time"].keys()},
            "crane2_over_time": {sawmill_id: [1] * len(replication_result["crane2_over_time"][sawmill_id]) for sawmill_id in replication_result["crane2_over_time"].keys()},
            "truck_turn_time_in_sawmill": {sawmill_id: [1] * len(replication_result["truck_turn_time_in_sawmill"][sawmill_id]) for sawmill_id in replication_result["truck_turn_time_in_sawmill"].keys()},
        }
    else:
        for site_id in replication_result["loaded_truck_count"].keys():
            aggregated_result["loaded_truck_count"][site_id] += replication_result["loaded_truck_count"][site_id]
            aggregated_result["amount_loaded"][site_id] += replication_result["amount_loaded"][site_id]
            aggregated_result["queue_lengths"][site_id], count_result["queue_lengths"][site_id] = add_lists_with_padding(
                aggregated_result["queue_lengths"][site_id], replication_result["queue_lengths"][site_id],
                count_result["queue_lengths"][site_id], [1] * len(replication_result["queue_lengths"][site_id]))
            aggregated_result["site_wait_time"][site_id], count_result["site_wait_time"][site_id] = add_lists_with_padding(
                aggregated_result["site_wait_time"][site_id], replication_result["site_wait_time"][site_id],
                count_result["site_wait_time"][site_id], [1] * len(replication_result["site_wait_time"][site_id]))
            aggregated_result["loader_idle_time"][site_id], count_result["loader_idle_time"][site_id] = add_lists_with_padding(
                aggregated_result["loader_idle_time"][site_id], replication_result["loader_idle_time"][site_id],
                count_result["loader_idle_time"][site_id], [1] * len(replication_result["loader_idle_time"][site_id]))
            aggregated_result["total_loading_time"][site_id], count_result["total_loading_time"][site_id] = add_lists_with_padding(
                aggregated_result["total_loading_time"][site_id], replication_result["total_loading_time"][site_id],
                count_result["total_loading_time"][site_id], [1] * len(replication_result["total_loading_time"][site_id]))
            aggregated_result["truck_turn_time_in_logging_site"][site_id], count_result["truck_turn_time_in_logging_site"][site_id] = add_lists_with_padding(
                aggregated_result["truck_turn_time_in_logging_site"][site_id], replication_result["truck_turn_time_in_logging_site"][site_id],
                count_result["truck_turn_time_in_logging_site"][site_id], [1] * len(replication_result["truck_turn_time_in_logging_site"][site_id]))

        for sawmill_id in replication_result["Number_of_Trucks_Unloaded"].keys():
            aggregated_result["Number_of_Trucks_Unloaded"][sawmill_id] += replication_result["Number_of_Trucks_Unloaded"][sawmill_id]
            aggregated_result["sawmill_queue_lengths"][sawmill_id], count_result["sawmill_queue_lengths"][sawmill_id] = add_lists_with_padding(
                aggregated_result["sawmill_queue_lengths"][sawmill_id], replication_result["sawmill_queue_lengths"][sawmill_id],
                count_result["sawmill_queue_lengths"][sawmill_id], [1] * len(replication_result["sawmill_queue_lengths"][sawmill_id]))
            aggregated_result["scale_in_wait_times"][sawmill_id], count_result["scale_in_wait_times"][sawmill_id] = add_lists_with_padding(
                aggregated_result["scale_in_wait_times"][sawmill_id], replication_result["scale_in_wait_times"][sawmill_id],
                count_result["scale_in_wait_times"][sawmill_id], [1] * len(replication_result["scale_in_wait_times"][sawmill_id]))
            aggregated_result["truck_wait_time_in_crane"][sawmill_id], count_result["truck_wait_time_in_crane"][sawmill_id] = add_lists_with_padding(
                aggregated_result["truck_wait_time_in_crane"][sawmill_id], replication_result["truck_wait_time_in_crane"][sawmill_id],
                count_result["truck_wait_time_in_crane"][sawmill_id], [1] * len(replication_result["truck_wait_time_in_crane"][sawmill_id]))
            aggregated_result["truck_departed"][sawmill_id] += replication_result["truck_departed"][sawmill_id]
            aggregated_result["crane1_idle_time"][sawmill_id], count_result["crane1_idle_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane1_idle_time"][sawmill_id], replication_result["crane1_idle_time"][sawmill_id],
                count_result["crane1_idle_time"][sawmill_id], [1] * len(replication_result["crane1_idle_time"][sawmill_id]))
            aggregated_result["crane1_unloading_time"][sawmill_id], count_result["crane1_unloading_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane1_unloading_time"][sawmill_id], replication_result["crane1_unloading_time"][sawmill_id],
                count_result["crane1_unloading_time"][sawmill_id], [1] * len(replication_result["crane1_unloading_time"][sawmill_id]))
            aggregated_result["crane1_over_time"][sawmill_id], count_result["crane1_over_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane1_over_time"][sawmill_id], replication_result["crane1_over_time"][sawmill_id],
                count_result["crane1_over_time"][sawmill_id], [1] * len(replication_result["crane1_over_time"][sawmill_id]))
            aggregated_result["crane1_processed_truck"][sawmill_id] += replication_result["crane1_processed_truck"][sawmill_id]
            aggregated_result["crane1_processed_truck_on_overtime"][sawmill_id] += replication_result["crane1_processed_truck_on_overtime"][sawmill_id]
            aggregated_result["crane2_idle_time"][sawmill_id], count_result["crane2_idle_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane2_idle_time"][sawmill_id], replication_result["crane2_idle_time"][sawmill_id],
                count_result["crane2_idle_time"][sawmill_id], [1] * len(replication_result["crane2_idle_time"][sawmill_id]))
            aggregated_result["crane2_unloading_time"][sawmill_id], count_result["crane2_unloading_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane2_unloading_time"][sawmill_id], replication_result["crane2_unloading_time"][sawmill_id],
                count_result["crane2_unloading_time"][sawmill_id], [1] * len(replication_result["crane2_unloading_time"][sawmill_id]))
            aggregated_result["crane2_over_time"][sawmill_id], count_result["crane2_over_time"][sawmill_id] = add_lists_with_padding(
                aggregated_result["crane2_over_time"][sawmill_id], replication_result["crane2_over_time"][sawmill_id],
                count_result["crane2_over_time"][sawmill_id], [1] * len(replication_result["crane2_over_time"][sawmill_id]))
            aggregated_result["crane2_processed_truck"][sawmill_id] += replication_result["crane2_processed_truck"][sawmill_id]
            aggregated_result["crane2_processed_truck_on_overtime"][sawmill_id] += replication_result["crane2_processed_truck_on_overtime"][sawmill_id]
            aggregated_result["truck_turn_time_in_sawmill"][sawmill_id], count_result["truck_turn_time_in_sawmill"][sawmill_id] = add_lists_with_padding(
                aggregated_result["truck_turn_time_in_sawmill"][sawmill_id], replication_result["truck_turn_time_in_sawmill"][sawmill_id],
                count_result["truck_turn_time_in_sawmill"][sawmill_id], [1] * len(replication_result["truck_turn_time_in_sawmill"][sawmill_id]))
            aggregated_result["truck_diverted_from_sawmill"][sawmill_id] += replication_result["truck_diverted_from_sawmill"][sawmill_id]
            aggregated_result["breakdown_number"][sawmill_id] += replication_result["breakdown_number"][sawmill_id]
            aggregated_result["missed_breakdown_number"][sawmill_id] += replication_result["missed_breakdown_number"][sawmill_id]

pool.close()
pool.join()

average_aggregated_result = {
    "loaded_truck_count": {site_id: count / number_of_replication for site_id, count in aggregated_result["loaded_truck_count"].items()},
    "amount_loaded": {site_id: count / number_of_replication for site_id, count in aggregated_result["amount_loaded"].items()},
    "queue_lengths": {site_id: average_elements_with_count(aggregated_result["queue_lengths"][site_id], count_result["queue_lengths"][site_id]) for site_id in aggregated_result["queue_lengths"].keys()},
    "site_wait_time": {site_id: average_elements_with_count(aggregated_result["site_wait_time"][site_id], count_result["site_wait_time"][site_id]) for site_id in aggregated_result["site_wait_time"].keys()},
    "loader_idle_time": {site_id: average_elements_with_count(aggregated_result["loader_idle_time"][site_id], count_result["loader_idle_time"][site_id]) for site_id in aggregated_result["loader_idle_time"].keys()},
    "total_loading_time": {site_id: average_elements_with_count(aggregated_result["total_loading_time"][site_id], count_result["total_loading_time"][site_id]) for site_id in aggregated_result["total_loading_time"].keys()},
    "truck_turn_time_in_logging_site": {site_id: average_elements_with_count(aggregated_result["truck_turn_time_in_logging_site"][site_id], count_result["truck_turn_time_in_logging_site"][site_id]) for site_id in aggregated_result["truck_turn_time_in_logging_site"].keys()},
    "Number_of_Trucks_Unloaded": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["Number_of_Trucks_Unloaded"].items()},
    "sawmill_queue_lengths": {sawmill_id: average_elements_with_count(aggregated_result["sawmill_queue_lengths"][sawmill_id], count_result["sawmill_queue_lengths"][sawmill_id]) for sawmill_id in aggregated_result["sawmill_queue_lengths"].keys()},
    "scale_in_wait_times": {sawmill_id: average_elements_with_count(aggregated_result["scale_in_wait_times"][sawmill_id], count_result["scale_in_wait_times"][sawmill_id]) for sawmill_id in aggregated_result["scale_in_wait_times"].keys()},
    "truck_wait_time_in_crane": {sawmill_id: average_elements_with_count(aggregated_result["truck_wait_time_in_crane"][sawmill_id], count_result["truck_wait_time_in_crane"][sawmill_id]) for sawmill_id in aggregated_result["truck_wait_time_in_crane"].keys()},
    "truck_departed": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["truck_departed"].items()},
    "crane1_idle_time": {sawmill_id: average_elements_with_count(aggregated_result["crane1_idle_time"][sawmill_id], count_result["crane1_idle_time"][sawmill_id]) for sawmill_id in aggregated_result["crane1_idle_time"].keys()},
    "crane1_unloading_time": {sawmill_id: average_elements_with_count(aggregated_result["crane1_unloading_time"][sawmill_id], count_result["crane1_unloading_time"][sawmill_id]) for sawmill_id in aggregated_result["crane1_unloading_time"].keys()},
    "crane1_over_time": {sawmill_id: average_elements_with_count(aggregated_result["crane1_over_time"][sawmill_id], count_result["crane1_over_time"][sawmill_id]) for sawmill_id in aggregated_result["crane1_over_time"].keys()},
    "crane1_processed_truck": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["crane1_processed_truck"].items()},
    "crane1_processed_truck_on_overtime": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["crane1_processed_truck_on_overtime"].items()},
    "crane2_idle_time": {sawmill_id: average_elements_with_count(aggregated_result["crane2_idle_time"][sawmill_id], count_result["crane2_idle_time"][sawmill_id]) for sawmill_id in aggregated_result["crane2_idle_time"].keys()},
    "crane2_unloading_time": {sawmill_id: average_elements_with_count(aggregated_result["crane2_unloading_time"][sawmill_id], count_result["crane2_unloading_time"][sawmill_id]) for sawmill_id in aggregated_result["crane2_unloading_time"].keys()},
    "crane2_over_time": {sawmill_id: average_elements_with_count(aggregated_result["crane2_over_time"][sawmill_id], count_result["crane2_over_time"][sawmill_id]) for sawmill_id in aggregated_result["crane2_over_time"].keys()},
    "crane2_processed_truck": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["crane2_processed_truck"].items()},
    "crane2_processed_truck_on_overtime": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["crane2_processed_truck_on_overtime"].items()},
    "truck_turn_time_in_sawmill": {sawmill_id: average_elements_with_count(aggregated_result["truck_turn_time_in_sawmill"][sawmill_id], count_result["truck_turn_time_in_sawmill"][sawmill_id]) for sawmill_id in aggregated_result["truck_turn_time_in_sawmill"].keys()},
    "truck_diverted_from_sawmill": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["truck_diverted_from_sawmill"].items()},
    "breakdown_number": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["breakdown_number"].items()},
    "missed_breakdown_number": {sawmill_id: count / number_of_replication for sawmill_id, count in aggregated_result["missed_breakdown_number"].items()}
}

print("Average Aggregated Results:")
print("Logging Site Data:")
for site_id, count in average_aggregated_result["loaded_truck_count"].items():
    print("")
    print(f"Site {site_id}: {count:.2f} trucks loaded on average")
    print(f"Site {site_id}: {average_aggregated_result['amount_loaded'][site_id]:.2f} tons loaded")
    # print(f"Site {site_id}: average queue length {average_aggregated_result['queue_lengths'][site_id]} ")
    # print(f"Site {site_id}: average wait time {average_aggregated_result['site_wait_time'][site_id]} ")
    # print(f"Site {site_id}: loader idle time {average_aggregated_result['loader_idle_time'][site_id]} ")
    # print(f"Site {site_id}: total loading time {average_aggregated_result['total_loading_time'][site_id]}")
    # print(f"Site {site_id}: truck turn time in logging site {average_aggregated_result['truck_turn_time_in_logging_site'][site_id]} ")
    print(f"Loader utilization : {(1 - (np.sum(average_aggregated_result['loader_idle_time'][site_id])/(total_days * 600))):.2f}")
    print(" ")

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['queue_lengths'][site_id], marker='.')
    # plt.title(f'Queue length at Logging Site {site_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Queue length')
    # plt.grid(True)
    # plt.show()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['site_wait_time'][site_id], marker='.')
    # plt.title(f'Wait times for each truck at Logging Site {site_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Wait Time (minutes)')
    # plt.grid(True)
    # plt.show()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['total_loading_time'][site_id], marker='.')
    # plt.title(f'Loading time at Logging Site {site_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Loading Time (minutes)')
    # plt.grid(True)
    # plt.show()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['loader_idle_time'][site_id], marker='.')
    # plt.title(f'Loader idle time at Logging Site {site_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Idle Time (minutes)')
    # plt.grid(True)
    # plt.show()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['truck_turn_time_in_logging_site'][site_id], marker='.')
    # plt.title(f'Truck turn time in logging site {site_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Turn Time (minutes)')
    # plt.grid(True)
    # plt.show()

import os

# Specify the output directory for the HPC
output_dir = "/home/mahmed/code/figure/"  # Update this with the correct path on your HPC

# Create the directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print("\nSawmill Data:")
for sawmill_id, count in average_aggregated_result["Number_of_Trucks_Unloaded"].items():
    print(" ")
    print(f"Sawmill {sawmill_id}: {count:.2f} trucks unloaded on average")
    # print(f"Sawmill {sawmill_id}: average queue length {average_aggregated_result['sawmill_queue_lengths'][sawmill_id]} ")
    # print(f"Sawmill {sawmill_id}: scale in wait time {average_aggregated_result['scale_in_wait_times'][sawmill_id]} ")
    # print(f"Sawmill {sawmill_id}: truck wait time in crane {average_aggregated_result['truck_wait_time_in_crane'][sawmill_id]} ")

    print(f"Sawmill {sawmill_id}: truck average wait time in crane {np.mean(average_aggregated_result['truck_wait_time_in_crane'][sawmill_id]):.2f} ")

    print(f"Sawmill {sawmill_id}: trucks departed {average_aggregated_result['truck_departed'][sawmill_id]:.2f} ")
    print(f"Sawmill {sawmill_id}: breakdown number {average_aggregated_result['breakdown_number'][sawmill_id]:.2f} ")
    # print(f"Sawmill {sawmill_id}: truck turn time in sawmill {average_aggregated_result['truck_turn_time_in_sawmill'][sawmill_id]} ")
    print(f"Sawmill {sawmill_id}: trucks diverted from sawmill {average_aggregated_result['truck_diverted_from_sawmill'][sawmill_id]:.2f} ")


    print(" ")
    # print(f"Sawmill {sawmill_id}: crane1 idle time {average_aggregated_result['crane1_idle_time'][sawmill_id]} ")
    # print(f"Sawmill {sawmill_id}: crane1 unloading time {average_aggregated_result['crane1_unloading_time'][sawmill_id]} ")
    # print(f"Sawmill {sawmill_id}: crane1 over time {average_aggregated_result['crane1_over_time'][sawmill_id]} ")
    print(f"Sawmill {sawmill_id}: crane1 processed truck {average_aggregated_result['crane1_processed_truck'][sawmill_id]:.2f} ")
    print(f"Sawmill {sawmill_id}: crane1 processed truck on overtime {average_aggregated_result['crane1_processed_truck_on_overtime'][sawmill_id]:.2f} ")
    print(f"Crane 1 utilization : {1- (np.sum(average_aggregated_result['crane1_idle_time'][sawmill_id])/(total_days * 720)):.2f}")
    print(" ")
    # print(f"Sawmill {sawmill_id}:  crane2 idle time {average_aggregated_result['crane2_idle_time'][sawmill_id]}")
    # print(f"Sawmill {sawmill_id}: crane2 unloading time {average_aggregated_result['crane2_unloading_time'][sawmill_id]} ")
    # print(f"Sawmill {sawmill_id}: crane2 over time {average_aggregated_result['crane2_over_time'][sawmill_id]} ")
    print(f"Sawmill {sawmill_id}: crane2 processed truck {average_aggregated_result['crane2_processed_truck'][sawmill_id]:.2f} ")
    print(f"Sawmill {sawmill_id}: crane2 processed truck on overtime{average_aggregated_result['crane2_processed_truck_on_overtime'][sawmill_id]:.2f} ")
    print(f"Crane 2 utilization : {1- (np.sum(average_aggregated_result['crane2_idle_time'][sawmill_id])/(total_days * 720)):.2f}")
    print(" ")

    # # Save plots for each metric
    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['scale_in_wait_times'][sawmill_id], marker='.')
    # plt.title(f'Truck wait time before scale in at Sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Wait Time (minutes)')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_scale_in_wait_time.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['truck_wait_time_in_crane'][sawmill_id], marker='.')
    # plt.title(f'Truck wait time for crane at Sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Wait Time (minutes)')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_crane_wait_time.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['sawmill_queue_lengths'][sawmill_id], marker='.')
    # plt.title(f'Truck queue length for crane at Sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Queue Length')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_queue_length.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['crane1_idle_time'][sawmill_id], marker='.', color='g')
    # plt.title(f'Crane 1 idle time in sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Idle Time')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_crane1_idle_time.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['crane1_unloading_time'][sawmill_id], marker='.', color='r')
    # plt.title(f'Truck unloading time for crane 1 in sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Unloading Time')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_crane1_unloading_time.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['crane2_idle_time'][sawmill_id], marker='.', color='g')
    # plt.title(f'Crane 2 idle time in sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Idle Time')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_crane2_idle_time.png")
    # plt.close()

    # plt.figure(figsize=(10, 5))
    # plt.plot(average_aggregated_result['crane2_unloading_time'][sawmill_id], marker='.', color='r')
    # plt.title(f'Truck unloading time for crane 2 in sawmill {sawmill_id}')
    # plt.xlabel('Truck Index')
    # plt.ylabel('Unloading Time')
    # plt.grid(True)
    # plt.savefig(f"{output_dir}sawmill_{sawmill_id}_crane2_unloading_time.png")
    # plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(average_aggregated_result['truck_turn_time_in_sawmill'][sawmill_id], marker='.', color='r')
    plt.title(f'Truck turn time in sawmill {sawmill_id}')
    plt.xlabel('Truck Index')
    plt.ylabel('Truck Turn Time')
    plt.grid(True)
    plt.savefig(f"{output_dir}sawmill_{sawmill_id}_truck_turn_time.png")
    plt.close()

