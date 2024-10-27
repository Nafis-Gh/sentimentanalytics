from openai import OpenAI
import os 

API_key = os.getenv('REDDIT_CLIENT_ID')
client = OpenAI(
    # This is the default and can be omitted
    api_key=API_key,
)

def query_chatgpt(topic):
    client = OpenAI(api_key=API_key)

    # Use the topic in the content of the message
    query_message = f"Provide 20 keywords related to '{topic}' with no extra explanation in a comma separated format all lowercase without space at start, without space at end and without space after comma, add the given topic itself in the keywords list"

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": query_message}],
        stream=True,
    )

    # Print the response in chunks
    result = ""
    # Collect the response in chunks
    for chunk in stream:
        result += chunk.choices[0].delta.content or ""

    return result.strip()

# Example usage
#topic_name = "fashion"  # You can change this to any topic you want
#query_chatgpt(topic_name)
def get_hot_topics():
    client = OpenAI(api_key=API_key)

    # Use the topic in the content of the message
    query_message = f"Provide 5 2024 last querter single word hot topics in different subjects with no extra explanation in a comma separated format with first capital letter without space at start, at end and after comma"

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": query_message}],
        stream=True,
    )

    # Print the response in chunks
    result = ""
    # Collect the response in chunks
    for chunk in stream:
        result += chunk.choices[0].delta.content or ""

    return result.strip()
