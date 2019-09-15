# PSL

from collections import defaultdict
from email.message import EmailMessage

import aiosmtplib
import asyncio
import time

# THIRD PARTY

from bs4 import BeautifulSoup
from pymongo import MongoClient

import requests
import lxml

# PROJECT

import secret

# CONSTANTS

# NOTE: Must update each term
# TODO: Find a way to dynamically update without manual intervtion
_TERM = '2019-92'
_WEBSOC = 'https://www.reg.uci.edu/perl/WebSoc?'
_OPEN_SUBJECT = "[AntAlmanac Class Notification] Class opened"
_WAIT_SUBJECT = "[AntAlmanac Class Notification] Class waitlisted"
_CNCL_SUBJECT = "[AntAlmanac Class Notification] Class cancelled"
# TODO: add to hidden config file
_DB = MongoClient(secret._DATABASE_URL).admin


# EXCEPTIONS

class HttpResponseError(Exception):
    def __init__(self, message):
        super().__init__(message)

# FUNCTIONS

def print_time(begin, end, msg):
    elapsed = f'{(end - begin):.4f}'
    print(f'{msg:<30}: {elapsed:<12}')

def fetch_statuses(chunked_codes: list, debug: bool=False):
    """
        returns a dictionary of status where classes aren't closed
        {
            'open' : [codes],
            'closed' : [codes],
            'waitl' : [codes]
        }

        Args:
            chunked_codes: nested list of chunked codes
                [ [1, 2, 3, 4], [7, 10, 24], ...]
    """
    begin = time.time()
    statuses = defaultdict(list)

    for chunk in chunked_codes:
        if debug: print('Chunk:', chunk)
        params = {
            'YearTerm' : _TERM,
            'CourseCodes' : f'{chunk[0]}-{chunk[len(chunk) - 1]}',
            'CancelledCourses' : 'Include',
            'Submit' : 'XML'
        }
        begin_rsp = time.time()
        rsp = requests.get(_WEBSOC, params=params)
        end_rsp = time.time()
        
        if debug: 
            print(rsp)
            print_time(begin_rsp, end_rsp, '>>> Get response time:')
        soup = BeautifulSoup(rsp.content, 'lxml')
        # if debug: print(soup)

        begin_it = time.time()
        for item in soup.find_all('section'):
            cc = item.find('course_code').text
            # if debug: print(cc)
            if int(cc) in chunk:
                status = item.find('sec_status').text
                if debug: print(f'Chunk({cc}): ', status)
                statuses[status].append(cc)
        end_it = time.time()
        print_time(begin_it, end_it, '>>> Iteration time:')

    end = time.time()
    if debug: print_time(begin, end, '>>> Fetch status time:')
    return statuses

# Done
def chunk_codes(codes: list, optimize: bool=False, debug: bool=False):
    """
        chunks codes into ranges compatible with websoc

        currently chunks by range of 900
        TODO: run analysis on websoc to find more efficient chunking range

        Args:
            codes: list of course codes to chunk, codes should be sorted
            optimize: TODO: optimize flag for wider range than 900

        Return:
            nested lists of code chunks
            [ [1, 2, 3, 4], [7, 10, 24], ...]
    """
    _SAFE = 900
    _OPTIMIZED = -1
    chunks = []

    start = None
    end = None
    for idx, code in enumerate(codes):
        if debug: print()
        if start is None:
            end = start = (idx, code)
            if debug: print('Starting', start, end)
            # continue
        elif code - start[1] <= _SAFE:
            end = (idx, code)
            if debug: print('New end', end)
            # continue
        else:
            if debug: print('Chunking', codes[start[0]:idx])
            chunks.append(codes[start[0]:idx])
            start = end = (idx, code)
        print(start, end)

    # capture final chunk if not caught by for loop
    if end[0] == len(codes) - 1:
        chunks.append(codes[start[0]:end[0] + 1])
    
    return chunks

# In-progress, finish TODO
def fetch_relations(debug: bool=False) -> dict:
    """
        fetches code, name, notifiers
        
        Returns
            {
                'code' : {
                    'email' : [emails],
                    'sms' : [numbers],
                    'name' : 'class name'
                }
            }
    """
    begin = time.time()

    relations = defaultdict(dict)

    # TODO: modify to work with sms and email, add code if email or sms isnt empty
    for course in _DB.queue.find():
        if debug: print(course)
        # check if people to notify
        if len(course['email']) != 0:
            relations[course['code']]['email'] = course['email']
            relations[course['code']]['name'] = course['name']
    
    end = time.time()
    if debug: print_time(begin, end, '>>> Fetching codes took')

    return relations

