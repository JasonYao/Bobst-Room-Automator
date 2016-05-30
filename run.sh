#!/usr/bin/env bash

set -e

# Goes into the folder
cd ~/projects/Bobst-Room-Automator/

# If running on a Raspberry Pi, uncomment the line below
#export DISPLAY=:0

# If running on a linux system without a graphical display (e.g. a fresh Digital Ocean droplet, or an Amazon Web Services VPS)
# Install vnc first, then uncomment the line below
#export DISPLAY=localhost:1

# If you're using a virtualenv (highly recommended), uncomment and replace the source destination below
#source .env/bin/activate

# Checks for dependencies
pip install -r requirements.txt

# Runs the fucking python file
python Automator.py

# Deactivates from the virtualenv
#deactivate
