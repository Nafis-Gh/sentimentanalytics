from nltk.sentiment import SentimentIntensityAnalyzer
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, from_json, col, lit, from_unixtime, avg, current_timestamp, count, when, to_timestamp
from pyspark.sql.types import StringType, StructType, StructField, IntegerType, BooleanType, FloatType, TimestampType
from rake_nltk import Rake
import uuid
import json
import threading
import time
from pyspark.sql import functions as F



# Initialize Spark session
spark: SparkSession = SparkSession.builder \
    .appName("StreamProcessor") \
    .config('spark.cassandra.connection.host', 'cassandra') \
    .config('spark.cassandra.connection.port', '9042') \
    .config('spark.cassandra.output.consistency.level', 'ONE') \
    .getOrCreate()

# Kafka configurations
kafka_bootstrap_servers = "kafkaservice:9092"
kafka_topic = "redditcomments"



# Define the function to analyze sentiment using NLTK's SentimentIntensityAnalyzer
def analyze_sentiment(text):
    if not text:
        return 0
    analyzer = SentimentIntensityAnalyzer()
    sentiment = analyzer.polarity_scores(text)
    return sentiment['compound']


# UUID generator for unique keys
def make_uuid():
    return str(uuid.uuid4())

# Function to classify country from subreddit
def classify_country(subreddit):
    subreddit_to_country = {
        'india': 'India',
        'usa': 'USA',
        'unitedkingdom': 'United Kingdom',
        'australia': 'Australia',
        'askarussian': 'Russia',
        'china': 'China',
        'japan': 'Japan',
        'southkorea': 'SouthKorea'
    }
    return subreddit_to_country.get(subreddit.lower(), 'Unknown')


# Broadcast the JSON data to all workers
file_path = "/mnt/topic/topic.json"
with open(file_path, 'r') as f:
    json_data = json.load(f)

# Convert the JSON structure into a broadcast dictionary
topic_keyword_dict = {keyword.strip(): topic for topic, keywords in json_data.items() for keyword in keywords}
broadcasted_topic_keyword_dict = spark.sparkContext.broadcast(topic_keyword_dict)


# UDF to find the topic based on the keyword
def find_topic(keywords):
    if keywords is None or len(keywords.strip()) == 0:
        return "other", None  # Return 'other' and None for no keywords

    topics = []
    matched_keywords = []
    for keyword in keywords.split(","):
        keyword = keyword.strip().lower()
        if keyword in broadcasted_topic_keyword_dict.value:
            topics.append(broadcasted_topic_keyword_dict.value[keyword])
            matched_keywords.append(keyword)
    
    topic = ",".join(topics) if topics else "other"
    matched_keyword = ",".join(matched_keywords) if matched_keywords else None
    return topic, matched_keyword


# UDF for country and topic and sentiment classification

find_topic_udf = udf(find_topic, StructType([
    StructField("topic", StringType(), True),
    StructField("matched_keyword", StringType(), True)
]))
sentiment_udf = udf(analyze_sentiment, FloatType())
classify_country_udf = udf(classify_country, StringType())


#-----------------------#

# Initialize a variable to store the previous topic (empty at first)
previous_topic = None

# Load the JSON file into a dictionary
def load_json_topic():
    file_path = "/mnt/topic/topic.json"
    with open(file_path, 'r') as f:
        json_data = json.load(f)
    return json_data

