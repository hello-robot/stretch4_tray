#!/bin/bash

# This script starts the launch files for stretch driver, dual hesai launch, head cameras and gripper camera.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $SCRIPT_DIR

# Helper function to run commands in a parallel terminal, keeping it open on error
run_in_terminal() {
    # Provide an alternative here: xterm -e "bash -c \"\$1 || { ...; read; }\"" &
    gnome-terminal --tab -- /bin/bash -c "echo '================='; echo ''; echo '$1'; echo ''; echo '=================='; $1; RET=\$?; echo -e '\n\e[33m[INFO] Process finished with exit code \$RET\nCommand ran: $1\e[0m'; export HISTFILE=~/.bash_history; history -s '$1'; history -a; exec /bin/bash" &
}


# run_in_terminal "stretch_body_server --launch"


# echo "Waiting until stretch body server is running before running the other ROS2 nodes..."
# while true; do
#     OUTPUT=$(stretch_body_server --ping 2>&1)
    
#     if ! echo "$OUTPUT" | grep -q "Not able to connect"; then
#         echo "Connection successful! Starting other terminals..."
#         break
#     fi

#     sleep 1
# done

# run_in_terminal "ros2 run rmw_zenoh_cpp rmw_zenohd"
# sleep 1
run_in_terminal "ros2 launch stretch_core stretch_driver.launch.py broadcast_odom_tf:=True"
run_in_terminal "ros2 launch stretch_core dual_hesai.launch.py use_rviz:=false"
# run_in_terminal "stretch_gamepad_teleop"

run_in_terminal "ros2 launch stretch_core luxonis.launch.py use_center:=true use_left:=true use_right:=true use_rviz:=false"
sleep 5 # Hack: running gripper_camera and luxonis in the same terminal causes the gripper camera to fail to start.
run_in_terminal "ros2 launch stretch_core gripper_camera.launch.py"

run_in_terminal "ros2 launch stretch_core rgbd.launch.py use_center:=true use_left:=true use_right:=true use_rviz:=false"