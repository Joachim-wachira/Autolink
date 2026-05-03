#!/bin/bash

# Generate config.js from environment variables if needed
# This script ensures config.js exists before starting the server

if [ ! -f "config.js" ]; then
    echo "Creating config.js from environment variables..."
    cat > config.js << EOF
// config.js - Generated at runtime
const CONFIG = {
    API_BASE_URL: '${API_BASE_URL:-https://autolink-backend.onrender.com}',
    GOOGLE_MAPS_API_KEY: '${GOOGLE_MAPS_API_KEY:-}'
};
EOF
    echo "config.js created successfully"
else
    echo "config.js already exists"
fi

echo "Frontend configuration ready"
