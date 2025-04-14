#!/usr/bin/env python3
"""
MCP Coco Database Server

This server provides Model Context Protocol (MCP) access to the Coco database,
allowing language models to execute both standard SQL and semantic vector queries.
It uses the Coco SDK for embedding generation and integrates with a PostgreSQL
database that has pgvector extension.
"""

import sys
import os
import json
import asyncio
import logging
import logging.config
import logging.handlers
import signal
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
import numpy as np

# FastMCP for the server implementation
from mcp.server.fastmcp import FastMCP, Context

# PostgreSQL async driver
import asyncpg

# Import Coco SDK components (will be available when the SDK is mounted)
from coco.lm import LanguageModelClient

# Define log directory
LOG_DIR = "/logs"
LOG_FILE = os.path.join(LOG_DIR, "mcp_server.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Logging configuration dictionary
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(process)d %(thread)d %(pathname)s %(lineno)d %(funcName)s %(message)s",
            "datefmt": "iso8601",  # Use ISO 8601 format for timestamps
        },
    },
    "handlers": {
        "stderr": {
            "class": "logging.StreamHandler",
            "level": "INFO",  # Or 'ERROR' if you want less noise on stderr
            "formatter": "simple",
            "stream": sys.stderr,  # Explicitly use stderr
        },
        "timed_rotating_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "INFO",  # Capture INFO and above in the file
            "formatter": "json",
            "filename": LOG_FILE,
            "when": "H",  # Rotate hourly
            "interval": 1,
            "backupCount": 24 * 7,  # Keep logs for 7 days
            "encoding": "utf-8",
            "delay": False,
            "utc": True,  # Use UTC for timestamps in filenames
        },
    },
    "loggers": {
        # Set level for specific noisy loggers if needed, e.g.:
        # 'asyncpg': {
        #     'level': 'WARNING',
        #     'handlers': ['stderr', 'timed_rotating_file'],
        #     'propagate': False,
        # },
    },
    "root": {
        "level": "INFO",  # Set root level to INFO
        "handlers": ["stderr", "timed_rotating_file"],
    },
}

# Apply the logging configuration
logging.config.dictConfig(LOGGING_CONFIG)

# Get the root logger
logger = logging.getLogger(__name__)

# Global variable to track server state
shutdown_event = asyncio.Event()


# Signal handler for graceful shutdown
def handle_terminate(sig, frame):
    """Handle termination signals by setting the shutdown event."""
    # logger.error(f"Received signal {sig}, initiating shutdown...") # Old logging
    logger.info(
        f"Received signal {sig}, initiating shutdown...",
        extra={"event_type": "shutdown_signal", "signal": sig},
    )
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGTERM, handle_terminate)
signal.signal(signal.SIGINT, handle_terminate)

# Main server instance
mcp = None  # Will be initialized in lifespan manager