# Function to compare topics and process if changed
def process_if_topic_changed():
    global previous_topic

    # Load the current JSON topic
    json_data = load_json_topic()
    current_topic = list(json_data.keys())[0]  # Assuming the JSON structure has one main topic

    # If the topic hasn't changed, do nothing
    if current_topic == previous_topic:
        print(f"No changes detected. Previous topic: {previous_topic}, Current topic: {current_topic}")
        return

    # If the topic has changed, update the previous topic
    print(f"Topic changed from {previous_topic} to {current_topic}")
    previous_topic = current_topic

    # Convert the JSON structure into a dictionary
    topic_keyword_dict = {keyword.strip(): current_topic for topic, keywords in json_data.items() for keyword in keywords}

    # UDF to match keywords from the comments and assign the new topic
    def assign_new_topic(keywords):
        if keywords is None or len(keywords.strip()) == 0:
            return "other", None  # Return 'other' and None if no keywords

        for keyword in keywords.split(","):
            keyword = keyword.strip().lower()
            if keyword in topic_keyword_dict:
                return topic_keyword_dict[keyword], keyword  # Return both the topic and the matched keyword

        return "other", None  # Default to 'other' and None if no match found


    # Register the UDF to return both topic and matched keyword
    assign_new_topic_udf = udf(assign_new_topic, StructType([
        StructField("topic", StringType(), True),
        StructField("matched_keyword", StringType(), True)
    ]))


    # Load the comments from Cassandra
    comments_df = spark.read \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="comments", keyspace="reddit") \
        .load()

        # Apply the UDF to update topics based on JSON keywords
    updated_comments_df = comments_df.withColumn("topic_keyword", assign_new_topic_udf(col("keywords")))

    # Split the result into 'topic' and 'matched_keyword' columns
    updated_comments_df = updated_comments_df.withColumn("topic", col("topic_keyword.topic")) \
                                            .withColumn("matched_keyword", col("topic_keyword.matched_keyword")) \
                                            .drop("topic_keyword")



    # Insert or update rows in the country_sentiment table with the new topic
    country_sentiment_df = updated_comments_df.select("country", "topic", "api_timestamp", "ingest_timestamp", "sentiment_score")

    # Perform aggregation
    country_sentiment_agg_df = country_sentiment_df.groupBy("country", "topic", "api_timestamp") \
        .agg(
            avg(col("sentiment_score")).alias("sentiment_score_avg"),
            count(when(col("sentiment_score") >= 0.05, True)).alias("positive_count"),
            count(when(col("sentiment_score") <= -0.05, True)).alias("negative_count"),
            count(when((col("sentiment_score") > -0.05) & (col("sentiment_score") < 0.05), True)).alias("neutral_count")
        ).withColumn("ingest_timestamp", current_timestamp())

    # Write to the country_sentiment table in Cassandra
    country_sentiment_agg_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="country_sentiment", keyspace="reddit") \
        .mode("append") \
        .save()
    
        # Country-to-ISO code mapping
    country_iso_mapping_hist = [
        ("India", "IN"),
        ("USA", "US"),
        ("United Kingdom", "GB"),
        ("Australia", "AU"),
        ("Russia", "RU"),
        ("Japan", "JP"),
        ("China", "CN")
    ]

    # Create a DataFrame with the mapping
    country_iso_hist_df = spark.createDataFrame(country_iso_mapping_hist, ["country_name", "iso_code"])

    # Main country sentiment DataFrame (Assuming 'country_sentiment_df' is your main DataFrame)
    # Join with the ISO mapping to add iso_code column
    country_sentiment_with_iso_df = country_sentiment_agg_df.join(
        country_iso_hist_df,
        country_sentiment_agg_df["country"] == country_iso_hist_df["country_name"],
        "left"
    ).drop("country_name")
    
    # Aggregate the data by country
    summary_df = country_sentiment_with_iso_df.groupBy("country","topic", "iso_code", "api_timestamp") \
        .agg(
        F.sum(col("positive_count")).alias("total_positive"),
        F.sum(col("negative_count")).alias("total_negative"),
        F.sum(col("neutral_count")).alias("total_neutral"),
        F.avg(col("sentiment_score_avg")).alias("sentiment_score_avg")
    ).withColumn("ingest_timestamp", current_timestamp())
    

    # Write the aggregated data to the new summary table
    summary_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="country_sentiment_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    
    topic_summary_df = updated_comments_df.groupBy("topic", "matched_keyword", "api_timestamp") \
    .agg(
        F.count("*").alias("comment_count")
    ).withColumn("ingest_timestamp", current_timestamp())

    topic_summary_df = topic_summary_df.fillna({'topic': 'other', 'matched_keyword': 'unknown'})

# Write the aggregated data to the new summary table
    topic_summary_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="topic_comment_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    

    # Pre-aggregate comment count by topic and matched_keyword
    matched_keyword_df = updated_comments_df.groupBy("topic","country", "matched_keyword", "api_timestamp") \
        .agg(
            F.count("*").alias("comment_count")
        ).withColumn("ingest_timestamp", current_timestamp())
    
    matched_keyword_df = matched_keyword_df.fillna({'matched_keyword': 'unknown'})

    # Write to a new table to store pre-aggregated data
    matched_keyword_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="topic_matched_keyword_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    

# Periodically check for topic changes and process if changed
def periodic_check():
    while True:
        process_if_topic_changed()
        time.sleep(60)  # Check every minute

# Start the periodic task
task_thread = threading.Thread(target=periodic_check)
task_thread.start()


