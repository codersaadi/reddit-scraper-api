import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import argparse
import os
import logging
from datetime import datetime
import concurrent.futures
import pandas as pd
import random
from urllib.parse import urljoin

class EnhancedRedditScraper:
    """
    An advanced scraper for extracting content from Reddit subreddits.
    """
    def __init__(self, subreddit, post_limit=25, output_format="csv", 
                 include_comments=False, pages=1, sort_by="hot", 
                 time_filter="all", delay=(1, 3)):
        """
        Initialize the Enhanced Reddit scraper.
        
        Args:
            subreddit (str): Name of the subreddit to scrape
            post_limit (int): Maximum number of posts to scrape
            output_format (str): Format to save data ("csv", "txt", "json")
            include_comments (bool): Whether to scrape comments
            pages (int): Number of pages to scrape
            sort_by (str): How to sort posts ("hot", "new", "top", "rising")
            time_filter (str): Time filter for top posts ("hour", "day", "week", "month", "year", "all")
            delay (tuple): Random delay range between requests in seconds (min, max)
        """
        self.subreddit = subreddit
        self.post_limit = post_limit
        self.output_format = output_format
        self.include_comments = include_comments
        self.pages = pages
        self.sort_by = sort_by
        self.time_filter = time_filter
        self.delay = delay
        
        # Build base URL based on sorting method
        self.base_url = f"https://old.reddit.com/r/{subreddit}/{sort_by}/"
        if sort_by == "top":
            self.base_url += f"?t={time_filter}"
        
        # Set up user agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        
        # Configure logging
        self.setup_logging()
        
    def setup_logging(self):
        """Set up logging configuration"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f"scraper_{self.subreddit}_{timestamp}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_random_headers(self):
        """
        Generate random headers for each request.
        
        Returns:
            dict: HTTP headers
        """
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def get_page(self, url, retries=3):
        """
        Fetch a webpage and return the BeautifulSoup object with retry logic.
        
        Args:
            url (str): URL to fetch
            retries (int): Number of retry attempts
            
        Returns:
            tuple: (BeautifulSoup object, URL after redirect)
        """
        for attempt in range(retries):
            try:
                # Random delay to be respectful
                delay_time = random.uniform(self.delay[0], self.delay[1])
                time.sleep(delay_time)
                
                self.logger.info(f"Fetching {url} (Attempt {attempt+1}/{retries})")
                response = requests.get(url, headers=self.get_random_headers(), timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                return soup, response.url
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching the page (Attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:  # Last attempt
                    return None, url
                time.sleep(2 * (attempt + 1))  # Exponential backoff
        
        return None, url
    
    def extract_posts(self, soup):
        """
        Extract post data from the soup object.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            list: List of dictionaries containing post data
            str: URL for the next page, or None
        """
        posts = []
        next_page_url = None
        
        if soup is None:
            return posts, next_page_url
            
        # Find all post elements
        post_elements = soup.find_all('div', class_='thing')
        
        for post in post_elements:
            if len(posts) >= self.post_limit:
                break
                
            try:
                # Extract post ID
                post_id = post.get('id', '').replace('thing_', '')
                
                # Extract post title
                title_element = post.find('a', class_='title')
                title = title_element.text.strip() if title_element else "No title"
                
                # Extract post URL
                url = title_element['href'] if title_element and 'href' in title_element.attrs else ""
                # Make absolute URL if needed
                if url.startswith('/'):
                    url = urljoin("https://www.reddit.com", url)
                
                # Extract score
                score_element = post.find('div', class_='score unvoted')
                score = score_element.get('title', '0') if score_element else "0"
                
                # Extract author
                author_element = post.find('a', class_='author')
                author = author_element.text.strip() if author_element else "Unknown"
                
                # Extract flair
                flair_element = post.find('span', class_='linkflairlabel')
                flair = flair_element.text.strip() if flair_element else ""
                
                # Extract timestamp
                time_element = post.find('time')
                timestamp = time_element['datetime'] if time_element and 'datetime' in time_element.attrs else ""
                
                # Extract comments count
                comments_element = post.find('a', class_='comments')
                comments_text = comments_element.text.strip() if comments_element else "0 comments"
                comments_count = comments_text.split()[0]
                comments_url = comments_element['href'] if comments_element and 'href' in comments_element.attrs else ""
                
                # Check if this is a self post
                is_self = 'self' in post.get('class', [])
                
                # Extract post content (if it's a self post)
                content = ""
                if is_self and 'expando' in post.get('class', []):
                    content_element = post.find('div', class_='expando')
                    if content_element:
                        content = content_element.text.strip()
                
                # Extract if post is stickied
                is_stickied = 'stickied' in post.get('class', [])
                
                # Check if post has media (image/video)
                has_media = bool(post.find('a', class_='thumbnail') or post.find('div', class_='media-preview'))
                
                # Create a post dictionary
                post_data = {
                    'id': post_id,
                    'title': title,
                    'author': author,
                    'score': score,
                    'comments_count': comments_count.replace('k', '000') if 'k' in comments_count else comments_count,
                    'post_url': url,
                    'comments_url': comments_url,
                    'timestamp': timestamp,
                    'flair': flair,
                    'is_self_post': is_self,
                    'is_stickied': is_stickied,
                    'has_media': has_media,
                    'content': content,
                    'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Add comments if requested
                if self.include_comments and comments_url:
                    post_data['comments'] = self.extract_comments(comments_url)
                
                posts.append(post_data)
                
            except Exception as e:
                self.logger.error(f"Error extracting post data: {e}")
                continue
        
        # Find next page button
        next_button = soup.find('span', class_='next-button')
        if next_button:
            next_link = next_button.find('a')
            if next_link and 'href' in next_link.attrs:
                next_page_url = next_link['href']
                
        return posts, next_page_url
    
    def extract_comments(self, url, depth=1, max_comments=10):
        """
        Extract comments from a post.
        
        Args:
            url (str): URL of the comments page
            depth (int): Current depth level
            max_comments (int): Maximum number of comments to extract
            
        Returns:
            list: List of comment dictionaries
        """
        if depth > 2:  # Limit depth to avoid excessive scraping
            return []
            
        comments = []
        
        try:
            soup, actual_url = self.get_page(url)
            if soup is None:
                return comments
                
            comment_elements = soup.find_all('div', class_='entry')[:max_comments]
            
            for comment in comment_elements:
                try:
                    author_element = comment.find('a', class_='author')
                    author = author_element.text.strip() if author_element else "Unknown"
                    
                    text_element = comment.find('div', class_='md')
                    text = text_element.text.strip() if text_element else ""
                    
                    score_element = comment.find('span', class_='score')
                    score = score_element.text.strip() if score_element else "0 points"
                    
                    time_element = comment.find('time')
                    timestamp = time_element['datetime'] if time_element and 'datetime' in time_element.attrs else ""
                    
                    comment_data = {
                        'author': author,
                        'text': text,
                        'score': score,
                        'timestamp': timestamp
                    }
                    
                    comments.append(comment_data)
                except Exception as e:
                    self.logger.warning(f"Error extracting comment: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error extracting comments from {url}: {e}")
            
        return comments
    
    def save_data(self, posts, filename=None):
        """
        Save the scraped data to a file.
        
        Args:
            posts (list): List of post dictionaries
            filename (str): Output filename (optional)
            
        Returns:
            str: Path to the saved file
        """
        if not posts:
            self.logger.warning("No posts to save.")
            return None
            
        # Create output directory if it doesn't exist
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.subreddit}_{self.sort_by}_{timestamp}"
        
        file_path = os.path.join(output_dir, filename)
        
        if self.output_format == "csv":
            csv_path = f"{file_path}.csv"
            try:
                # Flatten nested comment structures for CSV
                flattened_posts = self._flatten_posts_for_csv(posts)
                
                df = pd.DataFrame(flattened_posts)
                df.to_csv(csv_path, index=False, encoding='utf-8')
                self.logger.info(f"Data saved to {csv_path}")
                return csv_path
            except Exception as e:
                self.logger.error(f"Error saving to CSV: {e}")
                return None
                
        elif self.output_format == "json":
            json_path = f"{file_path}.json"
            try:
                with open(json_path, 'w', encoding='utf-8') as json_file:
                    json.dump(posts, json_file, indent=4, ensure_ascii=False)
                self.logger.info(f"Data saved to {json_path}")
                return json_path
            except Exception as e:
                self.logger.error(f"Error saving to JSON: {e}")
                return None
                
        elif self.output_format == "txt":
            txt_path = f"{file_path}.txt"
            try:
                with open(txt_path, 'w', encoding='utf-8') as txtfile:
                    for post in posts:
                        txtfile.write(f"Title: {post['title']}\n")
                        txtfile.write(f"Author: {post['author']}\n")
                        txtfile.write(f"Score: {post['score']}\n")
                        txtfile.write(f"Comments: {post['comments_count']}\n")
                        txtfile.write(f"Post URL: {post['post_url']}\n")
                        txtfile.write(f"Timestamp: {post['timestamp']}\n")
                        txtfile.write(f"Flair: {post['flair']}\n")
                        txtfile.write(f"Is Self Post: {post['is_self_post']}\n")
                        txtfile.write(f"Is Stickied: {post['is_stickied']}\n")
                        
                        if post['content']:
                            txtfile.write(f"\nContent:\n{post['content']}\n")
                            
                        if self.include_comments and 'comments' in post:
                            txtfile.write("\nComments:\n")
                            for comment in post['comments']:
                                txtfile.write(f"  Author: {comment['author']}\n")
                                txtfile.write(f"  Score: {comment['score']}\n")
                                txtfile.write(f"  Text: {comment['text']}\n")
                                txtfile.write(f"  Time: {comment['timestamp']}\n")
                                txtfile.write("  " + "-" * 40 + "\n")
                                
                        txtfile.write("=" * 80 + "\n\n")
                        
                self.logger.info(f"Data saved to {txt_path}")
                return txt_path
            except Exception as e:
                self.logger.error(f"Error saving to text file: {e}")
                return None
        else:
            self.logger.error(f"Unsupported output format: {self.output_format}")
            return None
    
    def _flatten_posts_for_csv(self, posts):
        """
        Flatten nested structures for CSV output.
        
        Args:
            posts (list): List of post dictionaries
            
        Returns:
            list: Flattened post dictionaries
        """
        flattened = []
        
        for post in posts:
            # Create a copy without comments
            flat_post = {k: v for k, v in post.items() if k != 'comments'}
            
            # If there are comments, create separate entries for summary stats
            if self.include_comments and 'comments' in post and post['comments']:
                flat_post['comment_count_actual'] = len(post['comments'])
                flat_post['top_comment'] = post['comments'][0]['text'] if post['comments'] else ""
                flat_post['top_comment_score'] = post['comments'][0]['score'] if post['comments'] else ""
            
            flattened.append(flat_post)
            
        return flattened
    
    def generate_analytics(self, posts):
     if not posts:
        return {}
        
     try:
        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(posts)
        
        # Convert score to numeric
        df['score_num'] = pd.to_numeric(df['score'], errors='coerce')
        
        # Basic statistics
        analytics = {
            'total_posts': int(len(posts)),
            'unique_authors': int(df['author'].nunique()),
            'average_score': float(df['score_num'].mean()),
            'median_score': float(df['score_num'].median()),
            'max_score': float(df['score_num'].max()),
            'min_score': float(df['score_num'].min()),
            'stickied_posts': int(df['is_stickied'].sum()) if 'is_stickied' in df else 0,
            'self_posts_percentage': float(df['is_self_post'].sum() / len(df) * 100) if 'is_self_post' in df else 0,
            'posts_with_media_percentage': float(df['has_media'].sum() / len(df) * 100) if 'has_media' in df else 0,
            'top_authors': {k: int(v) for k, v in df['author'].value_counts().head(5).to_dict().items()},
            'flair_distribution': {k: int(v) for k, v in df['flair'].value_counts().head(10).to_dict().items()} if 'flair' in df else {},
        }
        
        # Save analytics to file
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        analytics_path = os.path.join(output_dir, f"{self.subreddit}_analytics_{timestamp}.json")
        
        with open(analytics_path, 'w', encoding='utf-8') as f:
            json.dump(analytics, f, indent=4)
            
        self.logger.info(f"Analytics saved to {analytics_path}")
        return analytics
        
     except Exception as e:
        self.logger.error(f"Error generating analytics: {e}")
        return {}
    
    def scrape(self):
        """
        Main scraping function.
        
        Returns:
            list: Scraped post data
        """
        self.logger.info(f"Starting to scrape r/{self.subreddit} (Sort: {self.sort_by}, Pages: {self.pages})")
        
        all_posts = []
        current_url = self.base_url
        page = 1
        
        while page <= self.pages and len(all_posts) < self.post_limit:
            self.logger.info(f"Scraping page {page} of r/{self.subreddit}")
            
            soup, actual_url = self.get_page(current_url)
            if soup is None:
                break
                
            posts, next_page_url = self.extract_posts(soup)
            all_posts.extend(posts[:self.post_limit - len(all_posts)])
            
            self.logger.info(f"Scraped {len(posts)} posts from page {page}")
            
            if not next_page_url or len(all_posts) >= self.post_limit:
                break
                
            current_url = next_page_url
            page += 1
        
        self.logger.info(f"Finished scraping. Total posts: {len(all_posts)}")
        
        return all_posts
    
    def run_full_scrape(self, output_filename=None):
        """
        Runs a complete scrape operation including saving data and generating analytics.
        
        Args:
            output_filename (str): Base filename for outputs
            
        Returns:
            tuple: (saved file path, analytics)
        """
        # Scrape the data
        posts = self.scrape()
        
        # Save the data
        saved_path = self.save_data(posts, output_filename)
        
        # Generate analytics
        analytics = self.generate_analytics(posts)
        
        return saved_path, analytics

def main():
    """
    Main function to run the scraper from command line.
    """
    parser = argparse.ArgumentParser(description='Enhanced Reddit Scraper')
    parser.add_argument('subreddit', type=str, help='Subreddit to scrape')
    parser.add_argument('--limit', type=int, default=25, help='Maximum number of posts to scrape')
    parser.add_argument('--format', type=str, choices=['csv', 'txt', 'json'], default='csv', help='Output format')
    parser.add_argument('--output', type=str, help='Output filename (without extension)')
    parser.add_argument('--comments', action='store_true', help='Include comments')
    parser.add_argument('--pages', type=int, default=1, help='Number of pages to scrape')
    parser.add_argument('--sort', type=str, choices=['hot', 'new', 'top', 'rising'], default='hot', help='Sort method')
    parser.add_argument('--time', type=str, choices=['hour', 'day', 'week', 'month', 'year', 'all'], default='all', help='Time filter for top posts')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests')
    
    args = parser.parse_args()
    
    # Create and run the scraper
    scraper = EnhancedRedditScraper(
        args.subreddit, 
        args.limit, 
        args.format, 
        args.comments, 
        args.pages, 
        args.sort, 
        args.time, 
        (args.delay_min, args.delay_max)
    )
    
    saved_path, analytics = scraper.run_full_scrape(args.output)
    
    if saved_path:
        print(f"\nScraping completed successfully!")
        print(f"Data saved to: {saved_path}")
        
        if analytics:
            print("\nQuick Analytics:")
            print(f"- Total Posts: {analytics['total_posts']}")
            print(f"- Unique Authors: {analytics['unique_authors']}")
            print(f"- Average Score: {analytics['average_score']:.2f}")
            print(f"- Self Posts: {analytics['self_posts_percentage']:.1f}%")
            
            if analytics['top_authors']:
                print("\nTop Contributors:")
                for author, count in list(analytics['top_authors'].items())[:3]:
                    print(f"- {author}: {count} posts")

if __name__ == "__main__":
    main()