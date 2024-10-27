    -- Create the keyspace if it doesn't exist
CREATE KEYSPACE IF NOT EXISTS reddit 
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE reddit;

-- Table to store individual comments (for reference or further analysis)
CREATE TABLE IF NOT EXISTS comments (
    uuid uuid,
    id text,
    name text,
    author text,
    body text,
    subreddit text,
    upvotes int,
    downvotes int,
    over_18 boolean,
    permalink text,
    api_timestamp timestamp,
    ingest_timestamp timestamp,
    sentiment_score float,
    keywords text,
    country text, 
    PRIMARY KEY((subreddit), api_timestamp)
)
WITH CLUSTERING ORDER BY (api_timestamp DESC);

CREATE INDEX IF NOT EXISTS ON comments (uuid);

-- Table to store positive/negative sentiment counts per country and topic
CREATE TABLE IF NOT EXISTS country_sentiment (
    
    country text,
    topic text,
    api_timestamp timestamp,
    ingest_timestamp timestamp,
    positive_count int,
    negative_count int,
    neutral_count int,
    sentiment_score_avg double,
    PRIMARY KEY((country), topic, api_timestamp)
);

CREATE TABLE IF NOT EXISTS country_sentiment_summary (
    country text,
    topic text,
    iso_code text,
    api_timestamp timestamp,
    ingest_timestamp timestamp,
    total_positive int,
    total_negative int,
    total_neutral int,
    sentiment_score_avg double,
    PRIMARY KEY(country, api_timestamp)
);

CREATE TABLE IF NOT EXISTS topic_comment_summary (
    topic text,
    matched_keyword text,
    api_timestamp timestamp,
    ingest_timestamp timestamp,
    comment_count int,
    PRIMARY KEY ((topic), matched_keyword, api_timestamp)
);

CREATE TABLE IF NOT EXISTS topic_matched_keyword_summary (
    topic text,
    country text,
    matched_keyword text,
    comment_count int,
    api_timestamp timestamp,
    ingest_timestamp timestamp,
    PRIMARY KEY ((topic), matched_keyword, api_timestamp)
);



