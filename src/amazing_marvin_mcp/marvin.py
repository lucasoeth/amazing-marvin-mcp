import os
import json
import requests
import logging
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class MarvinAPI:
    """
    A class to handle interactions with the CouchDB server for Amazing Marvin data.
    This class provides raw API access to the Amazing Marvin database.
    """

    def __init__(self, log_level=None):
        """
        Initialize the MarvinAPI with connection details from environment variables.

        Args:
            log_level: Optional logging level (e.g., logging.DEBUG, logging.INFO)
        """
        # Set up logger
        self.logger = logging.getLogger('MarvinAPI')
        if log_level is not None:
            self.logger.setLevel(log_level)

        # Load environment variables
        load_dotenv()

        # Get database connection details from environment variables
        self.db_name = os.environ.get("DB_NAME")
        self.db_url = os.environ.get("DB_URL")
        self.db_username = os.environ.get("DB_USERNAME")
        self.db_password = os.environ.get("DB_PASSWORD")

        # Check if all required environment variables are available
        self._validate_env_vars()

        # Create the base URL for CouchDB requests
        self.base_url = f"{self.db_url}/{self.db_name}"

        # Initialize the session with auth credentials
        self.session = requests.Session()
        self.session.auth = (self.db_username, self.db_password)
        self.logger.debug(
            f"Initialized MarvinAPI with database: {self.db_name}")

        # Initialize caches and sequence tracking
        self._categories_cache = None
        self._categories_last_seq = '0'
        self._tasks_cache = None
        self._tasks_last_seq = '0'

    def _validate_env_vars(self):
        """Validate that all required environment variables are set."""
        missing_vars = []
        if not self.db_name:
            missing_vars.append("DB_NAME")
        if not self.db_url:
            missing_vars.append("DB_URL")
        if not self.db_username:
            missing_vars.append("DB_USERNAME")
        if not self.db_password:
            missing_vars.append("DB_PASSWORD")

        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    def test_connection(self) -> bool:
        """
        Test the connection to the CouchDB server.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            # Try to get the database info
            self.logger.info(
                f"Testing connection to {self.db_url}/{self.db_name}")
            response = self.session.get(self.base_url)
            response.raise_for_status()
            self.logger.info("Database connection successful!")
            self.logger.debug(f"Database info: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error connecting to database: {e}")
            return False

    def _check_changes(self, last_seq: str, selector: Dict[str, Any]) -> Optional[str]:
        """
        Check the _changes feed for documents matching the selector since last_seq.
        Returns new last_seq if changes found, or None if no changes.
        """
        url = f"{self.base_url}/_changes"
        params = {
            'feed': 'normal',
            'filter': '_selector',
            'include_docs': 'false',
            'since': last_seq
        }
        try:
            self.logger.debug(
                f"Checking changes since {last_seq} with selector: {json.dumps(selector)}")
            response = self.session.post(
                url, params=params, json={'selector': selector})
            response.raise_for_status()
            changes = response.json()
            new_last_seq = str(changes.get('last_seq'))
            if not changes.get('results'):
                self.logger.debug(
                    f"No relevant changes found since {last_seq}. Current seq: {new_last_seq}")
                return new_last_seq if last_seq == '0' else None
            else:
                self.logger.debug(
                    f"Changes found since {last_seq}. New seq: {new_last_seq}")
                return new_last_seq
        except Exception as e:
            self.logger.error(f"Error checking changes feed: {e}")
            raise

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetch all categories from the CouchDB database, using a cache invalidated by the _changes feed.
        
        Returns:
            List of category/project documents
        """
        category_selector = {
            "db": "Categories",
            "$or": [
                {"done": False},
                {"done": {"$exists": False}}
            ]
        }
        try:
            new_seq = self._check_changes(
                self._categories_last_seq, category_selector)
            if new_seq is None and self._categories_cache is not None:
                self.logger.info(
                    "Returning cached categories (no changes detected).")
                return self._categories_cache

            self.logger.info(
                "Fetching fresh categories (changes detected or cache empty).")
            url = f"{self.base_url}/_find"
            query = {"selector": category_selector}
            self.logger.debug(
                f"Fetching categories with query: {json.dumps(query)}")
            response = self.session.post(url, json=query)
            response.raise_for_status()
            result = response.json()
            categories = result.get("docs", [])
            for category in categories:
                if "fieldUpdates" in category:
                    del category["fieldUpdates"]
            self.logger.info(
                f"Successfully fetched {len(categories)} categories")
            self._categories_cache = categories
            if new_seq is None:
                current_seq = self._check_changes('0', category_selector)
                self._categories_last_seq = current_seq or self._categories_last_seq
            else:
                self._categories_last_seq = new_seq
            return categories
        except Exception as e:
            self.logger.error(f"Error fetching categories: {str(e)}")
            self._categories_cache = None
            self._categories_last_seq = '0'
            raise

    def get_tasks(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch incomplete tasks from the CouchDB database, using a cache for all tasks (when parent_id is None),
        invalidated by the _changes feed.
        
        Args:
            parent_id: Optional ID of the parent project to filter tasks
            
        Returns:
            List of task documents
        """
        if parent_id:
            self.logger.info(
                f"Fetching tasks for specific parent {parent_id}, bypassing cache.")
            try:
                query = {
                    "selector": {
                        "db": "Tasks",
                        "parentId": parent_id,
                        "$or": [
                            {"done": False},
                            {"done": {"$exists": False}}
                        ]
                    }
                }
                url = f"{self.base_url}/_find"
                self.logger.debug(
                    f"Fetching tasks for parent {parent_id} with query: {json.dumps(query)}")
                response = self.session.post(url, json=query)
                response.raise_for_status()
                result = response.json()
                tasks = result.get("docs", [])
                for task in tasks:
                    if "fieldUpdates" in task:
                        del task["fieldUpdates"]
                self.logger.info(
                    f"Successfully fetched {len(tasks)} tasks for parent {parent_id}")
                return tasks
            except Exception as e:
                self.logger.error(
                    f"Error fetching tasks for parent {parent_id}: {str(e)}")
                raise

        # Always fetch only incomplete tasks
        task_selector = {
            "db": "Tasks",
            "$or": [
                {"done": False},
                {"done": {"$exists": False}}
            ]
        }
        try:
            new_seq = self._check_changes(self._tasks_last_seq, task_selector)
            if new_seq is None and self._tasks_cache is not None:
                self.logger.info(
                    "Returning cached tasks (no changes detected).")
                return self._tasks_cache

            self.logger.info(
                "Fetching fresh tasks (changes detected or cache empty).")
            url = f"{self.base_url}/_find"
            query = {"selector": task_selector}
            self.logger.debug(
                f"Fetching all tasks with query: {json.dumps(query)}")
            response = self.session.post(url, json=query)
            response.raise_for_status()
            result = response.json()
            tasks = result.get("docs", [])
            for task in tasks:
                if "fieldUpdates" in task:
                    del task["fieldUpdates"]
            self.logger.info(f"Successfully fetched {len(tasks)} tasks.")
            self._tasks_cache = tasks
            if new_seq is None:
                current_seq = self._check_changes('0', task_selector)
                self._tasks_last_seq = current_seq or self._tasks_last_seq
            else:
                self._tasks_last_seq = new_seq
            return tasks
        except Exception as e:
            self.logger.error(f"Error fetching tasks: {str(e)}")
            self._tasks_cache = None
            self._tasks_last_seq = '0'
            raise

    def create_task(self, title: str, parent_id: str = "unassigned", day: Optional[str] = None,
                    due_date: Optional[str] = None, time_estimate: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a new task directly in the CouchDB database.
        
        Args:
            title: The title of the task
            parent_id: ID of the parent project
            day: Optional day for the task (YYYY-MM-DD)
            due_date: Optional due date for the task (YYYY-MM-DD)
            time_estimate: Optional time estimate in milliseconds
            
        Returns:
            The created task document
        """
        self.logger.info(f"Creating new task: {title}")

        current_time = int(time.time())

        # Fetch all tasks to determine rank/masterRank
        all_tasks = self.get_tasks()
        # rank: max rank among all tasks + 1
        max_rank = max((t.get("rank", 0) for t in all_tasks if isinstance(
            t.get("rank", 0), (int, float))), default=0)
        new_rank = max_rank + 1

        # masterRank: max masterRank among tasks in the same parent + 1
        parent_tasks = [t for t in all_tasks if t.get("parentId") == parent_id]
        max_master_rank = max((t.get("masterRank", 0) for t in parent_tasks if isinstance(
            t.get("masterRank", 0), (int, float))), default=0)
        new_master_rank = max_master_rank + 1

        # Create the task document
        task = {
            "db": "Tasks",
            "title": title,
            "parentId": parent_id,
            "createdAt": current_time,
            "updatedAt": current_time,
            "rank": new_rank,
            "masterRank": new_master_rank
        }

        # Add optional fields
        if day:
            task["day"] = day
        else:
            task["day"] = "unassigned"
        if due_date:
            task["dueDate"] = due_date
        if time_estimate:
            task["timeEstimate"] = time_estimate

        task["fieldUpdates"] = {}

        # Insert the document into CouchDB
        try:
            response = self.session.post(self.base_url, json=task)
            response.raise_for_status()
            self.logger.info(f"Successfully created task: {title}")
            return response.json()
        except Exception as e:
            self.logger.error(f"Error creating task: {str(e)}")
            raise

    def create_project(self, title: str, parent_id: str = "unassigned",
                       due_date: Optional[str] = None, priority: Optional[str] = None,
                       ) -> Dict[str, Any]:
        """
        Create a new project directly in the CouchDB database.
        
        Args:
            title: The title of the project
            parent_id: ID of the parent project
            due_date: Optional due date for the project (YYYY-MM-DD)
            priority: Optional priority level
            
        Returns:
            The created project document
        """
        self.logger.info(f"Creating new project: {title}")

        current_time = int(time.time())

        # Fetch all categories to determine rank/masterRank
        all_categories = self.get_categories()
        # rank: max rank among all categories + 1
        max_rank = max(
            (c.get("rank", 0) for c in all_categories if isinstance(
                c.get("rank", 0), (int, float))),
            default=0
        )
        new_rank = max_rank + 1

        # masterRank: max masterRank among categories in the same parent + 1
        parent_categories = [c for c in all_categories if c.get("parentId") == parent_id]
        max_master_rank = max(
            (c.get("masterRank", 0) for c in parent_categories if isinstance(
                c.get("masterRank", 0), (int, float))),
            default=0
        )
        new_master_rank = max_master_rank + 1

        # Create the project document
        project = {
            "db": "Categories",
            "type": "project",
            "title": title,
            "parentId": parent_id,
            "createdAt": current_time,
            "updatedAt": current_time,
            "rank": new_rank,
            "masterRank": new_master_rank
        }

        # Add optional fields
        if due_date:
            project["dueDate"] = due_date
        if priority:
            project["priority"] = priority

        # Insert the document into CouchDB
        try:
            response = self.session.post(self.base_url, json=project)
            response.raise_for_status()
            self.logger.info(f"Successfully created project: {title}")
            return response.json()
        except Exception as e:
            self.logger.error(f"Error creating project: {str(e)}")
            raise
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing task directly in the CouchDB database.
        
        Args:
            task_id: The ID of the task to update
            updates: Dictionary of fields to update and their new values
            
        Returns:
            The updated task document
        """
        self.logger.info(f"Updating task with ID: {task_id}")
        
        # First, get the current task document to ensure we have the latest revision
        try:
            url = f"{self.base_url}/{task_id}"
            response = self.session.get(url)
            response.raise_for_status()
            task = response.json()
            
            # Update the updatedAt timestamp
            current_time = int(time.time() * 1000)
            task["updatedAt"] = current_time
            
            # Apply the updates
            for key, value in updates.items():
                task[key] = value
                
                if "fieldUpdates" not in task:
                    task["fieldUpdates"] = {}
                task["fieldUpdates"][key] = current_time
            
            # Update the document in CouchDB
            response = self.session.put(url, json=task)
            response.raise_for_status()
            
            self.logger.info(f"Successfully updated task {task_id}")
            return task
            
        except Exception as e:
            self.logger.error(f"Error updating task {task_id}: {str(e)}")
            raise