# AntAlmanac Notification Transmission System - Currently underproduction

AntAlmanac Notification Transmition System (AANTS) is a tool to notify AntAlmanac users when a course either opens, waitlisted, or cancelled.

**NOTE**: out of date, moving from mongo to dynamodb

*Add more details here*

## API Access

*Add API details here*

## Installation and setup

### Requirements

* MongoDB
* Python 3.7 (other versions unsupported)
* Linux System

NOTE: Other versions of python may work but have not been tested. AANTS may also work on other operating systems but was developed, tested, and intended for running on linux. Other operating systems are not supported.

#### Install MongoDB

`sudo apt update`

`sudo apt install -y mongodb`

Gather information for your database with 

`mongo --eval 'db.runCommand({ connectionStatus : 1 })'`

__Useful commands__

`sudo systemctl status mongodb`

`sudo systemctl stop mongodb`

`sudo systemctl start mongodb`

`sudo systemctl restart mongodb`

#### Create a python virtual environment

