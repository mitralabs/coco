#!/bin/bash

# Repository constants
REPO_URL="https://github.com/ggml-org/whisper.cpp"
COMMIT_HASH="ada745f4a5af9a5e237fda9ca402b4b73919bdde"
WHISPER_DIR="$(pwd)/whisper.cpp"

# Transcription service constants
TRANSCRIPTION_DIR="$(pwd)/transcription"
VENV_DIR="$TRANSCRIPTION_DIR/venv-transcription"
PID_FILE="$TRANSCRIPTION_DIR/transcription_server.pid"
LOG_FILE="$TRANSCRIPTION_DIR/uvicorn.log"
APP_MODULE="app.main:app"

# Function to check if the model name is valid
is_valid_model() {
    local model=$1
    local valid_models=("tiny" "base" "small" "medium" "large-v1" "large-v2" "large-v3" "large-v3-turbo" "large-v3-turbo-q5_0")
    
    for valid_model in "${valid_models[@]}"; do
        if [ "$model" == "$valid_model" ]; then
            return 0
        fi
    done
    return 1
}

# Custom function to parse .env file that handles spaces around equals sign
parse_env_file() {
    local env_file=$1
    
    if [ -f "$env_file" ]; then
        echo "✅ Loading environment variables from $env_file file"
        
        # Read the file line by line
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip comments and empty lines
            if [[ $line =~ ^\s*# ]] || [[ -z $line ]]; then
                continue
            fi
            
            # Remove leading/trailing whitespace and extract variable name and value
            line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            
            # Extract variable name and value, handling spaces around equals sign
            if [[ $line =~ ^([A-Za-z0-9_]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
                local name="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Remove quotes if present
                value=$(echo "$value" | sed -e 's/^["\x27]//' -e 's/["\x27]$//')
                
                # Export the variable
                export "$name"="$value"
            fi
        done < "$env_file"
    else
        echo "⚠️ No $env_file file found, will use default model if WHISPER_MODEL is not set"
    fi
}

# Function to check if transcription service is running
check_transcription_service() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "✅ Transcription service is already running with PID $(cat "$PID_FILE")"
        return 0
    else
        # Clean up stale PID file if it exists
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
        return 1
    fi
}

# Function to wait for application startup
wait_for_startup() {
    local max_attempts=30
    local attempt=1
    echo "🔍 Checking if transcription service started successfully..."
    
    while [ $attempt -le $max_attempts ]; do
        if grep -q "Application startup complete" "$LOG_FILE" 2>/dev/null; then
            echo "✅ Transcription service started successfully!"
            return 0
        fi
        
        echo "⏳ Waiting for application to start... (attempt $attempt/$max_attempts)"
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo "⚠️ Timeout waiting for application to start. Check $LOG_FILE for details."
    
    # Kill the process if it failed to start properly
    if [ -f "$PID_FILE" ]; then
        echo "🛑 Terminating failed process with PID $(cat "$PID_FILE")"
        kill -9 $(cat "$PID_FILE") 2>/dev/null || echo "⚠️ Process already terminated"
        rm -f "$PID_FILE"
        echo "🧹 Removed stale PID file"
    fi
    
    return 1
}

# Function to check if whisper model already exists
check_model_exists() {
    local model=$1
    local model_path="$WHISPER_DIR/models/ggml-$model.bin"
    
    if [ -f "$model_path" ]; then
        return 0
    else
        return 1
    fi
}

# Load environment variables
echo "🔍 Loading environment variables..."
parse_env_file ".env"

# Set default model if not defined
if [ -z "$WHISPER_MODEL" ]; then
    WHISPER_MODEL="base"
    echo "ℹ️ Using default model: $WHISPER_MODEL"
else
    # Extract the base part before ".en" if present
    MODEL_BASE=${WHISPER_MODEL%%.*}
    
    if is_valid_model "$MODEL_BASE"; then
        echo "✅ Using model: $WHISPER_MODEL"
    else
        echo "⚠️ Invalid model name: $WHISPER_MODEL"
        echo "Valid models are: tiny, base, small, medium, large-v1, large-v2, large-v3, large-v3-turbo, large-v3-turbo-q5_0"
        echo "You can add .en suffix for English-only models"
        exit 1
    fi
fi

# Check if whisper.cpp directory already exists
if [ -d "$WHISPER_DIR" ]; then
    echo "📁 $WHISPER_DIR directory already exists. Skipping clone and build steps."
else
    echo "🚀 Setting up whisper.cpp repository..."
    
    # Create a temporary directory for cloning
    TEMP_DIR=$(mktemp -d)
    echo "🔄 Created temporary directory: $TEMP_DIR"
    
    # Clone the repository
    echo "📥 Cloning repository: $REPO_URL"
    git clone "$REPO_URL" "$TEMP_DIR" || { echo "❌ Failed to clone repository"; exit 1; }
    
    # Navigate to the cloned repository
    cd "$TEMP_DIR" || exit 1
    
    # Checkout the specific commit
    echo "⚙️ Checking out commit: $COMMIT_HASH"
    git checkout "$COMMIT_HASH" || { echo "❌ Failed to checkout commit"; exit 1; }
    
    # Remove .git directory
    echo "🧹 Removing Git information..."
    rm -rf .git
    
    # Move to parent directory of the script
    cd ..
    
    # Move the contents to the target directory
    echo "📦 Moving files to $WHISPER_DIR"
    mv "$TEMP_DIR" "$WHISPER_DIR"
    
    # Navigate to the whisper.cpp directory
    cd "$WHISPER_DIR" || { echo "❌ Failed to navigate to $WHISPER_DIR"; exit 1; }
    
    # Build the project
    echo "🔨 Building whisper.cpp..."
    cmake -B build || { echo "❌ Failed to configure the build"; exit 1; }
    echo "⚙️ Compiling..."
    cmake --build build --config Release || { echo "❌ Failed to build the project"; exit 1; }
    echo "✅ Build completed successfully!"
    
    # Return to the original directory
    cd ..
fi

# Check if the model already exists before attempting download
cd "$WHISPER_DIR" || { echo "❌ Failed to navigate to $WHISPER_DIR"; exit 1; }
if check_model_exists "$WHISPER_MODEL"; then
    echo "✅ Model $WHISPER_MODEL already exists, skipping download."
else
    echo "📥 Downloading whisper model: $WHISPER_MODEL..."
    sh ./models/download-ggml-model.sh "$WHISPER_MODEL" || { echo "❌ Failed to download the model"; exit 1; }
    echo "✅ Model $WHISPER_MODEL downloaded successfully!"
fi

echo "✨ Setup complete! whisper.cpp is ready to use with model: $WHISPER_MODEL"

# Return to the original directory
cd "$(dirname "$0")" || { echo "❌ Failed to navigate to script directory"; exit 1; }

# -------------------------------------------------------------
# Transcription Service Setup and Start
# -------------------------------------------------------------

echo "🔍 Checking transcription service status..."
if check_transcription_service; then
    echo "ℹ️ Transcription service is already running. No action needed."
    exit 0
fi

echo "🚀 Setting up transcription service..."

# Check if virtual environment exists
if [ -d "$VENV_DIR" ]; then
    echo "📁 Virtual environment already exists at $VENV_DIR"
    venv_created=false
else
    echo "🔧 Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR" || { echo "❌ Failed to create virtual environment"; exit 1; }
    echo "✅ Virtual environment created successfully"
    venv_created=true
fi

# Activate virtual environment
echo "🔌 Activating virtual environment"
source "$VENV_DIR/bin/activate" || { echo "❌ Failed to activate virtual environment"; exit 1; }

# Install requirements only if virtual environment was newly created
if [ "$venv_created" = true ] && [ -f "$TRANSCRIPTION_DIR/requirements.txt" ]; then
    echo "📦 Installing requirements from $TRANSCRIPTION_DIR/requirements.txt"
    pip install -r "$TRANSCRIPTION_DIR/requirements.txt" -q || { echo "❌ Failed to install requirements"; exit 1; }
    echo "✅ Requirements installed successfully"
elif [ "$venv_created" = true ] && [ ! -f "$TRANSCRIPTION_DIR/requirements.txt" ]; then
    echo "⚠️ No requirements.txt found in $TRANSCRIPTION_DIR"
else
    echo "ℹ️ Using existing virtual environment, skipping requirements installation"
fi

cd "$TRANSCRIPTION_DIR" || { echo "❌ Failed to navigate to $TRANSCRIPTION_DIR"; exit 1; }

# Start the transcription service
echo "🚀 Starting transcription service..."
nohup python3 -m uvicorn $APP_MODULE --host 0.0.0.0 --port 8000 --reload --log-level debug > "$LOG_FILE" 2>&1 &

# Save the PID
echo $! > "$PID_FILE"
echo "📝 Transcription service started with PID $!"

# Wait for application startup
wait_for_startup

# Deactivate virtual environment
deactivate
echo "🔌 Virtual environment deactivated"

cd "$(dirname "$0")" || { echo "❌ Failed to navigate to script directory"; exit 1; }