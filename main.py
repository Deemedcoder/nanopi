import json
import requests
from pysnmp.hlapi import *
import subprocess
import platform
import time

# API URL
fetch_url = "http://localhost/api.php"


def fetch_api_data(url):
    """
    Fetches JSON data from a given API URL.
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print("Failed to get data. Status code: {}".format(response.status_code))
            return None
    except Exception as e:
        print("Error fetching API data: {}".format(e))
        return None


# Ping function
def ping_device(hostname, timeout=1, count=1):
    """
    Pings a device to check its reachability.
    """
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        command = ["ping", param, str(count), timeout_param, str(timeout), hostname]
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output.returncode == 0
    except Exception as e:
        print("Error pinging device: {}".format(e))
        return False


# SNMP GET function
def snmp_get(ip, port, community, *oids):
    try:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(SnmpEngine(),
                   CommunityData(community, mpModel=1),
                   UdpTransportTarget((ip, port)),
                   ContextData(),
                   *object_types))

        if errorIndication:
            print("Error Indication: {}".format(errorIndication))
            return [None] * len(oids)
        elif errorStatus:
            print("Error Status: {} at {}".format(errorStatus.prettyPrint(), errorIndex))
            return [None] * len(oids)
        else:
            return [varBind[1].prettyPrint() for varBind in varBinds]
    except Exception as e:
        print("Exception in SNMP GET: {}".format(e))
        return [None] * len(oids)


# Function to process the data and query SNMP
def process_data_and_query_snmp(data_dict):
    result = {}

    if not isinstance(data_dict, dict):
        raise ValueError("Expected 'data_dict' to be a dictionary.")

    for hostname, device_data in data_dict.items():
        if not isinstance(device_data, dict):
            print("Expected a dictionary for device data: {}".format(device_data))
            continue

        ip = device_data.get("ip")
        port = device_data.get("port", 161)
        community = device_data.get("community_string")
        oids_str = device_data.get("oids")

        print("Processing device: {} ({})".format(hostname, ip))

        if not ping_device(ip):
            print("Device {} ({}) is not reachable. Skipping SNMP check.".format(hostname, ip))
            continue

        print("Device {} ({}) is reachable. Proceeding with SNMP check.".format(hostname, ip))

        try:
            oids_dict = json.loads(oids_str)
        except json.JSONDecodeError as e:
            print("Error decoding OID string: {}".format(e))
            continue

        oids = list(oids_dict.values())
        oids_name = list(oids_dict.keys())

        snmp_values = snmp_get(ip, port, community, *oids)

        device_result = {}
        for oid, value in zip(oids_name, snmp_values):
            device_result[oid] = value

        result[hostname] = device_result

    return result


# Get API endpoint function
def get_api_endpoint(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()

        if data.get('is_enabled') == '1':
            return data.get('api_endpoint')
        else:
            return None
    except requests.RequestException as e:
        print("An error occurred: {}".format(e))
        return None


def fetch_hardware_data_from_api():
    """
    Fetches JSON data from a hardcoded API URL.
    """
    # Hardcoded API URL
    api_url = "http://localhost/get_hardware_values.php"  # Replace with your API URL
    
    try:
        # Send the GET request to the API
        response = requests.get(api_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            return response.json()  # Return the response data as JSON
        else:
            print("Failed to get data. Status code: {}".format(response.status_code))
            return None
    except requests.exceptions.RequestException as e:
        # Handle any exceptions like connection errors
        print("Error fetching data from the API: {}".format(e))
        return None


# Send data to API function
def send_data_to_api(data, api_endpoint):
    try:
        print("Data type before sending:", type(data))
        response = requests.post(api_endpoint, json=data)  # JSON is passed automatically
        print("Response Code:", response.status_code)

        if response.status_code == 200:
            print("Data sent successfully!")
            print("Server response:", response.text)
        else:
            print("Failed to send data. Status code: {}".format(response.status_code))
            print("Response:", response.text)
    except Exception as e:
        print("Error sending data to server: {}".format(e))


# Convert data to desired format
def convert_data_format(data):
    detail_parts = []

    for key, value in data.items():
        if isinstance(value, dict):
            joined_values = "_".join(value.values())
            detail_parts.append("{}:{}".format(key, joined_values))
        else:
            detail_parts.append("{}:{}".format(key, value))

    detail_string = "||".join(detail_parts)
    print(detail_string)

    return {
        'mac': 1763377233,  # Keeping mac value fixed
        'detail': detail_string
    }


def merge_json_data(dict1, dict2):
    """
    Merges two dictionaries into one:
    - 'mac' is taken from dict1.
    - 'detail' from dict2 is combined with 'detail' from dict1.
    - 'values' from dict1 are appended in the format 'VALUE1_value', 'VALUE2_value', etc.
    """
    try:
        # Extract 'mac' from dict1 (we now use mac from dict1)
        mac = dict1.get('full_data', {}).get('mac', None)  # mac comes from dict1
        detail2 = dict2.get('detail', '')

        # Extract 'detail' and 'values' from dict1 (to append to detail2)
        detail1 = dict1.get('full_data', {}).get('detail', '')
        modbus_values = dict1.get('full_data', {}).get('values', [])

        # Combine both details with '||' separator
        combined_detail = "{}||{}".format(detail2, detail1)

        # Get the MODBUS values from dict1 and format them
        formatted_values = ["VALUE{}_{}".format(i + 1, value) for i, value in enumerate(modbus_values)]

        # Combine the formatted values into the 'detail' string
        combined_detail += '||' + '||'.join(formatted_values)

        # Prepare the resulting dictionary
        result = {
            'mac': mac,  # 'mac' from dict1
            'detail': combined_detail,  # Combined details from dict1 and dict2 with formatted values
        }

        return result

    except Exception as e:
        print("Error while merging data: {}".format(e))
        return None


# Main function to continuously run the program
def run_continuously():
    while True:
        try:
            # Fetch data from the API
            data = fetch_api_data(fetch_url)
            if data:
                final_result = process_data_and_query_snmp(data)

                # Convert SNMP result into the desired format
                formatted_data = convert_data_format(final_result)
                json_result = json.dumps(final_result, indent=4)
                print("The Json Value Is***************")
                #print(json_result)

                api_url = 'http://localhost/update_api.php'

                # Send the POST request with the result data
                headers = {'Content-Type': 'application/json'}
                response = requests.post(api_url, headers=headers, data=json_result)

                print("API Response Status Code:", response.status_code)
                print("API Response Body:", response.text)

                # Get the API endpoint from the server
                endpoint_url = "http://localhost/getapiendpoint.php"
                api_endpoint = get_api_endpoint(endpoint_url)

                if api_endpoint:
                    data_hardware = fetch_hardware_data_from_api()
                    #print(formatted_data)

                    main_final = merge_json_data(data_hardware, formatted_data)
                    print(type(formatted_data))

                    print(main_final)

                    # Send the formatted data to the API
                    send_data_to_api(main_final, api_endpoint)
                else:
                    print("API endpoint is not available")

        except Exception as e:
            print("Error occurred: {}".format(e))

        # Wait before the next cycle
        time.sleep(300)  # Run every 5 minutes


if __name__ == "__main__":
    run_continuously()
