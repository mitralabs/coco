# Docker Container to receive recordings from coco.
This container contains a FastAPI App which has an Endpoint to receive .wav files and stores them as blobs in an attached sqlLite Database and/or as plain files.

# ToDo
- [ ] Write instructions for the .env file and include a .env.template
- [ ] Include a "all files transmitted" message that coco sends to base.



## Step by Step instructions:
1. cd into this directory, if not already done.
2. set all environment variables
3. Build the docker image, using the configuration in the Dockerfile and run the container.
```
docker build -t coco_to_base .
```

4. Run the docker container
```
docker run -d -p 3030:8000 -v $(PWD)/app:/app -v $(PWD)/../_data:/data --name coco_to_base coco_to_base
```
Note: We are currently in dev mode. Once we reach a stable phase the images will have tags.

5. Now you can check whether the API is running correctly by visiting the site `http://localhost:3030`in your browser. (If you deploy on a remote machine, just exchange "localhost" with the IP-Adress of your machine). The container should reply with:
```
[{"status":"success","message":"Server is running"},200]
```


## Instructions if the files should go to the database
Set the env Variable "TO_DB" to true.

## Instructions if the files should be stored in a docker volume
Create a docker volume
```
docker volume create coco-database
```
Exchange the -v .../data flag with the latter -v flag in the docker run command
```
-v coco-database:/data
```

# Nice to know
### Docker flags:
- -d, running the container in detached mode.
- The port 8000 from the inside of the container is exposed on port 3030 on the outside of the container
- The /app directory is mounted as a volume so that the code can access it.
- The previously created docker volume is mounted as well under the path /data, so the code can access it also.
- restart=always, so that the container is restarted once changes are made.
- --rm, this flag to remove the container once its stopped. But, this is conflicting with --restart!**

### Container Logs
**Execute this command, to see the logs of the container**
```
docker logs -f name_of_container
```

### curl command to check the .wav endpoint
```
curl -X POST "http://cocobase.local:3030/uploadAudio" \
	-H 'X-API-Key: please_smile' \
	-H 'Content-Type: multipart/form-data' \
	-F file='@./audio_0_1.wav'
```

### You can use the shell script to stop the running container, remove it and remove the image also to rebuild a newer version of it.
1. Make it executable `chmod +x stop_rm_rmi_container.sh`
2. Run it `./stop_rm_rmi_container.sh`