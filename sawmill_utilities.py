# sawmill_utilities.py

def add_lists_with_padding(list1, list2, count1, count2):
    max_length = max(len(list1), len(list2))
    result = []
    updated_count = []

    for i in range(max_length):
        val1 = list1[i] if i < len(list1) else 0
        val2 = list2[i] if i < len(list2) else 0
        c1 = count1[i] if i < len(count1) else 0
        c2 = count2[i] if i < len(count2) else 0
        total_count = c1 + c2
        avg = (val1 * c1 + val2 * c2) / total_count if total_count != 0 else 0
        result.append(avg)
        updated_count.append(total_count)

    return result, updated_count

def average_elements_with_count(values, counts):
    return [val / count if count != 0 else 0 for val, count in zip(values, counts)]

from collections import defaultdict

def aggregate_and_average_results(replications, num_replications):
    def pad_and_average(lists):
        max_len = max(len(lst) for lst in lists)
        padded = [lst + [0] * (max_len - len(lst)) for lst in lists]
        counts = [[1] * len(lst) + [0] * (max_len - len(lst)) for lst in lists]
        summed = [sum(p[i] for p in padded) for i in range(max_len)]
        count_totals = [sum(c[i] for c in counts) for i in range(max_len)]
        return [s / c if c != 0 else 0 for s, c in zip(summed, count_totals)]

    aggregated = defaultdict(list)

    for rep in replications:
        for key, val in rep.items():
            aggregated[key].append(val)

    averaged_results = {}

    for key, val_list in aggregated.items():
        if isinstance(val_list[0], dict):
            averaged_results[key] = {}
            all_subkeys = set()
            for subdict in val_list:
                all_subkeys.update(subdict.keys())
            for subkey in all_subkeys:
                combined = [v.get(subkey, []) for v in val_list]
                if all(isinstance(x, list) for x in combined):
                    averaged_results[key][subkey] = pad_and_average(combined)
                else:
                    averaged_values = [v.get(subkey, 0) for v in val_list]
                    averaged_results[key][subkey] = sum(averaged_values) / len(averaged_values)
        else:
            if all(isinstance(x, list) for x in val_list):
                averaged_results[key] = pad_and_average(val_list)
            else:
                averaged_results[key] = sum(val_list) / len(val_list)

    return averaged_results

def find_alternative_sawmill(logging_site_id, assigned_sawmill_id, all_sawmills, travel_times_data):
    lowest_time = float('inf')
    alternative_sawmill = None
    # print(f"LS in alternative: {logging_site_id}")
    for sawmill_id, sawmill in all_sawmills.items():
        if sawmill_id == assigned_sawmill_id:
            continue  # Skip the originally assigned sawmill

        try:
            filtered = travel_times_data[
                (travel_times_data['Sawmill'] == sawmill_id) &
                (travel_times_data['LoggingSite'] == logging_site_id)
            ]
            if not filtered.empty:
                travel_time = filtered['Total_TruckTravelTime'].sum()
                if travel_time < lowest_time:
                    lowest_time = travel_time
                    alternative_sawmill = sawmill
                    # print(f'Alternative of {logging_site_id} is {alternative_sawmill.sawmill_id}')
        except Exception:
            continue

    return alternative_sawmill
