# Installing ctx on a WLAN Pi Go

1. On your host machine, download wlanpi-ctx debian file for bullseye:

cd ~/Downloads
wget --content-disposition "https://packagecloud.io/wlanpi/main/packages/debian/bullseye/wlanpi-ctx_1.0.0_arm64.deb/download.deb?distro_version_id=207"

2. Connect the WLAN Pi to the host machine via USB-C to C cable, and boot it up.

3. SCP the Debian package to your WLAN Pi:

cd ~/Downloads
scp wlanpi-ctx_1.0.0_arm64.deb wlanpi@169.254.42.1:/home/wlanpi

3. Install the Debian package via SSH

SSH to Pi:
ssh wlanpi@169.254.42.1

Run:
sudo apt install -y /home/wlanpi/wlanpi-ctx_1.0.0_arm64.deb"

4. Run ctx with debugging enabled via SSH

SSH to Pi (skip if already done):
ssh wlanpi@169.254.42.1

Run:
sudo ctx --debug