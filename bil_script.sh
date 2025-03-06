#!/bin/bash
echo "Running script..."
BIL_UUID="$1"  # Capture the first argument
echo "Processing BIL_UUID: $BIL_UUID"

# Simulate processing and write "Passed" to the output file
echo "Passed" > bil_output.txt
