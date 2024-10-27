#TODO: add logs and error handling
from json import dumps
from kafka import KafkaProducer
import configparser
import praw
import threading
import os

threads = []
#top_subreddit_list = ['AskReddit', 'funny', 'gaming', 'aww', 'worldnews']
countries_subreddit_list = ['india', 'usa', 'unitedkingdom', 'australia', 'AskARussian', 'China', 'Japan', 'southkorea']


class RedditProducer:

    def __init__(self, subreddit_list: list[str]):

        self.subreddit_list = subreddit_list
        self.reddit = self.__get_reddit_client__()
        self.producer = KafkaProducer(bootstrap_servers=['kafkaservice:9092'],
                            value_serializer=lambda x:
                            dumps(x).encode('utf-8')
                        )


    def __get_reddit_client__(self) -> praw.Reddit:
        

        try:
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT')
            refresh_token = os.getenv('REDDIT_REFRESH_TOKEN')
            
        except:
            raise ValueError("Could not load the secrets from environment variables")
        
        return praw.Reddit(
            user_agent = user_agent,
            client_id = client_id,
            client_secret = client_secret,
            refresh_token = refresh_token
        )
        
    def start_stream(self, subreddit_name) -> None:
        subreddit = self.reddit.subreddit(subreddit_name)
        comment: praw.models.Comment
        # Fetch recent comments first
        #print(f"Fetching recent comments from {subreddit_name}")
        for comment in subreddit.comments(limit=20000):
            try:
                comment_json: dict[str, str] = {
                    "id": comment.id,
                    "author": comment.author.name if comment.author else "deleted",
                    "body": comment.body,
                    "subreddit": comment.subreddit.display_name,
                    "upvotes": comment.ups,
                    "downvotes": comment.downs,
                    "over_18": comment.over_18,
                    "timestamp": comment.created_utc,
                    "permalink": comment.permalink,
                }
                
                self.producer.send("redditcomments", value=comment_json)
                print(f"subreddit: {subreddit_name}, comment: {comment_json}")
            except Exception as e:
                print("An error occurred:", str(e))
        for comment in subreddit.stream.comments(skip_existing=True):
            try:
                comment_json: dict[str, str] = {
                    "id": comment.id,
                    "author": comment.author.name if comment.author else "deleted",
                    "body": comment.body,
                    "subreddit": comment.subreddit.display_name,
                    "upvotes": comment.ups,
                    "downvotes": comment.downs,
                    "over_18": comment.over_18,
                    "timestamp": comment.created_utc,
                    "permalink": comment.permalink,
                }
                
                self.producer.send("redditcomments", value=comment_json)
                print(f"subreddit: {subreddit_name}, comment: {comment_json}")
            except Exception as e:
                print("An error occurred:", str(e))
    
    def start_streaming_threads(self):
        for subreddit_name in self.subreddit_list:
            thread = threading.Thread(target=self.start_stream, args=(subreddit_name,))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()


if __name__ == "__main__":
    reddit_producer = RedditProducer(countries_subreddit_list)
    reddit_producer.start_streaming_threads()
