from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query, Path, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
import os
import uuid
import logging
from datetime import datetime
import asyncio
from enum import Enum
import uvicorn

# Import the existing Reddit scraper
from scraper import EnhancedRedditScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_logs.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("reddit_api")

# Create FastAPI app
app = FastAPI(
    title="Reddit Scraper API",
    description="API for scraping Reddit subreddits and posts",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define enums for validation
class SortType(str, Enum):
    hot = "hot"
    new = "new"
    top = "top"
    rising = "rising"

class TimeFilter(str, Enum):
    hour = "hour"
    day = "day"
    week = "week"
    month = "month"
    year = "year"
    all = "all"

class OutputFormat(str, Enum):
    csv = "csv"
    json = "json"
    txt = "txt"

# Pydantic models for request validation
class ScrapeRequest(BaseModel):
    subreddit: str = Field(..., description="Name of the subreddit to scrape")
    post_limit: int = Field(25, ge=1, le=100, description="Maximum number of posts to scrape")
    output_format: OutputFormat = Field(OutputFormat.json, description="Format to save data")
    include_comments: bool = Field(False, description="Whether to scrape comments")
    pages: int = Field(1, ge=1, le=10, description="Number of pages to scrape")
    sort_by: SortType = Field(SortType.hot, description="How to sort posts")
    time_filter: TimeFilter = Field(TimeFilter.all, description="Time filter for top posts")
    delay_min: float = Field(1.0, ge=0.5, description="Minimum delay between requests")
    delay_max: float = Field(3.0, ge=1.0, description="Maximum delay between requests")

    @validator('delay_max')
    def check_delay_range(cls, v, values):
        if 'delay_min' in values and v < values['delay_min']:
            raise ValueError('maximum delay must be greater than minimum delay')
        return v

class ScrapeResponse(BaseModel):
    task_id: str
    status: str
    subreddit: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    subreddit: str
    start_time: str
    completion_time: Optional[str] = None
    post_count: Optional[int] = None
    output_file: Optional[str] = None
    error: Optional[str] = None

# Store for background tasks
task_store = {}

# Function to run the scraper in the background
async def run_scraper_task(task_id: str, subreddit: str, post_limit: int, output_format: str,
                          include_comments: bool, pages: int, sort_by: str, time_filter: str,
                          delay_min: float, delay_max: float):
    """Run the scraper in the background and update the task status."""
    try:
        task_store[task_id]["status"] = "running"
        
        # Create a unique filename for this task
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{subreddit}_{sort_by}_{task_id}_{timestamp}"
        
        # Run the scraper (this is synchronous but we're running it in a background task)
        scraper = EnhancedRedditScraper(
            subreddit=subreddit,
            post_limit=post_limit,
            output_format=output_format,
            include_comments=include_comments,
            pages=pages,
            sort_by=sort_by,
            time_filter=time_filter,
            delay=(delay_min, delay_max)
        )
        
        saved_path, analytics = scraper.run_full_scrape(filename)
        
        if saved_path:
            task_store[task_id].update({
                "status": "completed",
                "completion_time": datetime.now().isoformat(),
                "post_count": analytics.get('total_posts', 0),
                "output_file": os.path.basename(saved_path),
                "analytics": analytics
            })
        else:
            task_store[task_id].update({
                "status": "failed",
                "completion_time": datetime.now().isoformat(),
                "error": "Failed to save results"
            })
            
    except Exception as e:
        logger.error(f"Error in task {task_id}: {str(e)}")
        task_store[task_id].update({
            "status": "failed",
            "completion_time": datetime.now().isoformat(),
            "error": str(e)
        })

# API endpoints
@app.post("/scrape", response_model=ScrapeResponse, status_code=status.HTTP_202_ACCEPTED)
async def scrape_subreddit(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new scraping task for a subreddit.
    
    This endpoint runs the scraper in the background and returns a task ID
    that can be used to check the status of the scraping task.
    """
    task_id = str(uuid.uuid4())
    
    # Create a new task entry
    task_store[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "subreddit": request.subreddit,
        "start_time": datetime.now().isoformat(),
        "parameters": request.dict()
    }
    
    # Add the task to the background tasks
    background_tasks.add_task(
        run_scraper_task,
        task_id,
        request.subreddit,
        request.post_limit,
        request.output_format,
        request.include_comments,
        request.pages,
        request.sort_by,
        request.time_filter,
        request.delay_min,
        request.delay_max
    )
    
    return ScrapeResponse(
        task_id=task_id,
        status="pending",
        subreddit=request.subreddit,
        message="Scraping task started"
    )

@app.get("/tasks", response_model=List[TaskStatus])
async def get_all_tasks():
    """
    Get a list of all tasks and their statuses.
    """
    return [TaskStatus(**{k: v for k, v in task.items() if k != "parameters" and k != "analytics"}) 
            for task in task_store.values()]

@app.get("/tasks/{task_id}", response_model=Union[TaskStatus, Dict[str, Any]])
async def get_task_status(
    task_id: str = Path(..., description="The ID of the task to check"),
    include_analytics: bool = Query(False, description="Include analytics in the response")
):
    """
    Get the status of a specific task.
    
    Optionally include analytics data if the task has completed.
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    if include_analytics and task.get("status") == "completed" and "analytics" in task:
        return task
    else:
        return TaskStatus(**{k: v for k, v in task.items() if k != "parameters" and k != "analytics"})

@app.get("/download/{task_id}")
async def download_result(task_id: str = Path(..., description="The ID of the task to download")):
    """
    Download the result file for a completed task.
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    if "output_file" not in task:
        raise HTTPException(status_code=404, detail="Output file not found")
    
    file_path = os.path.join("output", task["output_file"])
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path, 
        filename=task["output_file"],
        media_type="application/octet-stream"
    )

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str = Path(..., description="The ID of the task to delete")):
    """
    Delete a task and its associated data.
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    # Delete the output file if it exists
    if "output_file" in task:
        file_path = os.path.join("output", task["output_file"])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
    
    # Remove the task from the store
    del task_store[task_id]
    
    return {"message": "Task deleted successfully"}

@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Reddit Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "/scrape": "Start a new scraping task",
            "/tasks": "Get all tasks",
            "/tasks/{task_id}": "Get task status",
            "/download/{task_id}": "Download task results",
            "/docs": "API documentation"
        }
    }

if __name__ == "__main__":
    # Make sure output directory exists
    os.makedirs("output", exist_ok=True)
    
    # Start the server
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)