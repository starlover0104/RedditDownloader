import praw
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from praw.exceptions import RedditAPIException, ClientException, PRAWException

def read_api_credentials():
    try:
        with open('API.txt', 'r') as file:
            lines = file.readlines()
            if len(lines) < 3:
                raise ValueError("API.txt should contain at least 3 lines")
            return {
                'client_id': lines[0].strip(),
                'client_secret': lines[1].strip(),
                'user_agent': lines[2].strip()
            }
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {str(e)}")
        exit(1)

def get_reddit_instance():
    credentials = read_api_credentials()
    try:
        return praw.Reddit(
            client_id=credentials['client_id'],
            client_secret=credentials['client_secret'],
            user_agent=credentials['user_agent']
        )
    except (ClientException, PRAWException) as e:
        print(f"Error creating Reddit instance: {str(e)}")
        exit(1)

def get_downloads_folder(content_type):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_folder = os.path.join(script_dir, 'Reddit_downloads')
        content_folder = os.path.join(base_folder, content_type.capitalize())
        os.makedirs(content_folder, exist_ok=True)
        return content_folder
    except Exception as e:
        print(f"Error creating download folders: {str(e)}")
        exit(1)

def download_file(url, filename, download_folder):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        file_path = os.path.join(download_folder, filename)
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Downloaded {filename} to {file_path}")
        return True
    except requests.RequestException as e:
        print(f"Error downloading file {filename}: {str(e)}")
        return False

def save_text(selftext, filename, download_folder):
    try:
        file_path = os.path.join(download_folder, filename)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(selftext)
        print(f"Saved text post to {file_path}")
        return True
    except IOError as e:
        print(f"Error saving text file {filename}: {str(e)}")
        return False

def get_available_flairs(subreddit):
    try:
        flairs = set()
        for submission in subreddit.hot(limit=10000):
            if submission.link_flair_text:
                flairs.add(submission.link_flair_text)
        return list(flairs)
    except RedditAPIException as e:
        print(f"Error fetching flairs: {str(e)}")
        return []

def countdown_timer(seconds):
    for remaining in range(seconds, 0, -1):
        print(f"\rCooldown: {remaining} seconds remaining", end='', flush=True)
        time.sleep(1)
    print("\rCooldown complete. Resuming downloads...                ")

def scrape_reddit(subreddit_name, count, num_threads, download_type, flair=None):
    reddit = get_reddit_instance()
    try:
        subreddit = reddit.subreddit(subreddit_name)
        posts = [submission for submission in subreddit.hot(limit=count) if (not flair or submission.link_flair_text == flair)]
    except RedditAPIException as e:
        print(f"Error accessing subreddit {subreddit_name}: {str(e)}")
        return

    total_downloads = 0
    batch_size = 100
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i+batch_size]
        batch_downloads = 0
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for submission in batch:
                if download_type in ['media', 'both'] and hasattr(submission, 'url') and submission.url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4')):
                    media_name = os.path.basename(submission.url)
                    media_folder = get_downloads_folder('Media')
                    futures.append(executor.submit(download_file, submission.url, media_name, media_folder))
                
                if download_type in ['text', 'both'] and submission.selftext:
                    text_filename = f"{submission.id}_text.txt"
                    text_folder = get_downloads_folder('Text')
                    futures.append(executor.submit(save_text, submission.selftext, text_filename, text_folder))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        batch_downloads += 1
                except Exception as e:
                    print(f"Error in future task: {str(e)}")

        total_downloads += batch_downloads
        print(f"\nCompleted {batch_downloads} downloads in this batch. Total downloads: {total_downloads}")
        
        if i + batch_size < len(posts):
            print(f"Starting cooldown...")
            countdown_timer(60)

    print(f"\nAll downloads completed. Total successful downloads: {total_downloads}")

def print_title():
    title = r"""
 ____           _     _ _ _     ____                      _                 _           
|  _ \ ___   __| | __| (_) |_  |  _ \  _____      ___ __ | | ___   __ _  __| | ___ _ __ 
| |_) / _ \ / _` |/ _` | | __| | | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
|  _ < (_) | (_| | (_| | | |_  | |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
|_| \_\___/ \__,_|\__,_|_|\__| |____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   
                                                                                        
                        - made by Starlover
    """
    print(title)

def search_subreddits(query):
    reddit = get_reddit_instance()
    try:
        return list(reddit.subreddits.search(query, limit=10))
    except RedditAPIException as e:
        print(f"Error searching subreddits: {str(e)}")
        return []

def main():
    print_title()
    
    search_query = input("Enter a search query for subreddits: ")
    matching_subreddits = search_subreddits(search_query)
    
    if not matching_subreddits:
        print("No matching subreddits found.")
        return

    print("Top matching subreddits:")
    for i, subreddit in enumerate(matching_subreddits, 1):
        print(f"{i}. r/{subreddit.display_name} - {subreddit.title}")

    choice = int(input("Enter the number of the subreddit you want to download from: "))
    if choice < 1 or choice > len(matching_subreddits):
        print("Invalid choice.")
        return

    selected_subreddit = matching_subreddits[choice - 1]
    subreddit_name = selected_subreddit.display_name

    download_type = input("What do you want to download? ([M]edia [T]ext [B]oth): ").lower()
    if download_type not in ['m', 't', 'b']:
        print("Invalid choice for download type.")
        return

    count = int(input("Enter the number of posts to process: "))
    num_threads = int(input("Enter the number of concurrent downloads: "))

    if count <= 0 or num_threads <= 0:
        print("The number of posts and concurrent downloads must be positive integers.")
        return

    if download_type == 'm':
        download_type = 'media'
    elif download_type == 't':
        download_type = 'text'
    elif download_type == 'b':
        download_type = 'both'

    available_flairs = get_available_flairs(selected_subreddit)

    flair = None
    if available_flairs:
        print("Available flairs:")
        for i, flair_text in enumerate(available_flairs, 1):
            print(f"{i}. {flair_text}")
        flair_choice = input("Enter the number of the flair you want to filter from (Leave blank for all): ")
        if flair_choice.isdigit() and 1 <= int(flair_choice) <= len(available_flairs):
            flair = available_flairs[int(flair_choice) - 1]

    scrape_reddit(subreddit_name, count, num_threads, download_type, flair)

if __name__ == "__main__":
    main()