#-----------------------#
# Initialize RAKE (Rapid Automatic Keyword Extraction)
rake = Rake()

# Define the function to extract keywords using RAKE
def extract_keywords_rake(text):
    rake.extract_keywords_from_text(text)
    keywords = rake.get_ranked_phrases()  # Get the ranked keyword phrases
    if keywords:
        return ','.join(keywords)  # Return keywords as comma-separated string
    return None

# UDF to extract keywords using RAKE
extract_keywords_rake_udf = udf(extract_keywords_rake, StringType())

#---------------------#

# Define the schema for the JSON value column
comment_schema = StructType([
    StructField("id", StringType(), True),
    StructField("name", StringType(), True),
    StructField("author", StringType(), True),
    StructField("body", StringType(), True),
    StructField("subreddit", StringType(), True),
    StructField("upvotes", IntegerType(), True),
    StructField("downvotes", IntegerType(), True),
    StructField("over_18", BooleanType(), True),
    StructField("timestamp", FloatType(), True),
    StructField("permalink", StringType(), True),
])

# Read from Kafka
df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
    .option("subscribe", kafka_topic) \
    .load()

# Parse the value column as JSON
parsed_df = df.withColumn("comment_json", from_json(df["value"].cast("string"), comment_schema))

# Process and select relevant columns
output_df = parsed_df.select(
        "comment_json.id",
        "comment_json.name",
        "comment_json.author",
        "comment_json.body",
        "comment_json.subreddit",
        "comment_json.upvotes",
        "comment_json.downvotes",
        "comment_json.over_18",
        "comment_json.timestamp",  
        "comment_json.permalink"
    ) \
    .withColumn("uuid", udf(lambda: str(uuid.uuid4()), StringType())()) \
    .withColumn("api_timestamp", from_unixtime(col("timestamp").cast(FloatType()))) \
    .withColumn("ingest_timestamp", current_timestamp()) \
    .drop("timestamp")


# Sentiment and Topic Classification
output_df = output_df.withColumn('sentiment_score', sentiment_udf(output_df['body']))
output_df = output_df.withColumn("country", classify_country_udf(output_df['subreddit']))


# Apply the new UDF to extract keywords using RAKE
output_df = output_df.withColumn("keywords", extract_keywords_rake_udf(output_df['body']))


# Write comments to the `comments` table
output_df.writeStream \
    .option("checkpointLocation", "/tmp/check_point/") \
    .option("failOnDataLoss", "false") \
    .format("org.apache.spark.sql.cassandra") \
    .options(table="comments", keyspace="reddit") \
    .start()

#------------------#

#Explode the keywords column and apply the UDF to get the topic
output_df_with_topics = output_df.withColumn(
    "topic_keyword", find_topic_udf(output_df["keywords"])
)

# Split the result into two columns: 'topic' and 'matched_keyword'
output_df_with_topics = output_df_with_topics.withColumn("topic", col("topic_keyword.topic")) \
                                             .withColumn("matched_keyword", col("topic_keyword.matched_keyword")) \
                                             .drop("topic_keyword")

# Step 4: Convert `api_timestamp` to timestamp format
output_df_with_topics = output_df_with_topics.withColumn(
    "api_timestamp", to_timestamp(col("api_timestamp"), "yyyy-MM-dd HH:mm:ss")
)

# Apply watermark on `api_timestamp` column to allow for aggregation in append mode
output_df_with_topics = output_df_with_topics.withWatermark("api_timestamp", "1 minutes")


# Step 5: Perform the aggregation based on the `topic` column with the applied watermark
country_sentiment_df = output_df_with_topics \
    .groupBy("country", "topic", "api_timestamp") \
    .agg(
        avg(col("sentiment_score")).alias("sentiment_score_avg"),
        count(when(col("sentiment_score") >= 0.05, True)).alias("positive_count"),
        count(when(col("sentiment_score") <= -0.05, True)).alias("negative_count"),
        count(when((col("sentiment_score") > -0.05) & (col("sentiment_score") < 0.05), True)).alias("neutral_count")
    ).withColumn("ingest_timestamp", current_timestamp())

# Replace null values in the 'topic' column with 'other'
country_sentiment_df = country_sentiment_df.fillna({'topic': 'other'})

# Country-to-ISO code mapping
country_iso_mapping = [
    ("India", "IN"),
    ("USA", "US"),
    ("United Kingdom", "GB"),
    ("Australia", "AU"),
    ("Russia", "RU"),
    ("Japan", "JP"),
    ("China", "CN")
]

