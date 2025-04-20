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

class MarvinAPI:
    """
    A class to handle interactions with the CouchDB server for Amazing Marvin data.
    This is part of the Model Context Protocol (MCP) server implementation.
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
        self.logger.debug(f"Initialized MarvinAPI with database: {self.db_name}")
        
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
            self.logger.info(f"Testing connection to {self.db_url}/{self.db_name}")
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
            self.logger.debug(f"Checking changes since {last_seq} with selector: {json.dumps(selector)}")
            response = self.session.post(url, params=params, json={'selector': selector})
            response.raise_for_status()
            changes = response.json()
            new_last_seq = str(changes.get('last_seq'))
            if not changes.get('results'):
                self.logger.debug(f"No relevant changes found since {last_seq}. Current seq: {new_last_seq}")
                return new_last_seq if last_seq == '0' else None
            else:
                self.logger.debug(f"Changes found since {last_seq}. New seq: {new_last_seq}")
                return new_last_seq
        except Exception as e:
            self.logger.error(f"Error checking changes feed: {e}")
            raise

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetch all categories from the CouchDB database, using a cache invalidated by the _changes feed.
        """
        category_selector = {
            "db": "Categories",
            "$or": [
                {"done": False},
                {"done": {"$exists": False}}
            ]
        }
        try:
            new_seq = self._check_changes(self._categories_last_seq, category_selector)
            if new_seq is None and self._categories_cache is not None:
                self.logger.info("Returning cached categories (no changes detected).")
                return self._categories_cache

            self.logger.info("Fetching fresh categories (changes detected or cache empty).")
            url = f"{self.base_url}/_find"
            query = {"selector": category_selector}
            self.logger.debug(f"Fetching categories with query: {json.dumps(query)}")
            response = self.session.post(url, json=query)
            response.raise_for_status()
            result = response.json()
            categories = result.get("docs", [])
            for category in categories:
                if "fieldUpdates" in category:
                    del category["fieldUpdates"]
            self.logger.info(f"Successfully fetched {len(categories)} categories")
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
        """
        if parent_id:
            self.logger.info(f"Fetching tasks for specific parent {parent_id}, bypassing cache.")
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
                self.logger.debug(f"Fetching tasks for parent {parent_id} with query: {json.dumps(query)}")
                response = self.session.post(url, json=query)
                response.raise_for_status()
                result = response.json()
                tasks = result.get("docs", [])
                for task in tasks:
                    if "fieldUpdates" in task: del task["fieldUpdates"]
                self.logger.info(f"Successfully fetched {len(tasks)} tasks for parent {parent_id}")
                return tasks
            except Exception as e:
                self.logger.error(f"Error fetching tasks for parent {parent_id}: {str(e)}")
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
                self.logger.info("Returning cached tasks (no changes detected).")
                return self._tasks_cache

            self.logger.info("Fetching fresh tasks (changes detected or cache empty).")
            url = f"{self.base_url}/_find"
            query = {"selector": task_selector}
            self.logger.debug(f"Fetching all tasks with query: {json.dumps(query)}")
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
        tasks = self.get_tasks()

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