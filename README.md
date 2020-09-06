# AntAlmanac Notification Transmission System - Currently underproduction

AntAlmanac Notification Transmission System (AANTS) is a tool to notify AntAlmanac users when a course either opens or waitlisted.

This system makes use of async functionality to reduce time spent on webrequests and dispatching emails by asynchronously executing multiple webrequests or email dispatches.

**NOTE:** This system is not meant to be modified and ran independently. AANTS is made to benefit all UCI students by being a public tool for all. Webscrapers can stress webservers and cause issues if not adhering to rate limits or if numerous webscrapers are hitting the same site. For this reason AntAlmanac does not approve of this system being used independently and would discourage you from doing so. If you would like to add improvements you can fork and submit pull requests.

## What AANTS does

AANTS attempts to chunk all notification codes to efficiently batch process courses that students have requested. An optimizer is run to find the max interval for a course term.

For any course code interval the total amount of codes is less than 900 (the max return of codes for WebSoc.

Length(A<sub>i</sub> to B<sub>j</sub>) < 900

These batch interval requests are set to be rate limited to lessen the strain of AANTS on WebSoc.

Once codes are chunked we request a course code interval from websoc and process the batch of codes for course statuses we are monitoring. We then dispatch notifications for courses that have `Open` or `Waitlist` status.

## API Access

Refer to AntAlmanac internal documentation

## Installation and setup

### Requirements

* MongoDB
* Python 3.7 (other versions unsupported)
* Linux System

NOTE: Other versions of python may work but have not been tested. AANTS may also work on other operating systems but was developed, tested, and intended for running on linux. Other operating systems are not supported.

### Create config.py

This system requires multiple setup variables, refer to AntAlmanac internal documentation

#### Create a python virtual environment

Create a virtual environment of your choice and active it then install requirements.

`pip install -r requirements.txt`

## Running AANTS

`python dispatcher.py --run`

This will run the dispatcher in production mode. When not in production mode the dispatcher will only check for notifications once. To continue polling for notifications it *must be run in production mode*

**NON PRODUCTION MODE**

`python dispatcher.py`

