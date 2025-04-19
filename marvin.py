import os
import json
import requests
import logging
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class MarvinDB:
    """
    A class to handle interactions with the CouchDB server for Amazing Marvin data.
    This is part of the Model Context Protocol (MCP) server implementation.
    """
    
    def __init__(self, log_level=None):
        """
        Initialize the MarvinDB with connection details from environment variables.
        
        Args:
            log_level: Optional logging level (e.g., logging.DEBUG, logging.INFO)
        """
        # Set up logger
        self.logger = logging.getLogger('MarvinDB')
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
        self.logger.debug(f"Initialized MarvinDB with database: {self.db_name}")
        
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
            self.logger.info(f"Testing connection to {self.db_url}/{self.db_name}")
            response = self.session.get(self.base_url)
            response.raise_for_status()
            self.logger.info("Database connection successful!")
            self.logger.debug(f"Database info: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error connecting to database: {e}")
            return False

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetch all categories from the CouchDB database.
        
        Categories in Amazing Marvin are like folders that contain projects and tasks.
        By default, only fetches categories that aren't marked as done.
        Manually removes the fieldUpdates field after retrieval.
        
        Returns:
            List[Dict[str, Any]]: A list of category objects
        """
        try:
            # Construct the query to find documents where db field equals "Categories"
            # and either done=false or done field doesn't exist
            query = {
                "selector": {
                    "db": "Categories",
                    "$or": [
                        {"done": False},
                        {"done": {"$exists": False}}
                    ]
                },
            }
            
            # CouchDB's _find endpoint for querying with selectors
            url = f"{self.base_url}/_find"
            
            self.logger.debug(f"Fetching categories with query: {json.dumps(query)}")
            response = self.session.post(url, json=query)
            response.raise_for_status()
            
            result = response.json()
            categories = result.get("docs", [])
            
            # Manually remove fieldUpdates field from each category
            for category in categories:
                if "fieldUpdates" in category:
                    del category["fieldUpdates"]
            
            self.logger.info(f"Successfully fetched {len(categories)} categories")
            self.logger.debug(f"Categories: {json.dumps(categories)}")
            
            return categories
        except Exception as e:
            self.logger.error(f"Error fetching categories: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response content: {e.response.text}")
            raise
            
    def get_tasks(self, parent_id: Optional[str] = None, include_done: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch tasks from the CouchDB database.
        
        If parent_id is provided, only tasks under that parent category/project are returned.
        Otherwise, all tasks are returned. By default, only incomplete tasks are returned,
        including those where the done field doesn't exist.
        Manually removes the fieldUpdates field after retrieval.
        
        Args:
            parent_id (Optional[str]): The ID of the parent category/project
            include_done (bool): Whether to include completed tasks (default: False)
            
        Returns:
            List[Dict[str, Any]]: A list of task objects
        """
        try:
            # Base query to find documents where db field equals "Tasks"
            query = {
                "selector": {
                    "db": "Tasks"
                },
            }
            
            # If we only want incomplete tasks (either done=false or done field doesn't exist)
            if not include_done:
                query["selector"]["$or"] = [
                    {"done": False},
                    {"done": {"$exists": False}}
                ]
                
            # If parent_id is provided, add it to the selector
            if parent_id:
                query["selector"]["parentId"] = parent_id
                self.logger.debug(f"Fetching tasks for parent ID: {parent_id}")
            else:
                self.logger.debug("Fetching all tasks")
            
            # CouchDB's _find endpoint for querying with selectors
            url = f"{self.base_url}/_find"
            
            self.logger.debug(f"Fetching tasks with query: {json.dumps(query)}")
            response = self.session.post(url, json=query)
            response.raise_for_status()
            
            result = response.json()
            tasks = result.get("docs", [])
            
            # Manually remove fieldUpdates field from each task
            for task in tasks:
                if "fieldUpdates" in task:
                    del task["fieldUpdates"]
            
            self.logger.info(f"Successfully fetched {len(tasks)} tasks")
            self.logger.debug(f"First few tasks: {json.dumps(tasks[:3]) if tasks else '[]'}")
            
            return tasks
        except Exception as e:
            self.logger.error(f"Error fetching tasks: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response content: {e.response.text}")
            raise

    def _convert_time_estimate(self, ms):
        if not ms:
            return None
        hours = ms / (1000 * 60 * 60)
        if hours < 1:
            return f"{int(ms / (1000 * 60))}m"
        if hours.is_integer():
            return f"{int(hours)}h"
        return f"{hours:.1f}h"
        
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        res = {"t": task.get("title", "Untitled Task")}
        if task.get("dueDate"): res["due"] = task["dueDate"]
        est = self._convert_time_estimate(task.get("timeEstimate"))
        if est: res["est"] = est
        if task.get("isStarred"): res["pri"] = task.get("isStarred")
        return res

    def _process_category(self, cat: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if cat.get("priority"): data["pri"] = cat["priority"]
        if cat.get("dueDate"): data["due"] = cat["dueDate"]
        return data

    def build_hierarchy_string(self) -> str:
        """
        Build the hierarchical structure of categories and tasks and return as a compact JSON string.
        This does not save to file, just returns the string.
        """
        # Fetch all categories and tasks
        categories = self.get_categories()
        tasks = self.get_tasks(include_done=False)

        # Find root categories (parentId is "root" or missing)
        root_categories = [cat for cat in categories if cat.get("parentId") == "root" or not cat.get("parentId")]
        # Find categories with parentId 'unassigned' (should go under Inbox)
        inbox_categories = [cat for cat in categories if cat.get("parentId") == "unassigned"]
        inbox_tasks = [t for t in tasks if t.get("parentId") == "unassigned"]

        # Build the hierarchy with compact entries
        def process_category_recursive(category: Dict[str, Any]) -> Dict[str, Any]:
            cid = category["_id"]
            cdata = self._process_category(category)
            # Add tasks
            tlist = [self._process_task(t) for t in tasks if t.get("parentId") == cid]
            if tlist:
                cdata["tasks"] = tlist
            # Add subcategories
            subs = [c for c in categories if c.get("parentId") == cid]
            if subs:
                cdata["sub"] = {s.get("title", "Untitled"): process_category_recursive(s) for s in subs}
            return cdata

        hierarchy = {rc.get("title", "Untitled Category"): process_category_recursive(rc) for rc in root_categories}

        # Add synthetic Inbox for categories and tasks with parentId 'unassigned'
        if inbox_categories or inbox_tasks:
            inbox_dict = {}
            if inbox_categories:
                inbox_dict["sub"] = {cat.get("title", "Untitled Category"): process_category_recursive(cat) for cat in inbox_categories}
            if inbox_tasks:
                inbox_dict["tasks"] = [self._process_task(t) for t in inbox_tasks]
            hierarchy["Inbox"] = inbox_dict

        # Compact tasks formatting. Very important for the MCP server.
        json_str = json.dumps(hierarchy, indent=2)
        def compact_tasks(match):
            tasks = json.loads(match.group(2))
            if not tasks:
                return '"tasks": []'
            prefix = match.group(1)
            task_indent = prefix + '  '
            lines = [prefix + '"tasks": [']
            for i, task in enumerate(tasks):
                line = task_indent + json.dumps(task, separators=(',', ':'))
                if i < len(tasks) - 1:
                    line += ','
                lines.append(line)
            lines.append(prefix + ']')
            return '\n'.join(lines)
        pattern = r'^(\s*)"tasks": (\[[\s\S]*?\])'
        json_str = re.sub(pattern, compact_tasks, json_str, flags=re.MULTILINE)
        return json_str

if __name__ == "__main__":
    # Test the MarvinDB class
    try:
        # You can change the log level here to adjust verbosity
        # Options: logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL
        log_level = logging.INFO  # Change this to adjust verbosity
        
        # Configure root logger with command line handler if you want to see all logs
        logging.getLogger().setLevel(log_level)
        
        marvin_db = MarvinDB(log_level=log_level)
        connection_successful = marvin_db.test_connection()
        
        if connection_successful:
            logging.info("Connection test passed.")
            
            # Test getting categories
            try:
                categories = marvin_db.get_categories()
                logging.info(f"Found {len(categories)} categories")
                if categories and log_level == logging.DEBUG:
                    for category in categories[:3]:  # Show first 3 categories in debug mode
                        logging.debug(f"Category: {category.get('title', 'Untitled')}")
            except Exception as e:
                logging.error(f"Error testing get_categories: {e}")
        else:
            logging.warning("Connection test failed.")
    except Exception as e:
        logging.error(f"Error initializing MarvinDB: {e}", exc_info=True)