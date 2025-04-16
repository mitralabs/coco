#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import pgDefault from "pg";
const { Pool } = pgDefault;
import axios from "axios";

const server = new Server(
  {
    name: "example-servers/postgres",
    version: "0.1.0",
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  },
);

// const args = process.argv.slice(2);
// if (args.length === 0) {
//   console.error("Please provide a database URL as a command-line argument");
//   process.exit(1);
// }
// const databaseUrl = args[0];

// Read Database URL from environment variable
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
    console.error("Error: DATABASE_URL environment variable is not set.");
    process.exit(1);
}

// Read OpenAI API Key from environment variables
const openaiApiKey = process.env.OPENAI_API_KEY;
if (!openaiApiKey) {
    console.error("Error: OPENAI_API_KEY environment variable is not set.");
    process.exit(1);
}

const resourceBaseUrl = new URL(databaseUrl);
resourceBaseUrl.protocol = "postgres:";
resourceBaseUrl.password = "";

const pool = new Pool({
  connectionString: databaseUrl,
});

const SCHEMA_PATH = "schema";

server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const client = await pool.connect();
  try {
    const result = await client.query(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
    );
    return {
      resources: result.rows.map((row) => ({
        uri: new URL(`${row.table_name}/${SCHEMA_PATH}`, resourceBaseUrl).href,
        mimeType: "application/json",
        name: `"${row.table_name}" database schema`,
      })),
    };
  } finally {
    client.release();
  }
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const resourceUrl = new URL(request.params.uri);

  const pathComponents = resourceUrl.pathname.split("/");
  const schema = pathComponents.pop();
  const tableName = pathComponents.pop();

  if (schema !== SCHEMA_PATH) {
    throw new Error("Invalid resource URI");
  }

  const client = await pool.connect();
  try {
    const result = await client.query(
      "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1",
      [tableName],
    );

    return {
      contents: [
        {
          uri: request.params.uri,
          mimeType: "application/json",
          text: JSON.stringify(result.rows, null, 2),
        },
      ],
    };
  } finally {
    client.release();
  }
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "execute_pgvector_query",
        description:
          "Executes a read-only SQL query, optionally including vector similarity. Use $1 as the placeholder for the embedding vector if semantic_string is provided.",
        inputSchema: {
          type: "object",
          properties: {
            sql_query: {
              type: "string",
              description:
                "The complete SQL query. Use $1 as the placeholder for the embedding vector if semantic_string is provided.",
            },
            semantic_string: {
              type: "string",
              description:
                "Optional: Text to embed. Provide only if sql_query uses the $1 placeholder.",
            },
          },
          required: ["sql_query"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "execute_pgvector_query") {
    const sql_query = request.params.arguments?.sql_query as string;
    const semantic_string = request.params.arguments?.semantic_string as
      | string
      | undefined;

    let queryParams: any[] = [];
    const placeholder_present = sql_query.includes("$1");

    if (placeholder_present && !semantic_string) {
      throw new Error(
        "Query uses embedding placeholder $1 but no 'semantic_string' was provided.",
      );
    }
    if (semantic_string && !placeholder_present) {
        console.warn(
          "Warning: 'semantic_string' was provided, but the query is missing the '$1' placeholder."
        );
    }

    if (semantic_string) {
      try {
        console.log(`Fetching embedding for: "${semantic_string.substring(0, 50)}..."`); // Log embedding attempt
        const response = await axios.post(
          "https://api.openai.com/v1/embeddings",
          {
            input: semantic_string,
            model: "text-embedding-3-small", // Or make configurable
          },
          {
            headers: {
              Authorization: `Bearer ${openaiApiKey}`,
              "Content-Type": "application/json",
            },
            timeout: 15000, // 15 second timeout for embedding API call
          },
        );

        if (
          response.data &&
          response.data.data &&
          response.data.data.length > 0
        ) {
          const embeddingVector = response.data.data[0].embedding;
          if (placeholder_present) {
             queryParams = [embeddingVector]; // Use vector only if placeholder exists
             console.log("Embedding fetched successfully.");
          } else {
             console.warn("Embedding fetched but not used as $1 placeholder is missing.");
          }
        } else {
          throw new Error("Invalid response format from OpenAI Embedding API");
        }
      } catch (error: any) {
        console.error("Error fetching embedding from OpenAI:", error.response?.data || error.message);
        // Re-throw as a more specific error for MCP
        throw new Error(`Failed to get embedding: ${error.message}`);
      }
    } else if (placeholder_present) {
        throw new Error("Query uses embedding placeholder $1 but no 'semantic_string' was provided.");
    }

    const client = await pool.connect();
    try {
      console.log("Executing SQL query...");
      await client.query("BEGIN TRANSACTION READ ONLY");
      const result = await client.query(sql_query, queryParams);
      console.log(`Query executed successfully, returned ${result.rows.length} rows.`);
      return {
        content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        isError: false,
      };
    } catch (error: any) {
        console.error("Error executing SQL query:", error.message);
        throw error;
    } finally {
      console.log("Rolling back transaction and releasing client.");
      client
        .query("ROLLBACK")
        .catch((error) =>
          console.warn("Could not roll back transaction:", error),
        );

      client.release();
    }
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

runServer().catch(console.error);
