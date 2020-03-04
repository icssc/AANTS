# PSL

from collections import defaultdict
from email.message import EmailMessage
import urllib.parse

import aiosmtplib
import asyncio
import logging
import time
import random
import sys

# THIRD PARTY
import lxml
import boto3
import pymongo
from bs4 import BeautifulSoup

import requests

# PROJECT
import config

# CONSTANTS
db = pymongo.MongoClient(config.MONGODB_URI).aants_db
aws = boto3.client(
    "sns",
    aws_access_key_id=config.AWS_ACCESSKEYID,
    aws_secret_access_key=config.AWS_SECRECTKEY,
    region_name="us-east-1"
)
# db['notifications'].insert_one({
#         'code': '',
#         'email': [''],
#         'sms': [''],
#         'name': ''
#     })

# NOTE: Must update each term
# TODO: Find a way to dynamically update without manual intervention
_TERM = '2020-14'
_WEBSOC = 'https://www.reg.uci.edu/perl/WebSoc?'
_OPEN_SUBJECT = "[AntAlmanac Class Notification] Class opened"
_WAIT_SUBJECT = "[AntAlmanac Class Notification] Class waitlisted"
_CNCL_SUBJECT = "[AntAlmanac Class Notification] Class cancelled"
_DISPATCH = True

# TODO: Determine if we want to rotate headers
_USER_AGENT_HEADERS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 8.0.0;) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.99 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/80.0.3987.95 Mobile/15E148 Safari/605.1',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/73.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) Gecko/20100101 Firefox/73.0',
    'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/73.0',
    'Mozilla/5.0 (Android 8.0.0; Mobile; rv:61.0) Gecko/61.0 Firefox/68.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/22.0 Mobile/16B92 Safari/605.1.15'
]

_CHUNK_SAFE = 900
_CHUNK_OPTIMIZED = -1
TINY_URL_API = "http://tinyurl.com/api-create.php"


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


# EXCEPTIONS

class HttpResponseError(Exception):
    def __init__(self, message):
        super().__init__(message)


# FUNCTIONS

def shorten(long_url: str) -> str:
    """Uses tinyurl to shorten long urls"""

    try:
        url = TINY_URL_API + "?" + urllib.parse.urlencode({"url": long_url})
        res = requests.get(url)
        # print("LONG URL:", long_url)
        # print("SHORT URL:", res.text)
        return res.text if len(res.text) < 50 else long_url
    except Exception as e:
        return long_url


def fetch_notification_codes(debug: bool = False) -> dict:
    """
        Fetches all codes to check for notification status

        Args
            debug: flag to enable debugging code

        Return
            list of dictionaries of course codes
            [{
                'code' : {
                    'email' : [emails...],
                    'sms' : [numbers...],
                    'name' : 'class name'
                }
            }, ...]
    """
    notifications = {}
    result = db['notifications'].find({}, {'_id': 0})
    for doc in result:
        notifications[doc['code']] = {
            'email': doc['email'],
            'sms': doc['sms'],
            'name': doc['name']
        }

    return notifications


def chunk_codes(codes: list, optimize: bool = False, debug: bool = False):
    """
        Chunks codes into ranges compatiable with websoc

        currently only chunks into ranges of 900 max
        TODO: build analysis tool for websoc to find optimized chunking range

        Args
            codes: list of course codes to chunk, codes should be sorted from min to max
            optimize: TODO: optimize flag for wider range than 900

        Return
            nested lists of code chunks
            [ [1, 2, 3, 4], [7, 10, 24], ... ]
    """
    chunks = []

    start = None
    end = None
    for idx, code in enumerate(codes):
        code = int(code)

        if debug: print()

        if start is None:
            end = start = (idx, code)
            if debug: print('Starting', start, end)
            # continue
        elif code - start[1] <= _CHUNK_SAFE:
            end = (idx, code)
            if debug: print('New end', end)
            # continue
        else:
            if debug: print('Chunking', codes[start[0]:idx])
            chunks.append(codes[start[0]:idx])
            start = end = (idx, code)

        # print(start, end)

    # capture final chunk if not caught by for loop
    if end[0] == len(codes) - 1:
        chunks.append(codes[start[0]:end[0] + 1])

    return chunks


