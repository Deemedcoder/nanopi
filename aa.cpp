#include <iostream>
#include <string>
#include <curl/curl.h>
#include <sstream>
#include <json/json.h>  // You can use nlohmann/json too
#include <fstream>
#include <chrono>
#include <thread>
#include <cstdlib>
#include <stdexcept>
#include <vector>
#include <map>

using namespace std;

const string FETCH_URL = "http://localhost/api.php";

// Function to fetch API data using cURL
string fetch_api_data(const string &url) {
    CURL *curl;
    CURLcode res;
    string readBuffer;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
        res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            cerr << "cURL failed: " << curl_easy_strerror(res) << endl;
        }
        curl_easy_cleanup(curl);
    }
    curl_global_cleanup();
    return readBuffer;
}

// Callback function for handling cURL data
size_t WriteCallback(void *contents, size_t size, size_t nmemb, string *output) {
    size_t total_size = size * nmemb;
    output->append((char *)contents, total_size);
    return total_size;
}

// Function to ping a device
bool ping_device(const string &hostname, int timeout = 1) {
    string command = "ping -c 1 -W " + to_string(timeout) + " " + hostname + " > /dev/null 2>&1";
    return system(command.c_str()) == 0;
}

// Function to simulate SNMP GET (You need an SNMP C++ library such as snmp++ or net-snmp for this part)
vector<string> snmp_get(const string &ip, int port, const string &community, const vector<string> &oids) {
    // Placeholder for SNMP GET implementation
    vector<string> values;
    for (const auto &oid : oids) {
        // Simulate an SNMP GET operation
        values.push_back("value_of_" + oid); // Replace with actual SNMP operation
    }
    return values;
}

// Function to process the API data and SNMP requests
map<string, map<string, string>> process_data_and_query_snmp(const Json::Value &data) {
    map<string, map<string, string>> result;

    for (const auto &hostname : data.getMemberNames()) {
        const auto &device_data = data[hostname];
        string ip = device_data["ip"].asString();
        string community = device_data["community_string"].asString();
        string oids_str = device_data["oids"].asString();
        Json::Value oids_json;
        Json::Reader reader;

        if (reader.parse(oids_str, oids_json)) {
            vector<string> oids;
            for (const auto &key : oids_json.getMemberNames()) {
                oids.push_back(oids_json[key].asString());
            }

            if (!ping_device(ip)) {
                cerr << "Device " << hostname << " is unreachable." << endl;
                continue;
            }

            vector<string> snmp_values = snmp_get(ip, 161, community, oids);
            map<string, string> device_result;
            for (size_t i = 0; i < oids.size(); ++i) {
                device_result[oids[i]] = snmp_values[i];
            }
            result[hostname] = device_result;
        } else {
            cerr << "Failed to parse OIDs for " << hostname << endl;
        }
    }
    return result;
}

// Function to send data to the API
void send_data_to_api(const Json::Value &data, const string &api_endpoint) {
    CURL *curl;
    CURLcode res;
    stringstream ss;
    ss << data;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, api_endpoint.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, ss.str().c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, ss.str().length());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, nullptr); // Set content type if needed
        res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            cerr << "cURL failed: " << curl_easy_strerror(res) << endl;
        }
        curl_easy_cleanup(curl);
    }
    curl_global_cleanup();
}

// Main loop to fetch, process and send data
void run_continuously() {
    while (true) {
        try {
            string api_data = fetch_api_data(FETCH_URL);
            if (!api_data.empty()) {
                Json::Value jsonData;
                Json::Reader reader;
                if (reader.parse(api_data, jsonData)) {
                    map<string, map<string, string>> snmp_result = process_data_and_query_snmp(jsonData);
                    Json::Value final_result;
                    // You can modify this to match the desired output structure
                    final_result["snmp_result"] = Json::Value(Json::objectValue);

                    for (const auto &hostname : snmp_result) {
                        Json::Value device_data(Json::objectValue);
                        for (const auto &oid : hostname.second) {
                            device_data[oid.first] = oid.second;
                        }
                        final_result["snmp_result"][hostname.first] = device_data;
                    }

                    string api_endpoint = "http://localhost/api_endpoint.php";
                    send_data_to_api(final_result, api_endpoint);
                } else {
                    cerr << "Failed to parse API data." << endl;
                }
            }
        } catch (const exception &e) {
            cerr << "Error in main loop: " << e.what() << endl;
        }

        // Wait for 60 seconds before running again
        this_thread::sleep_for(chrono::seconds(60));
    }
}

int main() {
    run_continuously();
    return 0;
}
