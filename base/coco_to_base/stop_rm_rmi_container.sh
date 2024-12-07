#!/bin/bash

# Set the container name as a variable
CONTAINER_NAME="coco_to_base"

# Stop the container
echo "Stopping container $CONTAINER_NAME..."
docker stop $CONTAINER_NAME

# Remove the container
echo "Removing container $CONTAINER_NAME..."
docker rm $CONTAINER_NAME

# Remove the image
echo "Removing image $CONTAINER_NAME..."
docker rmi $CONTAINER_NAME

echo "Done!"