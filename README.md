# AntAlmanac Notification Transmission System - Currently underproduction

AntAlmanac Notification Transmission System (AANTS) is a tool to notify AntAlmanac users when a course either opens or waitlisted.

This system makes use of async functionality to reduce time spent on webrequests and dispatching emails by asynchronously executing multiple webrequests or email dispatches.

## API Access

refer to AntAlmanac internal documentation

## Installation and setup

### Requirements

* MongoDB
* Python 3.7 (other versions unsupported)
* Linux System

NOTE: Other versions of python may work but have not been tested. AANTS may also work on other operating systems but was developed, tested, and intended for running on linux. Other operating systems are not supported.

### Create config.py

This system requires multiple setup variables, refer to AntAlmanac internal documentation

#### Create a python virtual environment

**NOTE:** check python version to confirm it is python 3.7+ you may need `python3`

`python -m venv env`

Then activate your environment with 

`source env/bin/activate`

Install requirements

`pip install -r requirements.txt`

## Running AANTS

`source env/bin/activate`

`python dispatcher.py --run`

This will run the dispatcher in production mode. When not in production mode the dispatcher will only check for notifications once. To continue polling for notifications it *must be run in production mode*

**NON PRODUCTION MODE**

`python dispatcher.py`

