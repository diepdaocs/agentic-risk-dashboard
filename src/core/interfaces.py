from abc import ABC, abstractmethod
from typing import Any, Dict, List

class IDatabase(ABC):
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Executes a SQL query and returns the results."""
        pass

    @abstractmethod
    def get_schema_info(self) -> str:
        """Returns the database schema information."""
        pass

class IAgentWorkflow(ABC):
    @abstractmethod
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Processes a natural language query and returns the dashboard configuration and data."""
        pass
