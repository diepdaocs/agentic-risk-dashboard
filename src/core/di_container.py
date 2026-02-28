from dependency_injector import containers, providers
from src.core.interfaces import IDatabase, IAgentWorkflow
from src.data.sqlite_db import SQLiteDatabase
from src.agents.workflow import LangGraphWorkflow

class Container(containers.DeclarativeContainer):
    """Dependency injection container."""

    config = providers.Configuration()

    # DB configuration
    db = providers.Singleton(
        SQLiteDatabase,
        db_path=config.db_path
    )

    # Workflow configuration
    workflow = providers.Singleton(
        LangGraphWorkflow,
        db=db,
        base_url=config.llm_base_url,
        model_name=config.llm_model_name
    )
