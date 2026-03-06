#!/bin/bash
# Generate config.js with environment variables for production

cat > frontend/config.js << EOF
const CONFIG = {
    API_BASE_URL: '${API_BASE_URL}',
    GOOGLE_MAPS_API_KEY: '${GOOGLE_MAPS_API_KEY}'
};
EOF

echo "✓ Config file generated successfully"
