#!/bin/bash

# Script to clean up stuck processes on commonly used Django development ports

echo "Checking for processes on ports 7000, 8000, and 9000..."

PORTS=(7000 8000 9000)

for PORT in "${PORTS[@]}"; do
    echo ""
    echo "Checking port $PORT..."
    
    # Check if port is in use
    PID=$(lsof -t -i:$PORT)
    
    if [ -z "$PID" ]; then
        echo "✓ Port $PORT is free"
    else
        # Get process details
        echo "⚠ Port $PORT is in use by PID: $PID"
        ps -p $PID -o comm=,args= | sed 's/^/  /'
        
        # Ask for confirmation before killing
        read -p "Kill process $PID on port $PORT? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $PID
            if [ $? -eq 0 ]; then
                echo "✓ Process $PID killed successfully"
            else
                echo "✗ Failed to kill process $PID (may require sudo)"
            fi
        else
            echo "Skipped killing process $PID"
        fi
    fi
done

echo ""
echo "Port cleanup complete!"
echo ""
echo "Final status:"
for PORT in "${PORTS[@]}"; do
    if lsof -i:$PORT >/dev/null 2>&1; then
        echo "✗ Port $PORT is still in use"
    else
        echo "✓ Port $PORT is free"
    fi
done