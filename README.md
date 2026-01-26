# shrek_ros2_ws

A modular ROS2 Humble workspace for a four-wheeled differential drive robot with hexagonal chassis. This workspace provides a complete navigation stack with SLAM and AMCL localization, along with extensible modules for perception and manipulation.

## 🤖 Robot Description

The Shrek robot features:
- **Chassis**: Hexagonal design (green) with 0.6m length and 0.52m width
- **Drivetrain**: Four-wheeled differential drive (purple wheels)
- **Sensors**: LiDAR for SLAM and localization
- **Base**: Designed for autonomous navigation with future expansion for perception and manipulation

## 📦 Package Structure

### `shrek_essentials`
Core robot description and configuration files.
- **URDF/Xacro**: Complete robot model with proper inertial properties
- **Config**: Robot physical parameters and sensor configurations
- **Purpose**: Foundation for all other packages

### `shrek_bringup`
Launch files and configurations for bringing up the robot.
- **Launch Files**: Robot state publisher with RViz2 visualization
- **RViz Config**: Pre-configured visualization setup
- **Purpose**: Quick robot startup and visualization

### `shrek_navigation`
Complete navigation stack with SLAM and localization.
- **SLAM**: SLAM Toolbox for mapping
- **AMCL**: Adaptive Monte Carlo Localization for pose estimation
- **Nav2**: Full navigation stack with path planning and obstacle avoidance
- **Purpose**: Autonomous navigation capabilities

### `shrek_perception`
Placeholder for future perception modules.
- Camera integration, object detection, point cloud processing
- **Status**: Ready for expansion

### `shrek_manipulation`
Placeholder for future manipulation modules.
- Robotic arms, grippers, MoveIt integration
- **Status**: Ready for expansion

## 🚀 Getting Started

### Prerequisites

- **ROS2 Humble** installed
- Required packages:
  ```bash
  sudo apt install ros-humble-navigation2 ros-humble-nav2-bringup \
                   ros-humble-slam-toolbox ros-humble-robot-state-publisher \
                   ros-humble-joint-state-publisher-gui ros-humble-xacro
  ```

### Building the Workspace

```bash
cd ~/shrek_ros2_ws
colcon build --symlink-install
source install/setup.bash
```

### Visualizing the Robot

Launch the robot state publisher with RViz2:

```bash
ros2 launch shrek_bringup robot_state_publisher.launch.py
```

This will:
- Load the robot URDF
- Start the robot state publisher
- Open RViz2 with the robot model
- Launch joint state publisher GUI for testing

## 🗺️ Navigation

### Running SLAM (Mapping)

To create a map of your environment:

```bash
# Terminal 1: Launch robot (or use your robot's actual launch file)
ros2 launch shrek_bringup robot_state_publisher.launch.py

# Terminal 2: Start SLAM
ros2 launch shrek_navigation slam.launch.py

# Terminal 3: Drive the robot around to build the map
# (Use teleop or your preferred control method)

# Terminal 4: Save the map when done
cd ~/shrek_ros2_ws/src/shrek_navigation/maps
ros2 run nav2_map_server map_saver_cli -f my_map
```

### Running Localization (AMCL)

To localize the robot on an existing map:

```bash
# Terminal 1: Launch robot
ros2 launch shrek_bringup robot_state_publisher.launch.py

# Terminal 2: Start localization
ros2 launch shrek_navigation localization.launch.py map:=/path/to/your/map.yaml
```

### Running Full Navigation

To run autonomous navigation:

```bash
# Terminal 1: Launch robot
ros2 launch shrek_bringup robot_state_publisher.launch.py

# Terminal 2: Start localization
ros2 launch shrek_navigation localization.launch.py map:=/path/to/your/map.yaml

# Terminal 3: Start navigation
ros2 launch shrek_navigation navigation.launch.py
```

Then use RViz2 to:
1. Set initial pose (2D Pose Estimate)
2. Set navigation goal (2D Nav Goal)

## 🔧 Configuration

### Robot Parameters
Edit `shrek_essentials/config/robot_params.yaml` to adjust:
- Wheel dimensions and separation
- Maximum velocities
- LiDAR parameters

### Navigation Tuning
- **SLAM**: `shrek_navigation/config/slam_params.yaml`
- **AMCL**: `shrek_navigation/config/amcl_params.yaml`
- **Nav2**: `shrek_navigation/config/nav2_params.yaml`

## 📁 Directory Structure

```
shrek_ros2_ws/
├── src/
│   ├── shrek_essentials/      # Robot description and configs
│   ├── shrek_bringup/          # Launch files
│   ├── shrek_navigation/       # SLAM, AMCL, Nav2
│   ├── shrek_perception/       # Future: cameras, detection
│   └── shrek_manipulation/     # Future: arms, grippers
└── README.md
```

## 🎯 Future Development

- [ ] Add camera sensors to robot URDF
- [ ] Implement object detection in `shrek_perception`
- [ ] Integrate robotic arm in `shrek_manipulation`
- [ ] Add Gazebo simulation support
- [ ] Implement advanced path planning algorithms

## 📝 License

MIT

## 👤 Maintainer

Shrikar
