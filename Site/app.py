import json
import time
from flask import Flask, jsonify, render_template, request
from chtgpt import *

app = Flask(__name__)
FILE_PATH = './topic/topic.json'
FILE_PATH_STR='./topic/topicstring.txt'
# Sample data for dropdown options
OPTIONS = ["Option 1", "Option 2", "Option 3", "Option 4"]

@app.route('/')
def index():
    return render_template('index.html')

'''@app.route('/topics', methods=['GET'])
def get_topics():
    with open('./topic/topicstring.txt', 'r') as file:
        topic = file.readline().strip()  # Read the single line and strip whitespace
    return topic, 200  # Return the line as plain text
'''
@app.route('/topics', methods=['GET'])
def get_topics():
    with open('./topic/topicstring.txt', 'r') as file:
        topic = file.readline().strip()  # Read the single line and strip whitespace
    topics_list = topic.split(',')  # Split the string into a list
    response = jsonify(topics_list)
    return response, 200  # Return as JSON
@app.route('/api/options', methods=['GET'])
def api_options():
    result = get_hot_topics()
    word_list = result.split(',')
    # Return the dropdown options as JSON
    return jsonify({"options": word_list})

@app.route('/submit', methods=['POST'])

def submit():
    # Getting the input from 'customInputField'
    custom_input = request.form.get('customInput')

    # Assuming 'query_chatgpt' is a function that takes the topic and returns a comma-separated string
    result = query_chatgpt(custom_input)
    word_list = result.split(',')

    # Write results to a JSON file
    json_data = {custom_input: word_list}
    with open(FILE_PATH, 'w') as file:
        json.dump(json_data, file, indent=4)

    # Write results to a text file
    with open(FILE_PATH_STR, 'w') as file2:
        out_string = custom_input.strip() + ',other'
        file2.write(out_string)
    
    # Simulating processing delay (10 seconds)
    time.sleep(3)
    
    # Constructing the result URL
    result_url = f"http://20.188.226.121/?orgId=1&refresh=5s&topic={custom_input}"

    # Return the result (URL) in JSON format
    return jsonify({"status": "success", "url": result_url})

if __name__ == '__main__':
    app.run(debug=True)