# Done
def fetch_websoc(params: dict, debug: bool=False) -> BeautifulSoup:
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
    begin_rsp = time.time()
    rsp = requests.get(_WEBSOC, params=params)

    if rsp.status_code < 300 and debug:
        print(f'>>> Response code: {rsp.status_code}')
    elif rsp.status_code >= 300 and rsp.status_code < 400 and debug:
        print(f'>>> Redirection: {rsp.status_code}')
    elif rsp.status_code >= 400:
        raise HttpResponseError(f'Websoc status code {rsp.status_code}')

    if debug: print(rsp)

    soup = BeautifulSoup(rsp.content, 'lxml')

    end_rsp = time.time()

    if debug: print_time(begin_rsp, end_rsp, '>>> Fetch websoc time:')
    return soup

# In-progress, experiment with gmail API
async def send_emails(mail_list: dict, status: str):
    """
        sends emails out for a specific status
        TODO: implement with some emailing, gmail API or sendgrid
        
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
        msg = EmailMessage()
        msg.set_content(format_content(status, info['name'], code)) 
        msg['To'] = secret._EMAIL_USERNAME

        msg['From'] = _FROM
        if status == 'OPEN':
            msg['Subject'] = _OPEN_SUBJECT
        elif status == 'Waitl':
            msg['Subject'] = _WAIT_SUBJECT
        msg['Bcc'] = ','.join(info['email'])
        _MESSAGES.append(msg)
    server = aiosmtplib.SMTP(
        hostname='smtp.gmail.com',
        port=587,
        start_tls=True,
        username=secret._EMAIL_USERNAME,
        password=secret._EMAIL_PASSWORD
    )
    await server.connect()
    tasks = []
    # for msg
    # print(_MESSAGES)
    for msg in _MESSAGES:
        print(str(msg))
        tasks.append(server.send_message(msg))
    await asyncio.gather(*tasks)
    await server.quit()


    



#     tasks = []
#     loop = asyncio.get_event_loop()
#     for key in mailing:
#         tasks.append(send_emails(mailing[key], key))
#     loop.run_until_complete(asyncio.gather(*tasks))
    

def format_content(status, name, code):
    if status == 'OPEN':
        msg = f'Space opened in {name}. Code: {code}'
    if status == 'Waitl':
        msg = f'Waitlist opened for {name}. Code: {code}'
    return f"""
Hello User,
{msg}
    """

# TESTING FUNCTIONS

def mock_fetch_websoc(file_path: str) -> BeautifulSoup:
    """
        used to load an mock xml file of websoc results for unit testing
        Args:
            file_path: path to the mock xml
        
        Results:
            a BeautifulSoup object

    """
    with open(file_path, 'r') as f:
        whole = f.read()
        return BeautifulSoup(whole, 'lxml')

def mock_insert_notification():
    pass    

# MAIN



if __name__ == '__main__':
    pass
    # soup = fetch_websoc(params={
    #         'YearTerm' : _TERM,
    #         'CourseCodes' : f'34000-37000',
    #         'CancelledCourses' : 'Include',
    #         'Submit' : 'XML'
    #     }, debug=True)
    # print(soup)

    ##################
    # EMAIL TEST
    # test_list = {
    #     '420' : {
    #         'email' : ['yayeet', 'apatheticlamp@gmail.com','vacneyelk@gmail.com','nycoraxency@gmail.com','kavance@uci.edu'],
    #         'name' : 'Aslan\'s weed class'
    #     },
    #     '69' : {
    #         'email' : ['kavance@uci.edu', 'kavance@uci.edu','kavance@uci.edu'],
    #         'name' : 'Aslan\'s sex class'
    #     }
    # }
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(send_emails(test_list, 'OPEN'))
    ##################

#     names = ['kyle', 'nate', 'aslan', 'isoo', 'sid', 'nic', 'alexis', 'rafool']
#     from pprint import pprint
#     s = fetch_statuses(
#             [
#                 [34020, 34062, 35940, 35970, 36105, 36600, 36720, 37000]
#             ], 
#             debug=True
#         )
#     pprint(s)
#     import random
#     mailing = defaultdict(dict)
#     for status in s:
#         for code in s[status]:
#             # mailing[status] = {
#             #         code : {
#             #                 'name' : 'Dope Ass Class 420',
#             #                 'email' : []    
#             #             }
#             #     }
#             mailing[status][code] = {}
#             mailing[status][code]['name'] = 'Dope Ass Class 420'
#             mailing[status][code]['email'] = []
#             for _ in range(random.randint(1, 5)):
#                 mailing[status][code]['email'].append(
#                         names[ random.randint(0, len(names) - 1)]    
#                     )
#     pprint(mailing)
#     tasks = []
#     loop = asyncio.get_event_loop()
#     for key in mailing:
#         tasks.append(send_emails(mailing[key], key))
#     loop.run_until_complete(asyncio.gather(*tasks))


    # for status, codes in s.items():
    #     for code in codes:
    #         mailing[code] = {
    #                 'name' : 'Dope Ass Class 420',
    #                 'status' : status,
    #                 'email' : []  
    #             }
    #         for _ in range(random.randrange(0, 5)):
    #             mailing[code]['email'].append(
    #                     names[ random.randint(0, len(names) - 1) ]
    #                 )
    # pprint(mailing)


