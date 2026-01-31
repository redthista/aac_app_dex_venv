#!/bin/bash

# Build and Deploy Script for Dexter Speaks AAC App

echo "🐳 Building Docker image..."
docker build -t dexter-speaks:latest .

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
    echo ""
    echo "📦 To run the container:"
    echo "   docker-compose up -d"
    echo ""
    echo "   OR manually:"
    echo "   docker run -d --name dexter-speaks -p 8080:8080 -v ./data:/app/data dexter-speaks:latest"
    echo ""
    echo "🌐 Access the app at: http://localhost:8080"
else
    echo "❌ Build failed!"
    exit 1
fi
