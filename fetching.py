from collections import defaultdict
from bs4 import BeautifulSoup
from requests.exceptions import ReadTimeout
from exceptions import HttpResponseError

import random
import sys
import pymongo
import constants
import time
import exceptions
import requests
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def fetch_code_statuses(chunks: [[str]], debug: bool = False) -> {str: [str]}:
    """
        Fetches the status of all codes
        TODO: look into fetching all chunks asynchronously and then merging the sets

        Args:
            chunks: nested list of chunked codes
                [ ['00000', '00001', '00002', '00003'], ['00004', ..., ...], ...]
            debug: if true, print debug info to console

        Return
            TODO: look into using a set instead of a list
            dictionary of statuses and their codes as a list
            {
                'status' : ['00000', '00001', '00002', '00003']
            }
    """
    begin = time.time()
    statuses = defaultdict(list)

    for chunk in chunks:
        if debug:
            print('Chunk:', chunk)

        chunk_string = f'{chunk[0]}-{chunk[-1]}' if len(chunk) > 8 else ','.join(chunk)
        params = {
            'YearTerm': constants.TERM,
            'CourseCodes': chunk_string,
            'CancelledCourses': 'Include',
            'Submit': 'XML'
        }
        begin_rsp = time.time()

        try:
            soup = fetch_websoc(params)
        except exceptions.HttpResponseError as e:
            print(e, file=sys.stderr)
            logger.error('ERROR: chunk request failed')
            continue
        except ReadTimeout as e:
            print(e, file=sys.stderr)
            logger.error('ERROR: chunk timed out')
            continue

        for item in soup.find_all('section'):
            cc = item.find('course_code').text

            if cc in chunk:
                status = item.find('sec_status').text.lower()
                if debug: print(f'Chunk({cc}): ', status)
                statuses[status].append(cc)

    end = time.time()

    return statuses


def fetch_notification_codes(db: pymongo.MongoClient, debug: bool = False) -> dict:
    """
        Fetches all codes to check for notification status

        Args
            debug: flag to enable debugging code

        Return
            list of dictionaries of course codes
            [{
                'sectionCode' : {
                    'phoneNumbers' : [numbers...],
                    'courseTitle' : 'class name'
                }
            }, ...]
    """
    notifications = {}

    # Aggregation to filter out codes that have no registered notification methods
    # Collect lengths of arrays and filter codes with both <= 0
    result = db['notifications'].aggregate(
        [
            {'$project': {'_id': 0, 'sectionCode': 1, 'courseTitle': 1, 'phoneNumbers': 1,
                          'phoneNumbers_sz': {'$size': '$phoneNumbers'}}},

            {'$match': {'$or': [
                {'phoneNumbers_sz': {'$gt': 0}}
            ]}}
        ]
    )

    for doc in result:
        notifications[doc['sectionCode']] = {
            'phoneNumbers': doc['phoneNumbers'],
            'courseTitle': doc['courseTitle']
        }

    return notifications


def fetch_websoc(params: dict, debug: bool = False) -> BeautifulSoup:
    """
        Fetches a WebSOC page
        Args
            params: parameters to encode in the url
            example
            {
                'YearTerm' : '2020-92',
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
        'User-Agent': random.choice(constants.USER_AGENT_HEADERS),
    }

    begin_rsp = time.time()
    rsp = requests.get(constants.WEBSOC, params=params, headers=headers, timeout=5)

    if rsp.status_code < 300 and debug:
        print(f'>>> Response code: {rsp.status_code}')
    elif 300 <= rsp.status_code < 400 and debug:
        print(f'>>> Redirection: {rsp.status_code}')
    elif rsp.status_code >= 400:
        raise HttpResponseError(f'WebSoc errored with status code {rsp.status_code}')
    elif rsp.headers.get('Content-Length') == '0':
        raise HttpResponseError(f'WebSoc returned empty page')

    if debug: print(rsp)

    soup = BeautifulSoup(rsp.content, 'lxml')

    end_rsp = time.time()

    return soup
