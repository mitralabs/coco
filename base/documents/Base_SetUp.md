
# Starting fresh

## ToDo
- [ ] Generate a password (e.g. on [PW Generate](https://randompasswordgenerator.com/)) 30 characters should be sufficient.
- [ ] Don't Forget. If more people use Coco, the Coco_Connect SSID should be different -> Increasing Integers at the end.


## Start in the Raspberry Pi Imager on your machine
(If you don't have it yet, you can download it [here](https://www.raspberrypi.com/software/))
1. Choose your Raspberry Pi Model. We work with the "Raspberry Pi 5"
2. Choose the OS. We work with Other -> OS Lite 64 Bit
3. Choose the microSD Card you want to install the image on to.
4. Click on "next"
5. Click on "configure settings" (bzw. "Einstellungen bearbeiten")
	1. Choose a "hostname" // we use "cocobase"
	3. Choose a "name" and "password" // we use "mitralabs" & "please_smile!"
6. Click on the Tab "Services"/"Dienste" and activate "SSH" (only Password not with a Public Key)
7. That's it click "Save"/"Speichern" and maybe a few times yes. The Raspberry Imager should now write the firmware to the microSD card.

## Connect to the raspberry
Choose your favorite terminal and type in the following:
```
ssh mitralabs@cocobase.local
```
Then enter the password. (Note: If you chose a different hostname and password, you need to enter this here as well.)

## Update apt and grab git
Run the following commands.

```
sudo apt update
sudo apt upgrade
sudo apt-get install git-all
sudo reboot 
```

# Install docker
(Note: This might be outdated. Check the official docker documentation for an updated version. We might just link it here.)
1. Set Up Docker's apt Repository
```
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
```

2. Install the docker packages
```
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

3. Verify that the installation was successful by running the hello-world container
```
sudo docker run hello-world
```

4. Add your current username as a root for docker. Then you don't need to `sudo`every docker command
```
sudo usermod -aG docker mitralabs 
newgrp docker
```

## Configuring the Pi as Access Point (only needed, if you don't use the offline version of the coco firmware)
The bottom line will enable the Pi as a hotspot, after turning on the wifi
```
sudo nmcli radio wifi on
sudo nmcli device wifi hotspot ssid coco_connect password please_smile
```

(Note: If you want to chose a different SSID and/or Password. You need to exchange it with 'coco_connect' and 'please_smile' above.)

The access point is closed every time the pi reboots. Therefore we add the line above as a cronjob. (Note: You might need to chose a texteditor. We use nano.)
```
sudo crontab -e
```

And insert this at the bottom of the file. Exit the editor and save the file.
```
# Establishing Access Point on reboot
@reboot sleep 30 && nmcli device wifi hotspot ssid coco_connect password please_smile
```
-> Since it might be the case, that the network functions are not all up during the booting phase, we add a sleep for 30s until the command is executed, to make sure that everything works.