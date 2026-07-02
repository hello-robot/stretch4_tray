#!/bin/bash

WS_DIR="$HOME/ament_ws"

# Navigate to the workspace
cd "$WS_DIR" || { echo "Error: $WS_DIR not found."; exit 1; }

# Clean the workspace
echo "Cleaning workspace: removing build, install, and log..."
rm -rf build/ install/ log/
echo "Clean complete."

# Run colcon build
echo "Starting colcon build..."
export MAKEFLAGS="-j 4" # the NUC cannot handle the memory intensive build of depthai_core, this and --executor sequential are the best config for getting a successful build.
colcon build --allow-overriding nav2_costmap_2d --executor sequential --symlink-install
unset MAKEFLAGS

# Source the bashrc 
# (Requires running the script with 'source' to affect your current shell)
source ~/.bashrc

echo "Build finished and environment sourced."