@asynccontextmanager
async def db_lifespan(server: FastMCP):
    """
    Lifespan manager for the MCP server.

    This sets up database connections and Coco clients on server startup
    and cleans up resources on shutdown.
    """
    # Read required environment variables
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # logger.error("DATABASE_URL environment variable is not set") # Old logging
        logger.critical(
            "DATABASE_URL environment variable is not set",
            extra={"event_type": "config_error", "variable": "DATABASE_URL"},
        )
        sys.exit(1)

    # Read Coco SDK configuration variables
    ollama_base_url = os.getenv("COCO_OLLAMA_URL_BASE")
    openai_base_url = os.getenv("COCO_OPENAI_URL_BASE")
    embedding_api = os.getenv("COCO_EMBEDDING_API")
    llm_api = os.getenv("COCO_LLM_API")
    embedding_model = os.getenv("COCO_EMBEDDING_MODEL")

    # Validate configuration
    if embedding_api not in ["ollama", "openai"]:
        # logger.error(f"Invalid COCO_EMBEDDING_API: {embedding_api}. Must be 'ollama' or 'openai'") # Old logging
        logger.critical(
            f"Invalid COCO_EMBEDDING_API: {embedding_api}",
            extra={
                "event_type": "config_error",
                "variable": "COCO_EMBEDDING_API",
                "value": embedding_api,
                "allowed_values": ["ollama", "openai"],
            },
        )
        sys.exit(1)

    if embedding_api == "openai" and not os.getenv("OPENAI_API_KEY"):
        # logger.error("OPENAI_API_KEY environment variable is required when COCO_EMBEDDING_API=openai") # Old logging
        logger.critical(
            "OPENAI_API_KEY environment variable is required when COCO_EMBEDDING_API=openai",
            extra={
                "event_type": "config_error",
                "variable": "OPENAI_API_KEY",
                "condition": "COCO_EMBEDDING_API=openai",
            },
        )
        sys.exit(1)

    # Create a watchdog task to check for parent process
    parent_pid = os.getppid()

    async def check_parent_process():
        """Check if parent process is still running, if not trigger shutdown"""
        while not shutdown_event.is_set():
            try:
                # Try to get parent process info - will raise if parent is gone
                os.kill(parent_pid, 0)  # This doesn't actually send a signal
                await asyncio.sleep(5)  # Check every 5 seconds
            except OSError:
                # Parent process is gone
                # logger.error("Parent process is no longer running, initiating shutdown...") # Old logging
                logger.info(
                    "Parent process is no longer running, initiating shutdown...",
                    extra={"event_type": "parent_process_exit"},
                )
                shutdown_event.set()
                break

    # Start the watchdog task
    watchdog_task = asyncio.create_task(check_parent_process())

    # Resources to be cleaned up
    pool = None

    try:
        # Initialize database connection pool
        # logger.error(f"Connecting to database: {database_url.split('@')[-1]}") # Old logging
        logger.info(
            f"Attempting to connect to database pool: {database_url.split('@')[-1]}",
            extra={"event_type": "db_pool_init_start"},
        )
        pool = await asyncpg.create_pool(database_url)
        logger.info(
            f"Successfully connected to database pool: {database_url.split('@')[-1]}",
            extra={"event_type": "db_pool_init_success"},
        )

        # Initialize Coco language model client for embeddings
        # logger.error(f"Initializing Coco LanguageModelClient with {embedding_api} for embeddings") # Old logging
        logger.info(
            f"Initializing Coco LanguageModelClient",
            extra={
                "event_type": "coco_client_init_start",
                "embedding_api": embedding_api,
                "llm_api": llm_api,
            },
        )
        coco_client = LanguageModelClient(
            ollama_base_url=ollama_base_url,
            openai_base_url=openai_base_url,
            embedding_api=embedding_api,
            llm_api=llm_api,
        )

        # Yield the context with both resources
        yield {
            "db_pool": pool,
            "coco_client": coco_client,
            "embedding_model": embedding_model,
        }

        # After the context manager exits, wait for shutdown signal if needed
        if not shutdown_event.is_set():
            try:
                # Wait for shutdown signal with a timeout
                # logger.error("Waiting for clean shutdown signal...") # Old logging
                logger.info(
                    "Server running, waiting for shutdown signal...",
                    extra={"event_type": "waiting_for_shutdown"},
                )
                await asyncio.wait_for(shutdown_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # logger.error("Timeout waiting for shutdown signal, proceeding with cleanup") # Old logging
                logger.warning(
                    "Timeout waiting for shutdown signal, proceeding with cleanup anyway",
                    extra={"event_type": "shutdown_timeout"},
                )

    except Exception as e:
        # logger.error(f"Error during startup: {e}") # Old logging
        logger.critical(
            f"Fatal error during server startup: {e}",
            exc_info=True,
            extra={
                "event_type": "startup_error",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise
    finally:
        # Clean up resources
        # logger.error("Shutting down MCP server, cleaning up resources") # Old logging
        logger.info(
            "Shutting down MCP server, cleaning up resources...",
            extra={"event_type": "shutdown_start"},
        )

        # Cancel the watchdog task
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass

        # Close the database pool if it was created
        if pool is not None:
            # logger.error("Closing database connection pool") # Old logging
            logger.info(
                "Closing database connection pool...",
                extra={"event_type": "db_pool_close_start"},
            )
            await pool.close()
            logger.info(
                "Database connection pool closed.",
                extra={"event_type": "db_pool_close_success"},
            )

        # logger.error("Cleanup complete, server shutting down") # Old logging
        logger.info(
            "Resource cleanup complete. Server shut down.",
            extra={"event_type": "shutdown_complete"},
        )


# Initialize the FastMCP server with the lifespan manager
mcp = FastMCP("coco-db-mcp-server", lifespan=db_lifespan)

# Create a global reference for database URL
DATABASE_URL = os.getenv("DATABASE_URL")


@mcp.resource("coco_db://schema/{table_name}")
async def get_table_schema(table_name: str) -> str:
    """
    Resource handler that returns the schema information for a given table.

    Args:
        table_name: The name of the table to get schema information for

    Returns:
        JSON string containing column names and data types
    """
    start_time = asyncio.get_event_loop().time()
    resource_uri = f"coco_db://schema/{table_name}"
    logger.info(
        "Starting resource call",
        extra={
            "event_type": "resource_call_start",
            "resource_uri": resource_uri,
            "table_name": table_name,
        },
    )

    conn = None  # Initialize conn to None
    try:
        # Create a direct database connection for this request
        logger.info(
            "Attempting direct database connection",
            extra={
                "event_type": "db_direct_connect_start",
                "resource_uri": resource_uri,
                "database_url": DATABASE_URL.split("@")[
                    -1
                ],  # Log target db without credentials
            },
        )
        conn = await asyncpg.connect(DATABASE_URL)
        logger.info(
            "Successfully established direct database connection",
            extra={
                "event_type": "db_direct_connect_success",
                "resource_uri": resource_uri,
            },
        )

        # Execute query to get column information
        query = """
            SELECT column_name, data_type, is_nullable, 
                   column_default, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = $1 AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        logger.info(
            "Executing schema query",
            extra={
                "event_type": "db_query_start",
                "query_type": "schema",
                "resource_uri": resource_uri,
                "table_name": table_name,
                "sql": query.strip(),  # Log the query itself
            },
        )
        results = await conn.fetch(query, table_name)

        if not results:
            # Table doesn't exist or has no columns
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.warning(
                f"Schema information not found for table '{table_name}'",
                extra={
                    "event_type": "schema_not_found",
                    "resource_uri": resource_uri,
                    "table_name": table_name,
                    "duration_ms": duration_ms,
                },
            )
            return json.dumps(
                {
                    "error": f"Table '{table_name}' not found or has no columns",
                    "columns": [],
                },
                indent=2,
            )

        # Format the results as a more readable dictionary
        columns = []
        for row in results:
            column_info = {
                "name": row["column_name"],
                "data_type": row["data_type"],
                "is_nullable": row["is_nullable"],
                "default": row["column_default"],
            }

            # Only include maximum length for character types
            if row["character_maximum_length"] is not None:
                column_info["max_length"] = row["character_maximum_length"]

            columns.append(column_info)

        # Successful completion
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(
            "Resource call successful",
            extra={
                "event_type": "resource_call_success",
                "resource_uri": resource_uri,
                "table_name": table_name,
                "column_count": len(columns),
                "duration_ms": duration_ms,
            },
        )

        # Return the formatted schema information
        return json.dumps({"table_name": table_name, "columns": columns}, indent=2)

    except Exception as e:
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.error(
            "Resource call failed",
            exc_info=True,
            extra={
                "event_type": "resource_call_error",
                "resource_uri": resource_uri,
                "table_name": table_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": duration_ms,
            },
        )
        # Ensure connection is closed even if error happened before inner finally
        if conn and not conn.is_closed():
            try:
                await conn.close()
                logger.info(
                    "Direct database connection closed after error",
                    extra={
                        "event_type": "db_direct_close_on_error",
                        "resource_uri": resource_uri,
                    },
                )
            except Exception as close_err:
                logger.error(
                    "Failed to close database connection after error",
                    exc_info=True,
                    extra={
                        "event_type": "db_direct_close_failure",
                        "resource_uri": resource_uri,
                        "original_error_type": type(e).__name__,
                        "close_error_type": type(close_err).__name__,
                        "close_error_message": str(close_err),
                    },
                )
        return json.dumps(
            {
                "error": f"Failed to get schema for table '{table_name}': {str(e)}",
                "columns": [],
            },
            indent=2,
        )
    finally:
        # Ensure connection is closed in the normal path
        if conn and not conn.is_closed():
            await conn.close()
            logger.info(
                "Direct database connection closed",
                extra={"event_type": "db_direct_close", "resource_uri": resource_uri},
            )


@mcp.tool(
    name="execute_pgvector_query",
    description="""Executes a read-only SQL query against a PostgreSQL database with pgvector extension.

For vector similarity searches:
1. Use $1 as the placeholder for the embedding vector when providing 'semantic_string'
2. For cosine similarity searches, use the correct syntax: 'embedding <=> $1::vector'
3. For Euclidean distance searches, use: 'embedding <-> $1::vector'
4. For inner product similarity, use: 'embedding <#> $1::vector'

Examples:
- "SELECT * FROM documents ORDER BY embedding <=> $1::vector LIMIT 5;"
- "SELECT *, embedding <-> $1::vector AS distance FROM documents WHERE category = 'books' ORDER BY distance LIMIT 10;"

Notes:
- The embedding vector will be automatically generated from your 'semantic_string'
- Always use cast to vector with $1::vector syntax (not vector($1))
- The table 'documents' has columns: id, text, filename, date_time, embedding
""",
)
async def execute_pgvector_query(
    sql_query: str, ctx: Context, semantic_string: Optional[str] = None
) -> str:
    """
    Execute a SQL query against the PostgreSQL database, optionally with vector similarity.

    Args:
        sql_query: The SQL query to execute. Use $1 as placeholder for embedding vector.
        ctx: The MCP request context containing the lifespan context.
        semantic_string: Optional text to embed for vector similarity search.

    Returns:
        JSON string containing the query results.
    """
    start_time = asyncio.get_event_loop().time()
    tool_name = "execute_pgvector_query"
    tool_input = {
        "sql_query": sql_query,
        "semantic_string_present": bool(semantic_string),
        "semantic_string": semantic_string,
    }
    logger.info(
        "Starting tool execution",
        extra={
            "event_type": "tool_call_start",
            "tool_name": tool_name,
            "tool_input": tool_input,
        },
    )

    # Input validation
    placeholder_present = "$1" in sql_query
    query_params = []

    if placeholder_present and not semantic_string:
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        error_msg = (
            "Query uses embedding placeholder $1 but no 'semantic_string' was provided."
        )
        logger.error(
            error_msg,
            extra={
                "event_type": "tool_call_error",
                "tool_name": tool_name,
                "error_details": {"type": "ValueError", "message": error_msg},
                "tool_input": tool_input,
                "duration_ms": duration_ms,
            },
        )
        return json.dumps({"error": error_msg, "results": []}, indent=2)

    if semantic_string and not placeholder_present:
        # Log as warning, as we proceed anyway per the plan
        logger.warning(
            "'semantic_string' provided, but query missing '$1' placeholder.",
            extra={
                "event_type": "tool_call_warning",
                "tool_name": tool_name,
                "warning_details": {
                    "message": "Semantic string provided but not used in query."
                },
                "tool_input": tool_input,
            },
        )

    try:
        # Get embedding if needed
        if semantic_string and placeholder_present:
            embedding_start_time = asyncio.get_event_loop().time()
            logger.info(
                "Generating embedding",
                extra={
                    "event_type": "embedding_start",
                    "tool_name": tool_name,
                    "semantic_string_length": len(semantic_string),
                },
            )

            # Get the Coco client from the lifespan context
            coco_client = ctx.request_context.lifespan_context["coco_client"]
            embedding_model = ctx.request_context.lifespan_context.get(
                "embedding_model"
            )

            try:
                # Generate embedding - embed() is synchronous, so run in thread pool
                embedding_vector = await asyncio.to_thread(
                    coco_client.embed, semantic_string, model=embedding_model
                )
                embedding_duration_ms = (
                    asyncio.get_event_loop().time() - embedding_start_time
                ) * 1000
                embedding_dimensions = (
                    len(embedding_vector) if embedding_vector is not None else 0
                )

                logger.info(
                    f"Embedding generated successfully",
                    extra={
                        "event_type": "embedding_success",
                        "tool_name": tool_name,
                        "dimensions": embedding_dimensions,
                        "duration_ms": embedding_duration_ms,
                    },
                )

                # Format the embedding for pgvector
                if embedding_dimensions > 0:
                    query_params = [embedding_vector]
                    logger.info(
                        "Using embedding vector for pgvector",
                        extra={
                            "event_type": "embedding_param_set",
                            "tool_name": tool_name,
                            "vector_type": type(query_params[0]).__name__,
                            "query_params": query_params,
                        },
                    )
                else:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    error_msg = "Generated embedding vector has zero dimensions."
                    logger.error(
                        error_msg,
                        extra={
                            "event_type": "tool_call_error",
                            "tool_name": tool_name,
                            "error_details": {
                                "type": "ValueError",
                                "message": error_msg,
                            },
                            "tool_input": tool_input,
                            "duration_ms": duration_ms,
                        },
                    )
                    return json.dumps({"error": error_msg, "results": []}, indent=2)
            except Exception as embed_err:
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                embedding_duration_ms = (
                    asyncio.get_event_loop().time() - embedding_start_time
                ) * 1000
                logger.error(
                    "Embedding generation failed",
                    exc_info=True,
                    extra={
                        "event_type": "tool_call_error",
                        "tool_name": tool_name,
                        "error_stage": "embedding",
                        "error_details": {
                            "type": type(embed_err).__name__,
                            "message": str(embed_err),
                        },
                        "tool_input": tool_input,
                        "embedding_duration_ms": embedding_duration_ms,
                        "duration_ms": duration_ms,
                    },
                )
                return json.dumps(
                    {
                        "error": f"Failed to generate embedding: {str(embed_err)}",
                        "results": [],
                    },
                    indent=2,
                )

        # Execute database query
        db_query_start_time = asyncio.get_event_loop().time()
        logger.info(
            "Executing database query",
            extra={
                "event_type": "db_query_start",
                "tool_name": tool_name,
                "query_type": "pgvector" if placeholder_present else "sql",
                "sql": sql_query[:500]
                + ("..." if len(sql_query) > 500 else ""),  # Log truncated query
            },
        )
        pool = ctx.request_context.lifespan_context["db_pool"]

        formatted_results = []
        row_count = 0

        async with pool.acquire() as conn:
            # Register vector type codec (consider if this needs error handling)
            try:
                await conn.set_type_codec(
                    "vector",
                    encoder=lambda v: (
                        v if isinstance(v, str) else str(v).replace(" ", "")
                    ),
                    decoder=lambda v: v,
                    schema="public",
                    format="text",
                )
                logger.info(
                    "Registered vector type codec for connection",
                    extra={
                        "event_type": "db_codec_register_success",
                        "tool_name": tool_name,
                    },
                )
            except Exception as codec_error:
                # Log as warning, as the query might still work
                logger.warning(
                    f"Could not register vector type codec: {codec_error}",
                    extra={
                        "event_type": "db_codec_register_warning",
                        "tool_name": tool_name,
                        "error_details": {
                            "type": type(codec_error).__name__,
                            "message": str(codec_error),
                        },
                    },
                )

            # Use a read-only transaction for safety
            async with conn.transaction(readonly=True, isolation="read_committed"):
                try:
                    results = await conn.fetch(sql_query, *query_params)
                    db_query_duration_ms = (
                        asyncio.get_event_loop().time() - db_query_start_time
                    ) * 1000
                    row_count = len(results)
                    logger.info(
                        "Database query executed successfully",
                        extra={
                            "event_type": "db_query_success",
                            "tool_name": tool_name,
                            "row_count": row_count,
                            "duration_ms": db_query_duration_ms,
                        },
                    )

                    # Format the results (keep potentially large data out of logs)
                    for row in results:
                        row_dict = {}
                        for k, v in dict(row).items():
                            if isinstance(
                                v, (str, int, float, bool, type(None), list, dict)
                            ):
                                row_dict[k] = v
                            else:
                                row_dict[k] = str(v)  # Convert non-serializable types
                        formatted_results.append(row_dict)

                except asyncpg.PostgresSyntaxError as syntax_error:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    db_query_duration_ms = (
                        asyncio.get_event_loop().time() - db_query_start_time
                    ) * 1000
                    error_msg = str(syntax_error)
                    logger.error(
                        "SQL syntax error during query execution",
                        exc_info=True,
                        extra={
                            "event_type": "tool_call_error",
                            "tool_name": tool_name,
                            "error_stage": "db_query_syntax",
                            "error_details": {
                                "type": type(syntax_error).__name__,
                                "message": error_msg,
                                "query": sql_query,  # Include full query in error log
                            },
                            "tool_input": tool_input,
                            "db_query_duration_ms": db_query_duration_ms,
                            "duration_ms": duration_ms,
                        },
                    )

                    # Create enhanced error for user (keep sensitive info out)
                    enhanced_error = {
                        "error": f"SQL syntax error: {error_msg}",
                        "query": sql_query,
                        "hints": [],
                    }
                    # Analyze the error and provide specific guidance
                    if "syntax error at or near" in error_msg:
                        error_location = (
                            error_msg.split("syntax error at or near")[1]
                            .strip()
                            .strip("\"'")
                        )
                        enhanced_error["hints"].append(
                            f"There's a syntax error near: {error_location}"
                        )
                        if "$1" in error_location or error_location == "$1":
                            enhanced_error["hints"].append(
                                "When using vector operations with parameters, use PostgreSQL cast syntax: $1::vector"
                            )
                            enhanced_error["hints"].append(
                                "Example: embedding <=> $1::vector instead of embedding <=> $1"
                            )
                        if (
                            "<->" in sql_query
                            or "<=>" in sql_query
                            or "<#>" in sql_query
                        ):
                            if "::vector" not in sql_query and "vector" in sql_query:
                                enhanced_error["hints"].append(
                                    "This database doesn't support the vector() function"
                                )
                                enhanced_error["hints"].append(
                                    "Instead use the cast syntax: $1::vector"
                                )
                            elif (
                                "vector" not in sql_query
                                and "::vector" not in sql_query
                            ):
                                enhanced_error["hints"].append(
                                    "Vector comparison operators (<->, <=>, <#>) should be used with parameter casting"
                                )
                                enhanced_error["hints"].append(
                                    "Example: embedding <=> $1::vector LIMIT 5"
                                )
                    if "function vector" in error_msg:
                        enhanced_error["hints"].append(
                            "This database doesn't have a vector() function. Use PostgreSQL cast syntax instead."
                        )
                        enhanced_error["hints"].append(
                            "Use $1::vector instead of vector($1)"
                        )
                        fixed_query = sql_query.replace("vector($1)", "$1::vector")
                        enhanced_error["corrected_query_suggestion"] = fixed_query
                    enhanced_error["examples"] = [
                        "SELECT * FROM documents ORDER BY embedding <=> $1::vector LIMIT 5",
                        "SELECT *, embedding <-> $1::vector AS distance FROM documents ORDER BY distance LIMIT 10",
                        "SELECT * FROM documents WHERE embedding <#> $1::vector < 0.5",
                    ]
                    return json.dumps(enhanced_error, indent=2)

                except Exception as db_err:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    db_query_duration_ms = (
                        asyncio.get_event_loop().time() - db_query_start_time
                    ) * 1000
                    logger.error(
                        "Error during database query execution",
                        exc_info=True,
                        extra={
                            "event_type": "tool_call_error",
                            "tool_name": tool_name,
                            "error_stage": "db_query_execution",
                            "error_details": {
                                "type": type(db_err).__name__,
                                "message": str(db_err),
                                "query": sql_query,
                            },
                            "tool_input": tool_input,
                            "db_query_duration_ms": db_query_duration_ms,
                            "duration_ms": duration_ms,
                        },
                    )
                    return json.dumps(
                        {
                            "error": f"Error executing database query: {str(db_err)}",
                            "results": [],
                        },
                        indent=2,
                    )

        # Tool execution successful
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(
            "Tool execution successful",
            extra={
                "event_type": "tool_call_success",
                "tool_name": tool_name,
                "result_summary": {"row_count": row_count},
                "duration_ms": duration_ms,
            },
        )
        return json.dumps(
            {"results": formatted_results, "row_count": row_count}, indent=2
        )

    except Exception as outer_err:
        # Catch-all for errors outside the main db query block (e.g., pool acquire)
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.error(
            "Unhandled error during tool execution",
            exc_info=True,
            extra={
                "event_type": "tool_call_error",
                "tool_name": tool_name,
                "error_stage": "outer_exception",
                "error_details": {
                    "type": type(outer_err).__name__,
                    "message": str(outer_err),
                },
                "tool_input": tool_input,
                "duration_ms": duration_ms,
            },
        )
        return json.dumps(
            {"error": f"An unexpected error occurred: {str(outer_err)}", "results": []},
            indent=2,
        )


# Run the server when executed directly
if __name__ == "__main__":
    logger.error(
        "MCP Coco Database Server starting up"
    )  # Use error level to ensure it goes to stderr
