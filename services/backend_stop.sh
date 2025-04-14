#!/bin/bash

# Transcription service constants
TRANSCRIPTION_DIR="$(pwd)/transcription"
PID_FILE="$TRANSCRIPTION_DIR/transcription_server.pid"
LOG_FILE="$TRANSCRIPTION_DIR/uvicorn.log"

# Function to stop transcription service
stop_transcription_service() {
    if [ -f "$PID_FILE" ]; then
        echo "🔍 Checking transcription service status..."
        if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "🛑 Stopping transcription service with PID $(cat "$PID_FILE")..."
            kill $(cat "$PID_FILE")
            
            # Wait for the process to terminate
            local max_attempts=10
            local attempt=1
            
            while [ $attempt -le $max_attempts ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; do
                echo "⏳ Waiting for transcription service to stop... (attempt $attempt/$max_attempts)"
                attempt=$((attempt + 1))
                sleep 1
            done
            
            # Force kill if still running
            if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
                echo "⚠️ Transcription service did not stop gracefully, forcing termination..."
                kill -9 $(cat "$PID_FILE")
            fi
            
            echo "✅ Transcription service stopped successfully"
        else
            echo "ℹ️ Transcription service is not running but PID file exists"
        fi
        
        # Remove PID file
        rm -f "$PID_FILE"
        echo "🧹 Removed PID file"
    else
        echo "ℹ️ No transcription service PID file found, service might not be running"
    fi
}

# Function to stop Docker services
stop_docker_services() {
    echo "🔍 Checking Docker services status..."
    
    # Check if any containers are running using docker compose ps -q
    if [ -n "$(docker compose ps -q 2>/dev/null)" ]; then
        echo "🐳 Stopping Docker services..."
        docker compose down || { echo "⚠️ Failed to stop Docker services cleanly"; return 1; }
        echo "✅ Docker services stopped successfully"
    else
        echo "ℹ️ No Docker services are currently running"
    fi
}

# Function to clean up log files
clean_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "🧹 Cleaning up log files..."
        rm -f "$LOG_FILE"
        echo "✅ Log files removed"
    fi
}

echo "ℹ️ Stopping backend services..."

# Stop transcription service
stop_transcription_service

# Stop Docker services
stop_docker_services

# Clean up logs (optional, uncomment if you want to remove logs on stop)
# clean_logs

echo "✅ All services stopped successfully!"
exit 0