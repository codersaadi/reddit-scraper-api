import unittest
import requests
import json
import time
import os
import sys
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_test_logs.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("api_tests")

# API Base URL - Change this to match your deployment
API_BASE_URL = "http://localhost:8000"

class RedditScraperAPITests(unittest.TestCase):
    """Test suite for the Reddit Scraper API"""
    
    def setUp(self):
        """Set up test case"""
        self.task_ids = []  # Store task IDs for cleanup
        
    def tearDown(self):
        """Clean up after test case"""
        # Delete all tasks created during tests
        for task_id in self.task_ids:
            try:
                response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}")
                if response.status_code == 200:
                    logger.info(f"Successfully deleted task {task_id}")
                else:
                    logger.warning(f"Failed to delete task {task_id}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error deleting task {task_id}: {str(e)}")
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = requests.get(f"{API_BASE_URL}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Reddit Scraper API")
        self.assertIn("version", data)
        self.assertIn("endpoints", data)
    
    def test_basic_scrape(self):
        """Test a basic scraping task"""
        payload = {
            "subreddit": "python",
            "post_limit": 5,
            "output_format": "json",
            "include_comments": False,
            "pages": 1,
            "sort_by": "hot",
            "time_filter": "day",
            "delay_min": 1.0,
            "delay_max": 2.0
        }
        
        # Start the task
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["subreddit"], "python")
        
        # Save task ID for cleanup
        task_id = data["task_id"]
        self.task_ids.append(task_id)
        
        # Wait for task to complete (with timeout)
        task_completed = self._wait_for_task_completion(task_id, timeout=60)
        self.assertTrue(task_completed, "Task did not complete within the timeout period")
        
        # Get task status with analytics
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}?include_analytics=true")
        self.assertEqual(response.status_code, 200)
        
        task_data = response.json()
        self.assertEqual(task_data["status"], "completed")
        self.assertIn("output_file", task_data)
        self.assertIn("analytics", task_data)
        
        # Download the result
        response = requests.get(f"{API_BASE_URL}/download/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.content) > 0)
    
    def test_invalid_subreddit(self):
        """Test scraping an invalid subreddit"""
        payload = {
            "subreddit": "this_subreddit_does_not_exist_12345",
            "post_limit": 5,
            "output_format": "json",
            "include_comments": False,
            "pages": 1,
            "sort_by": "hot",
            "time_filter": "day",
            "delay_min": 1.0,
            "delay_max": 2.0
        }
        
        # Start the task
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        task_id = data["task_id"]
        self.task_ids.append(task_id)
        
        # Wait for task to complete
        task_completed = self._wait_for_task_completion(task_id, timeout=30)
        self.assertTrue(task_completed, "Task did not complete within the timeout period")
        
        # Check task status
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
        self.assertEqual(response.status_code, 200)
        
        task_data = response.json()
        # Either task should fail or return empty results
        if task_data["status"] == "failed":
            self.assertIn("error", task_data)
        else:
            self.assertEqual(task_data["status"], "completed")
            self.assertEqual(task_data.get("post_count", 0), 0)
    
    def test_include_comments(self):
        """Test scraping with comments included"""
        payload = {
            "subreddit": "AskReddit",
            "post_limit": 3,
            "output_format": "json",
            "include_comments": True,
            "pages": 1,
            "sort_by": "top",
            "time_filter": "week",
            "delay_min": 1.0,
            "delay_max": 2.0
        }
        
        # Start the task
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        task_id = data["task_id"]
        self.task_ids.append(task_id)
        
        # Wait for task to complete (with timeout)
        task_completed = self._wait_for_task_completion(task_id, timeout=120)  # Longer timeout since comments take time
        self.assertTrue(task_completed, "Task did not complete within the timeout period")
        
        # Download the result
        response = requests.get(f"{API_BASE_URL}/download/{task_id}")
        self.assertEqual(response.status_code, 200)
        
        # Parse the JSON content
        try:
            content = json.loads(response.content)
            self.assertTrue(len(content) > 0)
            
            # Check if comments were included
            if len(content) > 0:
                self.assertIn("comments", content[0], "Comments were not included in the response")
        except json.JSONDecodeError:
            self.fail("Response content is not valid JSON")
    
    def test_all_output_formats(self):
        """Test all output formats (json, csv, txt)"""
        formats = ["json", "csv", "txt"]
        
        for fmt in formats:
            payload = {
                "subreddit": "python",
                "post_limit": 3,
                "output_format": fmt,
                "include_comments": False,
                "pages": 1,
                "sort_by": "hot",
                "time_filter": "day",
                "delay_min": 1.0,
                "delay_max": 2.0
            }
            
            # Start the task
            response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
            self.assertEqual(response.status_code, 202)
            
            data = response.json()
            task_id = data["task_id"]
            self.task_ids.append(task_id)
            
            # Wait for task to complete
            task_completed = self._wait_for_task_completion(task_id, timeout=60)
            self.assertTrue(task_completed, f"Task for {fmt} format did not complete within the timeout period")
            
            # Download the result
            response = requests.get(f"{API_BASE_URL}/download/{task_id}")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(len(response.content) > 0)
            
            # Check file extension
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
            task_data = response.json()
            self.assertTrue(task_data["output_file"].endswith(f".{fmt}"), 
                           f"Output file does not have the correct extension: {task_data['output_file']}")
    
    def test_get_all_tasks(self):
        """Test retrieving all tasks"""
        # Create a task first
        payload = {
            "subreddit": "python",
            "post_limit": 2,
            "output_format": "json",
            "include_comments": False,
            "pages": 1,
            "sort_by": "hot",
            "time_filter": "day",
            "delay_min": 1.0,
            "delay_max": 2.0
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        task_id = data["task_id"]
        self.task_ids.append(task_id)
        
        # Get all tasks
        response = requests.get(f"{API_BASE_URL}/tasks")
        self.assertEqual(response.status_code, 200)
        
        tasks = response.json()
        self.assertIsInstance(tasks, list)
        
        # Check if our task is in the list
        task_ids = [task["task_id"] for task in tasks]
        self.assertIn(task_id, task_ids)
    
    def test_delete_task(self):
        """Test deleting a task"""
        # Create a task first
        payload = {
            "subreddit": "python",
            "post_limit": 2,
            "output_format": "json",
            "include_comments": False,
            "pages": 1,
            "sort_by": "hot",
            "time_filter": "day",
            "delay_min": 1.0,
            "delay_max": 2.0
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        task_id = data["task_id"]
        
        # Wait for task to complete
        task_completed = self._wait_for_task_completion(task_id, timeout=60)
        self.assertTrue(task_completed, "Task did not complete within the timeout period")
        
        # Delete the task
        response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}")
        self.assertEqual(response.status_code, 200)
        
        # Try to get the task (should fail)
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
        self.assertEqual(response.status_code, 404)
        
        # No need to add to self.task_ids since we're deleting it manually
    
    def test_invalid_task_id(self):
        """Test accessing a non-existent task"""
        fake_task_id = "nonexistent-task-id-12345"
        
        # Try to get the task
        response = requests.get(f"{API_BASE_URL}/tasks/{fake_task_id}")
        self.assertEqual(response.status_code, 404)
        
        # Try to download the task
        response = requests.get(f"{API_BASE_URL}/download/{fake_task_id}")
        self.assertEqual(response.status_code, 404)
        
        # Try to delete the task
        response = requests.delete(f"{API_BASE_URL}/tasks/{fake_task_id}")
        self.assertEqual(response.status_code, 404)
    
    def test_validation_errors(self):
        """Test API input validation"""
        # Test invalid subreddit (empty)
        payload = {
            "subreddit": "",
            "post_limit": 5,
            "output_format": "json"
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 422)  # Unprocessable Entity
        
        # Test invalid post limit (too high)
        payload = {
            "subreddit": "python",
            "post_limit": 500,  # Beyond the limit of 100
            "output_format": "json"
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 422)
        
        # Test invalid output format
        payload = {
            "subreddit": "python",
            "post_limit": 5,
            "output_format": "excel"  # Not a valid option
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 422)
        
        # Test invalid delay values
        payload = {
            "subreddit": "python",
            "post_limit": 5,
            "output_format": "json",
            "delay_min": 3.0,
            "delay_max": 1.0  # Max less than min
        }
        
        response = requests.post(f"{API_BASE_URL}/scrape", json=payload)
        self.assertEqual(response.status_code, 422)
    
    def _wait_for_task_completion(self, task_id, timeout=60, check_interval=2):
        """
        Wait for a task to complete with timeout
        
        Args:
            task_id (str): The ID of the task to wait for
            timeout (int): Maximum time to wait in seconds
            check_interval (int): Time between status checks in seconds
            
        Returns:
            bool: True if task completed, False if timed out
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] in ["completed", "failed"]:
                        return True
                    logger.info(f"Task {task_id} status: {data['status']}")
                else:
                    logger.warning(f"Failed to get task status: {response.status_code}")
            except Exception as e:
                logger.error(f"Error checking task status: {str(e)}")
            
            time.sleep(check_interval)
        
        logger.warning(f"Task {task_id} did not complete within {timeout} seconds")
        return False


class LoadTest(unittest.TestCase):
    """Basic load testing for the Reddit Scraper API"""
    
    def setUp(self):
        """Set up test case"""
        self.task_ids = []  # Store task IDs for cleanup
        
    def tearDown(self):
        """Clean up after test case"""
        # Delete all tasks created during tests
        for task_id in self.task_ids:
            try:
                requests.delete(f"{API_BASE_URL}/tasks/{task_id}")
            except:
                pass
    
    def test_concurrent_requests(self):
        """Test submitting multiple requests concurrently"""
        import concurrent.futures
        
        # List of subreddits to scrape
        subreddits = ["python", "programming", "webdev", "datascience", "machinelearning"]
        
        # Base payload
        def get_payload(subreddit):
            return {
                "subreddit": subreddit,
                "post_limit": 5,
                "output_format": "json",
                "include_comments": False,
                "pages": 1,
                "sort_by": "hot",
                "time_filter": "day",
                "delay_min": 1.0,
                "delay_max": 2.0
            }
        
        # Function to submit a task
        def submit_task(subreddit):
            try:
                response = requests.post(f"{API_BASE_URL}/scrape", json=get_payload(subreddit))
                if response.status_code == 202:
                    data = response.json()
                    return data["task_id"]
                else:
                    logger.error(f"Failed to submit task for {subreddit}: {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Error submitting task for {subreddit}: {str(e)}")
                return None
        
        # Submit tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(submit_task, subreddit): subreddit for subreddit in subreddits}
            
            for future in concurrent.futures.as_completed(futures):
                subreddit = futures[future]
                try:
                    task_id = future.result()
                    if task_id:
                        self.task_ids.append(task_id)
                        logger.info(f"Successfully submitted task for {subreddit}: {task_id}")
                except Exception as e:
                    logger.error(f"Exception occurred for {subreddit}: {str(e)}")
        
        # Check if all tasks were submitted
        self.assertEqual(len(self.task_ids), len(subreddits), 
                         "Not all tasks were submitted successfully")
        
        # Wait for all tasks to complete
        completed_tasks = 0
        for task_id in self.task_ids:
            if self._wait_for_task_completion(task_id, timeout=120):
                completed_tasks += 1
        
        logger.info(f"{completed_tasks} out of {len(self.task_ids)} tasks completed successfully")
        
        # Check if at least some tasks completed successfully
        self.assertGreater(completed_tasks, 0, "No tasks completed successfully")
    
    def _wait_for_task_completion(self, task_id, timeout=120, check_interval=5):
        """Wait for a task to complete with timeout"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] in ["completed", "failed"]:
                        return True
                else:
                    logger.warning(f"Failed to get task status: {response.status_code}")
            except Exception as e:
                logger.error(f"Error checking task status: {str(e)}")
            
            time.sleep(check_interval)
        
        return False


if __name__ == "__main__":
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add basic tests
    suite.addTest(unittest.makeSuite(RedditScraperAPITests))
    
    # Add load tests only if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--load-test":
        suite.addTest(unittest.makeSuite(LoadTest))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)