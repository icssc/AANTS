# PSL
import urllib.parse
import asyncio
import logging
import time
import sys
import os
# THIRD PARTY
import boto3
import pymongo
import random
import requests

# PROJECT

import chunking
import constants
import fetching
import exceptions
from dotenv import load_dotenv

load_dotenv()

# PERSISTENT GLOBALS
db = pymongo.MongoClient(os.getenv("MONGODB_URI"))[os.getenv("DB_NAME")]
aws = boto3.client(
    "sns",
    aws_access_key_id=os.getenv("AWS_ACCESSKEY"),
    aws_secret_access_key=os.getenv("AWS_SECRECTKEY"),
    region_name="us-west-2"
)

# chunks
chunks = None

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# create a file handler
handler = logging.FileHandler('logs/dispatcher.log')
handler.setLevel(logging.INFO)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
handler.setFormatter(formatter)

# add the file handler to the logger
logger.addHandler(handler)


# FUNCTIONS

def shorten(long_url: str) -> str:
    """Uses tinyurl to shorten long urls"""

    try:
        url = f'{constants.TINY_URL_API}?{urllib.parse.urlencode({"url": long_url})}'
        res = requests.get(url)
        # print("LONG URL:", long_url)
        # print("SHORT URL:", res.text)
        return res.text if len(res.text) < 50 else long_url
    except requests.RequestException:
        return long_url


async def dispatch(statuses: dict, notification_codes: dict, debug: bool = False) -> dict:
    """
        Takes each status and builds a dispatcher

        Args
            statuses: dictionary of all statuses
            {
                'OPEN' : [<str_codes>, ...],
                'Waitl' : [<str_codes>, ...],
                ...
            }

            notification_codes: dictionary of the codes and their related information
            {
                <str:sectionCode> : {
                    'phoneNumbers' : [<str:numbers>...],
                    'courseTitle' : <str:class_name>
            }

        Return
            dict of all dispatched codes and info
            {
                <str:sectionCode> : {
                    'phoneNumbers' : [<str:numbers>...]
            }
    """
    # print('Statuses\n', statuses)
    # print('Notifications\n', notification_codes)

    open_codes = {}

    for code in statuses['open']:
        open_codes[code] = notification_codes[code]
    if constants.DISPATCH:
        start = time.time()
        send_text_messages(open_codes, 'open')
        logger.info(f'DISPATCH OPEN SMS TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

    waitl_codes = {}

    for code in statuses['waitl']:
        waitl_codes[code] = notification_codes[code]
    if constants.DISPATCH:
        start = time.time()
        send_text_messages(waitl_codes, 'waitl')
        logger.info(f'DISPATCH WAITL SMS DISPATCH TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

    # back time complexity we ignore
    completed = open_codes
    completed.update(waitl_codes)
    return completed


def format_content(status: str, course_title: str, code: str, phone_number: str = '') -> str:
    """
        Contructs the message content for a text message based on status

        Args
            status: status of the course
            course_title: name of the course
            code: code of the course
        Return
            string content for the body of the text message
    """

    webreg_url = f"{constants.WEBSOC}?{urllib.parse.urlencode([('YearTerm', constants.TERM), ('CourseCodes', code)])}"

    params = f'{code}/{course_title}/{phone_number}'
    add_back_url = f'{os.getenv("API_URL")}/notifications/addBackNotifications/{urllib.parse.quote(params)}'

    webreg_url = shorten(webreg_url)
    add_back_url = shorten(add_back_url)

    if status == 'open':
        msg = f'Space opened in {course_title}. Code: {code}'
    if status == 'waitl':
        msg = f'Waitlist opened for {course_title}. Code: {code}'

    return f"""
AntAlmanac:
{msg} ({webreg_url})
To add back to the watchlist: {add_back_url}"""


def send_text_messages(phone_list: dict, status: str):
    """
        Sends text messages
    """
    for code, info in phone_list.items():
        for num in info['phoneNumbers']:
            msg = format_content(status, info['courseTitle'], code, num)
            aws.publish(PhoneNumber=f"+1{num}", Message=msg)


def remove_registered_notifications(completed_codes: dict, debug: bool = False) -> None:
    """
        Accesses the database and removes all the data for a completed notification dispatch

        Args
            completed_notifications: dictionary of codes and related information to remove due to successful dispatch
            {
                <sectionCode> : {
                    'phoneNumbers' : [list of phone numbers],
                }, ...
            }
    """
    if constants.DISPATCH:
        for code, info in completed_codes.items():
            db['notifications'].update_many(
                {'sectionCode': code},
                {'$pull': {'phoneNumbers': {'$in': info['phoneNumbers']}}}
            )


# MAIN

async def main(is_looping: bool = False):
    logger.info('GETTING ALL SECTION CODES...')
    all_course_codes = sorted(chunking.get_all_codes(constants.TERM))
    logger.info(f'GETTING ALL SECTION CODES FINISHED: GOT {len(all_course_codes)} SECTION CODES')

    while True:
        start = time.time()
        notification_codes = fetching.fetch_notification_codes(db)
        logger.info(f'FETCH TIME = {(time.time() - start):.4f}')

        if len(notification_codes) == 0:
            await asyncio.sleep(600)
            continue

        start = time.time()
        codes = notification_codes.keys()
        chunks_for_all_course_codes = chunking.get_chunks_for(codes, all_course_codes)

        logger.info(f'Num chunks: {len(chunks_for_all_course_codes)})')

        start = time.time()
        try:
            statuses = fetching.fetch_code_statuses(chunks_for_all_course_codes)
        except (requests.exceptions.ConnectionError, exceptions.HttpResponseError) as e:
            logger.error('ERROR: WebSoc fetch connection error', f'\n {e}')
            time.sleep(600)
            continue
        logger.info(f'WEBSOC FETCH TIME = {(time.time() - start):.4f}')

        start = time.time()
        completed_notifications = await dispatch(statuses, notification_codes)
        logger.info(f'TOTAL DISPATCH TIME = {(time.time() - start):.4f}')

        remove_registered_notifications(completed_notifications)
        time.sleep(random.randint(20, 30))

        if not is_looping:
            break


if __name__ == '__main__':
    try:
        production = sys.argv[1] == '--run'
    except IndexError:
        production = False

    if production:
        print('RUNNING PRODUCTION')
    else:
        print('RUNNING DEVELOPMENT')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(production))