def fetch_websoc(params: dict, debug: bool = False) -> BeautifulSoup:
    """
        Fetchs a websoc live page
        Args
            params: parameters to encode in the url
            example
            {
                'YearTerm' : '2019-92',
                'CourseCodes' :'30000-32000',
                'CancelledCourses' : 'Include',
                'Submit' : 'XML'
            }

        Raises
            HttpResponseError: GET return status code >= 400

        Returns
            a BeautifulSoup object
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0',
    }

    begin_rsp = time.time()
    rsp = requests.get(_WEBSOC, params=params, headers=headers)

    if rsp.status_code < 300 and debug:
        print(f'>>> Response code: {rsp.status_code}')
    elif 300 <= rsp.status_code < 400 and debug:
        print(f'>>> Redirection: {rsp.status_code}')
    elif rsp.status_code >= 400:
        raise HttpResponseError(f'Websoc status code {rsp.status_code}')

    if debug: print(rsp)

    soup = BeautifulSoup(rsp.content, 'lxml')

    end_rsp = time.time()

    if debug: print_time(begin_rsp, end_rsp, '>>> Fetch websoc time:')
    return soup


def fetch_code_statuses(chunks: list, debug: bool = False):
    """
        Fetches the status of all codes
        TODO: look into fetching all chunks asynchronously and then merging the sets

        Args:
            chunked_codes: nested listof chunked codes
                [ [1, 2, 3, 4], [7, 10, 24], ...]

        Return
            TODO: look into using a set instead of a list
            dictionary of statuses and their codes as a list
            {
                'status' : [codes]
            }
    """
    begin = time.time()
    statuses = defaultdict(list)

    for chunk in chunks:
        if debug: print('Chunk:', chunk)
        params = {
            'YearTerm': _TERM,
            'CourseCodes': f'{chunk[0]}-{chunk[len(chunk) - 1]}',
            'CancelledCourses': 'Include',
            'Submit': 'XML'
        }
        begin_rsp = time.time()
        ######## OLD ##########
        # rsp = requests.get(_WEBSOC, params=params)
        # end_rsp = time.time()

        # if debug:
        #     print(rsp)
        #     print_time(begin_rsp, end_rsp, '>>> Get response time:')
        # soup = BeautifulSoup(rsp.content, 'lxml')
        #######################
        try:
            soup = fetch_websoc(params)
        except HttpResponseError as e:
            print(e)
            print('ERROR: chunk request failed', file=sys.stderr)
            continue

        # if debug: print(soup)

        begin_it = time.time()
        for item in soup.find_all('section'):
            cc = item.find('course_code').text
            # if debug: print(cc)
            if cc in chunk:
                status = item.find('sec_status').text.lower()
                if debug: print(f'Chunk({cc}): ', status)
                statuses[status].append(cc)
        end_it = time.time()
        # print_time(begin_it, end_it, '>>> Iteration time:')

    end = time.time()
    if debug: print_time(begin, end, '>>> Fetch status time:')
    return statuses


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
                <str:code> : {
                    'email' : [<str:email>...],
                    'sms' : [<str:numbers>...],
                    'name' : <str:class_name>
            }

        Return
            dict of all dispatched codes and info
            {
                <str:code> : {
                    'email' : [<str:email>...],
                    'sms' : [<str:numbers>...]
            }
    """
    # print('Statuses\n', statuses)
    # print('Notifications\n', notification_codes)

    open_codes = {}
    for code in statuses['open']:
        open_codes[code] = notification_codes[code]
    if _DISPATCH:
        start = time.time()
        await send_emails(open_codes, 'open')
        logger.info(f'DISPATCH OPEN EMAIL TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

        start = time.time()
        send_text_messages(open_codes, 'open')
        logger.info(f'DISPATCH OPEN SMS TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

    waitl_codes = {}
    for code in statuses['waitl']:
        waitl_codes[code] = notification_codes[code]
    if _DISPATCH:
        start = time.time()
        await send_emails(waitl_codes, 'waitl')
        logger.info(f'DISPATCH WAITL EMAIL TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

        start = time.time()
        send_text_messages(waitl_codes, 'waitl')
        logger.info(f'DISPATCH WAITL SMS DISPATCH TIME (batch:{len(open_codes)}) = {(time.time() - start):.4f}')

    # back time complexity we ignore
    completed = open_codes
    completed.update(waitl_codes)
    return completed


def format_content(status: str, name: str, code: str, short: bool, sms: str='', email: str='') -> str:
    """
        simply used to format the message content for an email based on status

        Args
            status: status of the course
            name: name of the course
            code: code of the course
            short: whether to shorten the links or not
        Return
            string content for the body of the email
    """

    webreg_url = _WEBSOC + urllib.parse.urlencode([('YearTerm', _TERM), ('CourseCodes', code)])
    add_back_url = config.API_URL + '?' + urllib.parse.urlencode(
        {'code': code,
         'name': name,
         'sms': sms,
         'email': email,
         'command': 'update'})

    if short:
        webreg_url = shorten(webreg_url)
        add_back_url = shorten(add_back_url)

    if status == 'open':
        msg = f'Space opened in {name}. Code: {code}'
    if status == 'waitl':
        msg = f'Waitlist opened for {name}. Code: {code}'
    return f"""
AntAlmanac:
{msg} ({webreg_url})
To add back to the watchlist: {add_back_url}"""


async def send_emails(mail_list: dict, status: str):
    """
        sends emails out for a specific status using gmail smtp

        Args:
            mail_list: dict of codes mapped to emails and names
            {
                'code' : {
                    email : [],
                    name : 'class'
                },
                ...
            }
            status: status of the codes in the mailing list
    """
    _FROM = 'antalmanac@gmail.com'

    _MESSAGES = []
    for code, info in mail_list.items():
        for email in info['email']:
            msg = EmailMessage()
            msg.set_content(format_content(status, info['name'], code, False, sms="", email=email))
            msg['To'] = email
            msg['From'] = _FROM

            if status == 'open':
                msg['Subject'] = _OPEN_SUBJECT
            elif status == 'waitl':
                msg['Subject'] = _WAIT_SUBJECT

            # msg['Bcc'] = ','.join(info['email'])
            _MESSAGES.append(msg)

    server = aiosmtplib.SMTP(
        hostname='smtp.gmail.com',
        port=587,
        start_tls=True,
        username=config.EMAIL_USERNAME,
        password=config.EMAIL_PASSWORD
    )

    await server.connect()
    tasks = [server.send_message(msg) for msg in _MESSAGES]
    await asyncio.gather(*tasks, return_exceptions=True)
    await server.quit()


def send_text_messages(phone_list: dict, status: str):
    """
        Sends text messages
    """
    _MESSAGES = []
    for code, info in phone_list.items():
        for num in info['sms']:
            msg = format_content(status, info['name'], code, True, sms=num)
            aws.publish(PhoneNumber=f"+1{num}", Message=msg)


def remove_registered_notifications(completed_codes: dict, debug: bool = False) -> None:
    """
        Accesses the database and removes all the data for a completed notification dispatch

        Args
            completed_notifications: dictionary of codes and related information to remove due to successful dispatch
            {
                <code> : {
                    'email' : [list of emails],
                    'sms' : [list of sms numbers]
                }, ...
            }
    """
    for code, info in completed_codes.items():
        # print(code)
        # print(info['email'])
        db['notifications'].update_one(
            {'code': code},
            {'$pull': {'email': {'$in': info['email']},
                       'sms': {'$in': info['sms']}
                       }}
        )


def print_time(begin, end, msg):
    elapsed = f'{(end - begin):.4f}'
    print(f'{msg:<30}: {elapsed:<12}')


def average_chunk_size(chunks: list) -> float:
    """
        function to get average chunk size for analysis
    """
    # sizes = []
    # for chunk in chunks:
    #     sizes.append(len(chunk))
    sizes = [len(chunk) for chunk in chunks]
    return sum(sizes) / len(sizes)


# MAIN

async def main(is_looping: bool = False):
    while True:
        start = time.time()
        notification_codes = fetch_notification_codes()
        logger.info(f'FETCH TIME = {(time.time() - start):.4f}')

        if len(notification_codes) == 0:
            await asyncio.sleep(180)
            continue

        start = time.time()
        chunks = chunk_codes(sorted(list(notification_codes)))
        logger.info(f'CHUNKING TIME (chunks:{len(chunks)}, avg_chunk_size:{average_chunk_size(chunks)}) = {(time.time() - start):.4f}')

        start = time.time()
        statuses = fetch_code_statuses(chunks)
        logger.info(f'WBESOC FETCH TIME = {(time.time() - start):.4f}')

        start = time.time()
        completed_notifications = await dispatch(statuses, notification_codes)
        logger.info(f'TOTAL DISPATCH TIME = {(time.time() - start):.4f}')

        remove_registered_notifications(completed_notifications)
        # print('Waiting')
        # await asyncio.sleep(random.randint(10, 15)) # Useless??????
        time.sleep(random.randint(10, 15))
        # print('Waited')
        if not is_looping:
            break


if __name__ == '__main__':
    try:
        production = sys.argv[1] == '--run'
    except IndexError:
        production = False

    if production:
        print('RUNNING PRODUCTION')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(production))
