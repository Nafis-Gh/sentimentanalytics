FROM apache/spark-py:v3.4.0
ARG spark_id=185

# Installing nltk and required files
USER root
RUN pip install nltk
RUN pip install rake-nltk

# Create NLTK data directory and download only required resources
RUN mkdir -p /usr/local/nltk_data
RUN python3 -m nltk.downloader -d /usr/local/nltk_data punkt vader_lexicon stopwords punkt_tab 

# Adjust ownership to the Spark user
RUN chown -R ${spark_id}:${spark_id} /usr/local/nltk_data

USER ${spark_id}

# Set the NLTK data environment variable
ENV NLTK_DATA=/usr/local/nltk_data

WORKDIR /src
COPY . .

# Check https://stackoverflow.com/a/69559038/12382622
CMD /opt/spark/bin/spark-submit --conf spark.driver.extraJavaOptions="-Divy.cache.dir=/tmp -Divy.home=/tmp" \
    --packages org.apache.spark:spark-streaming-kafka-0-10_2.12:3.3.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,com.datastax.spark:spark-cassandra-connector_2.12:3.2.0 \
    stream_processor.py
