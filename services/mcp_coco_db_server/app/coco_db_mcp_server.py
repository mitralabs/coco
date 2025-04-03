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
import signal
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
import numpy as np

# Ensure the Python SDK is in the path when mounted in the Docker container
sys.path.insert(0, '/python_sdk/src')

# FastMCP for the server implementation
from mcp.server.fastmcp import FastMCP, Context

# PostgreSQL async driver
import asyncpg

# Import Coco SDK components (will be available when the SDK is mounted)
from coco.lm import LanguageModelClient

# Configure logging to stderr only for MCP compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Ensure logs go to stderr, not stdout
)
logger = logging.getLogger(__name__)

# Global variable to track server state
shutdown_event = asyncio.Event()

# Signal handler for graceful shutdown
def handle_terminate(sig, frame):
    """Handle termination signals by setting the shutdown event."""
    logger.error(f"Received signal {sig}, initiating shutdown...")
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
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    # Read Coco SDK configuration variables
    ollama_base_url = os.getenv("COCO_OLLAMA_URL_BASE")
    openai_base_url = os.getenv("COCO_OPENAI_URL_BASE")
    embedding_api = os.getenv("COCO_EMBEDDING_API")
    llm_api = os.getenv("COCO_LLM_API")
    embedding_model = os.getenv("COCO_EMBEDDING_MODEL")
    
    # Validate configuration
    if embedding_api not in ["ollama", "openai"]:
        logger.error(f"Invalid COCO_EMBEDDING_API: {embedding_api}. Must be 'ollama' or 'openai'")
        sys.exit(1)
    
    if embedding_api == "openai" and not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable is required when COCO_EMBEDDING_API=openai")
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
                logger.error("Parent process is no longer running, initiating shutdown...")
                shutdown_event.set()
                break
    
    # Start the watchdog task
    watchdog_task = asyncio.create_task(check_parent_process())
    
    # Resources to be cleaned up
    pool = None
    
    try:
        # Initialize database connection pool
        logger.error(f"Connecting to database: {database_url.split('@')[-1]}")  # Use error level to ensure it goes to stderr
        pool = await asyncpg.create_pool(database_url)
        
        # Initialize Coco language model client for embeddings
        logger.error(f"Initializing Coco LanguageModelClient with {embedding_api} for embeddings")  # Use error level to ensure it goes to stderr
        coco_client = LanguageModelClient(
            ollama_base_url=ollama_base_url,
            openai_base_url=openai_base_url,
            embedding_api=embedding_api,
            llm_api=llm_api,
        )
        
        # Yield the context with both resources
        yield {
            'db_pool': pool,
            'coco_client': coco_client,
            'embedding_model': embedding_model,
        }
        
        # After the context manager exits, wait for shutdown signal if needed
        if not shutdown_event.is_set():
            try:
                # Wait for shutdown signal with a timeout
                logger.error("Waiting for clean shutdown signal...")
                await asyncio.wait_for(shutdown_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for shutdown signal, proceeding with cleanup")
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Clean up resources
        logger.error("Shutting down MCP server, cleaning up resources")  # Use error level to ensure it goes to stderr
        
        # Cancel the watchdog task
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
            
        # Close the database pool if it was created
        if pool is not None:
            logger.error("Closing database connection pool")
            await pool.close()
            
        logger.error("Cleanup complete, server shutting down")

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
    logger.error(f"Getting schema for table '{table_name}'")  # Use error level to ensure it goes to stderr
    try:
        # Create a direct database connection for this request
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Execute query to get column information
            query = """
                SELECT column_name, data_type, is_nullable, 
                       column_default, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = $1 AND table_schema = 'public'
                ORDER BY ordinal_position
            """
            results = await conn.fetch(query, table_name)
            
            if not results:
                # Table doesn't exist or has no columns
                logger.error(f"No schema information found for table '{table_name}'")  # Use error level to ensure it goes to stderr
                return json.dumps({
                    "error": f"Table '{table_name}' not found or has no columns",
                    "columns": []
                }, indent=2)
            
            # Format the results as a more readable dictionary
            columns = []
            for row in results:
                column_info = {
                    "name": row['column_name'],
                    "data_type": row['data_type'],
                    "is_nullable": row['is_nullable'],
                    "default": row['column_default']
                }
                
                # Only include maximum length for character types
                if row['character_maximum_length'] is not None:
                    column_info["max_length"] = row['character_maximum_length']
                
                columns.append(column_info)
            
            # Return the formatted schema information
            return json.dumps({
                "table_name": table_name,
                "columns": columns
            }, indent=2)
        finally:
            # Ensure connection is closed
            await conn.close()
    
    except Exception as e:
        logger.error(f"Error getting schema for table '{table_name}': {e}")
        return json.dumps({
            "error": f"Failed to get schema: {str(e)}",
            "columns": []
        }, indent=2)

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
"""
)
async def execute_pgvector_query(
    sql_query: str, 
    ctx: Context,
    semantic_string: Optional[str] = None
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
    # Input validation
    placeholder_present = "$1" in sql_query
    query_params = []
    
    if placeholder_present and not semantic_string:
        error_msg = "Query uses embedding placeholder $1 but no 'semantic_string' was provided."
        logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "results": []
        }, indent=2)
    
    if semantic_string and not placeholder_present:
        logger.error("'semantic_string' was provided, but the query is missing the '$1' placeholder.")
    
    try:
        # Get embedding if needed
        if semantic_string and placeholder_present:
            logger.error(f"Generating embedding for semantic string: '{semantic_string[:50]}...'")  # Use error level to ensure it goes to stderr
            
            # Get the Coco client from the lifespan context
            coco_client = ctx.request_context.lifespan_context['coco_client']
            embedding_model = ctx.request_context.lifespan_context.get('embedding_model')
            
            # Generate embedding - embed() is synchronous, so we run it in a thread pool
            # to avoid blocking the event loop
            embedding_vector = await asyncio.to_thread(
                coco_client.embed,
                semantic_string,
                model=embedding_model
            )
            
            logger.error(f"Successfully generated embedding with {len(embedding_vector)} dimensions")  # Use error level to ensure it goes to stderr
            
            # Format the embedding for pgvector
            if len(embedding_vector) > 0:
                # Pass the embedding vector as is - asyncpg should handle the conversion
                query_params = [embedding_vector]
                logger.error(f"Using embedding vector for pgvector (type: {type(query_params[0]).__name__})")
            else:
                error_msg = "Generated embedding vector has no dimensions"
                logger.error(error_msg)
                return json.dumps({
                    "error": error_msg,
                    "results": []
                }, indent=2)
        
        # Execute database query
        logger.error(f"Executing SQL query: '{sql_query[:100]}...'")  # Use error level to ensure it goes to stderr
        pool = ctx.request_context.lifespan_context['db_pool']
        
        async with pool.acquire() as conn:
            # Register vector type codec if needed
            try:
                # Try to register a vector type handler for this connection
                await conn.set_type_codec(
                    'vector',
                    encoder=lambda v: v if isinstance(v, str) else str(v).replace(' ', ''),
                    decoder=lambda v: v,
                    schema='public',
                    format='text'
                )
                logger.error("Registered vector type codec for connection")
            except Exception as codec_error:
                logger.error(f"Note: Could not register vector type codec: {codec_error}")
            
            # Use a read-only transaction for safety
            async with conn.transaction(readonly=True, isolation='read_committed'):
                try:
                    results = await conn.fetch(sql_query, *query_params)
                except asyncpg.PostgresSyntaxError as syntax_error:
                    # Handle syntax errors with more detailed information
                    error_msg = str(syntax_error)
                    logger.error(f"SQL syntax error: {error_msg}")
                    logger.error(f"SQL query that caused the error: {sql_query}")
                    
                    # Create more helpful error messages for common vector syntax issues
                    enhanced_error = {
                        "error": f"SQL syntax error: {error_msg}",
                        "query": sql_query,
                        "hints": []
                    }
                    
                    # Analyze the error and provide specific guidance
                    if "syntax error at or near" in error_msg:
                        error_location = error_msg.split("syntax error at or near")[1].strip().strip('"\'')
                        enhanced_error["hints"].append(f"There's a syntax error near: {error_location}")
                        
                        # Check for common vector operation syntax issues
                        if "$1" in error_location or error_location == "$1":
                            enhanced_error["hints"].append("When using vector operations with parameters, use PostgreSQL cast syntax: $1::vector")
                            enhanced_error["hints"].append("Example: embedding <=> $1::vector instead of embedding <=> $1")
                            
                        if "<->" in sql_query or "<=>" in sql_query or "<#>" in sql_query:
                            if "::vector" not in sql_query and "vector" in sql_query:
                                enhanced_error["hints"].append("This database doesn't support the vector() function")
                                enhanced_error["hints"].append("Instead use the cast syntax: $1::vector")
                            elif "vector" not in sql_query and "::vector" not in sql_query:
                                enhanced_error["hints"].append("Vector comparison operators (<->, <=>, <#>) should be used with parameter casting")
                                enhanced_error["hints"].append("Example: embedding <=> $1::vector LIMIT 5")
                    
                    # Function error handling
                    if "function vector" in error_msg:
                        enhanced_error["hints"].append("This database doesn't have a vector() function. Use PostgreSQL cast syntax instead.")
                        enhanced_error["hints"].append("Use $1::vector instead of vector($1)")
                        
                        # Replace vector() syntax in the query with cast syntax for user reference
                        fixed_query = sql_query.replace("vector($1)", "$1::vector")
                        enhanced_error["corrected_query_suggestion"] = fixed_query
                    
                    # Add general pgvector syntax examples with correct PostgreSQL syntax
                    enhanced_error["examples"] = [
                        "SELECT * FROM documents ORDER BY embedding <=> $1::vector LIMIT 5",
                        "SELECT *, embedding <-> $1::vector AS distance FROM documents ORDER BY distance LIMIT 10",
                        "SELECT * FROM documents WHERE embedding <#> $1::vector < 0.5"
                    ]
                    
                    return json.dumps(enhanced_error, indent=2)
                except Exception as e:
                    # Handle other execution errors
                    error_msg = f"Error executing query: {str(e)}"
                    logger.error(error_msg)
                    return json.dumps({
                        "error": error_msg,
                        "results": []
                    }, indent=2)
            
            # Format the results as a list of dictionaries
            formatted_results = []
            for row in results:
                # Convert Row object to a regular dict with values that can be JSON serialized
                row_dict = {}
                for k, v in dict(row).items():
                    # Skip non-serializable types like bytea
                    if isinstance(v, (str, int, float, bool, type(None), list, dict)):
                        row_dict[k] = v
                    else:
                        row_dict[k] = str(v)
                
                formatted_results.append(row_dict)
            
            logger.error(f"Query executed successfully, returned {len(formatted_results)} rows")  # Use error level to ensure it goes to stderr
            return json.dumps({
                "results": formatted_results,
                "row_count": len(formatted_results)
            }, indent=2)
    
    except Exception as e:
        error_msg = f"Error executing query: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "results": []
        }, indent=2)

# Run the server when executed directly
if __name__ == "__main__":
    logger.error("MCP Coco Database Server starting up")  # Use error level to ensure it goes to stderr 