# Create a DataFrame with the mapping
country_iso_df = spark.createDataFrame(country_iso_mapping, ["country_name", "iso_code"])

# Main country sentiment DataFrame (Assuming 'country_sentiment_df' is your main DataFrame)
# Join with the ISO mapping to add iso_code column
country_sentiment_with_iso_df = country_sentiment_df.join(
    country_iso_df,
    country_sentiment_df["country"] == country_iso_df["country_name"],
    "left"
).drop("country_name")

# Aggregate the data by country
country_summary_df = country_sentiment_with_iso_df.groupBy("country","topic","iso_code", "api_timestamp") \
        .agg(
        F.sum(col("positive_count")).alias("total_positive"),
        F.sum(col("negative_count")).alias("total_negative"),
        F.sum(col("neutral_count")).alias("total_neutral"),
        F.avg(col("sentiment_score_avg")).alias("sentiment_score_avg")
    ).withColumn("ingest_timestamp", current_timestamp())

topic_comment_summary_df = output_df_with_topics.groupBy("topic",  "matched_keyword", "api_timestamp") \
    .agg(
        F.count("*").alias("comment_count")
    ).withColumn("ingest_timestamp", current_timestamp())

topic_comment_summary_df = topic_comment_summary_df.fillna({'topic': 'other', 'matched_keyword': 'unknown'})

# Pre-aggregate comment count by topic and matched_keyword
matched_keyword_summary_df = output_df_with_topics.groupBy("topic","country", "matched_keyword", "api_timestamp") \
    .agg(
        F.count("*").alias("comment_count")
    ).withColumn("ingest_timestamp", current_timestamp())

matched_keyword_summary_df = matched_keyword_summary_df.fillna({'matched_keyword': 'unknown'})


# Step 6: Define the `foreachBatch` function to write to Cassandra
def write_to_cassandra(batchDF, batchID):
    # Ensure all columns are included when writing to Cassandra
    batchDF.select(
        "country", "topic", "api_timestamp", "ingest_timestamp", 
        "sentiment_score_avg", "positive_count", "negative_count", "neutral_count"
    ).write \
        .format("org.apache.spark.sql.cassandra") \
        .option("checkpointLocation", "/tmp/check_point_country_sentiment/") \
        .options(table="country_sentiment", keyspace="reddit") \
        .mode("append") \
        .save()
    
    
def write_to_cassandra2(batchDF, batchID):
    # Ensure all columns are included when writing to Cassandra
    batchDF.write \
        .format("org.apache.spark.sql.cassandra") \
        .option("checkpointLocation", "/tmp/check_point_country_summary/") \
        .options(table="country_sentiment_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    
# Define the `foreachBatch` function to write to the Cassandra table
def write_topic_summary_to_cassandra(batchDF, batchID):
    batchDF.write \
        .format("org.apache.spark.sql.cassandra") \
        .option("checkpointLocation", "/tmp/check_point_comment_summary/") \
        .options(table="topic_comment_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    
# Define the `foreachBatch` function to write to the Cassandra table
def write_keyword_summary_to_cassandra(batchDF, batchID):
    batchDF.write \
        .format("org.apache.spark.sql.cassandra") \
        .option("checkpointLocation", "/tmp/check_point_keyword_summary/") \
        .options(table="topic_matched_keyword_summary", keyspace="reddit") \
        .mode("append") \
        .save()
    


# Start the streaming query using foreachBatch
query1 = country_sentiment_df.writeStream \
    .trigger(processingTime="10 seconds") \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .start()

# Start the streaming query using foreachBatch
query2 = country_summary_df.writeStream \
    .trigger(processingTime="10 seconds") \
    .foreachBatch(write_to_cassandra2) \
    .outputMode("append") \
    .start() 

# Start the streaming query for the topic summary
query3 = topic_comment_summary_df.writeStream \
    .trigger(processingTime="10 seconds") \
    .foreachBatch(write_topic_summary_to_cassandra) \
    .outputMode("append") \
    .start()

# Start the streaming query using foreachBatch
query4 = matched_keyword_summary_df.writeStream \
    .trigger(processingTime="10 seconds") \
    .foreachBatch(write_keyword_summary_to_cassandra) \
    .outputMode("append") \
    .start() 

# Await termination for the streaming query
query1.awaitTermination()
query2.awaitTermination()
query3.awaitTermination()
query4.awaitTermination()


#------------------#


spark.streams.awaitAnyTermination()