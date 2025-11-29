#!/bin/bash

# yt-dlp API - cURL Examples
# Make sure the API is running at http://localhost:8000

API_URL="http://localhost:8000"

echo "=== yt-dlp API Examples ==="
echo ""

# 1. Get video info
echo "1. Getting video info..."
curl -X GET "${API_URL}/api/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
echo -e "\n"

# 2. Start download (MP3)
echo "2. Starting MP3 download..."
RESPONSE=$(curl -s -X POST "${API_URL}/api/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "format": "mp3",
    "mp3_title": "Never Gonna Give You Up",
    "embed_thumbnail": true
  }')

echo $RESPONSE
TASK_ID=$(echo $RESPONSE | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)
echo "Task ID: $TASK_ID"
echo -e "\n"

# 3. Check status
if [ ! -z "$TASK_ID" ]; then
    echo "3. Checking task status..."
    sleep 2
    curl -X GET "${API_URL}/api/status/${TASK_ID}"
    echo -e "\n"
    
    # 4. Wait for completion (polling)
    echo "4. Waiting for completion..."
    while true; do
        STATUS=$(curl -s -X GET "${API_URL}/api/status/${TASK_ID}" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
        echo "Status: $STATUS"
        
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            break
        fi
        
        sleep 3
    done
    echo -e "\n"
    
    # 5. Download file
    if [ "$STATUS" = "completed" ]; then
        echo "5. Downloading file..."
        curl -O -J "${API_URL}/api/download/${TASK_ID}"
        echo "File downloaded!"
    fi
fi

echo -e "\n"
echo "=== Additional Examples ==="

# Get queue stats
echo "Queue statistics:"
curl -X GET "${API_URL}/api/queue/stats"
echo -e "\n"

# List all tasks
echo "Recent tasks:"
curl -X GET "${API_URL}/api/tasks?limit=5"
echo -e "\n"

# Download subtitles
echo "Download subtitles:"
curl -X GET "${API_URL}/api/subtitles?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&lang=en"
echo -e "\n"