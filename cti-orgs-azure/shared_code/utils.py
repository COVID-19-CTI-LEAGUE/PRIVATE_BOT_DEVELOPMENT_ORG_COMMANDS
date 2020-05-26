import logging
import os
import sys
import json
import hmac
import hashlib
import re

import requests
import re
import os
import traceback

from urllib.parse import parse_qs
from slack import WebClient

slack_client = WebClient(token=os.environ['SLACK_API_TOKEN'])

def verify_slack_request(slack_signature=None, slack_request_timestamp=None, request_body=None):
    ''' Form the basestring as stated in the Slack API docs. We need to make a bytestring. '''
    basestring = f'v0:{slack_request_timestamp}:{request_body}'.encode('utf-8')
    
    ''' Make the Signing Secret a bytestring too. '''
    slack_signing_secret = os.environ['SLACK_SIGNING_SECRET']
    slack_signing_secret = bytes(slack_signing_secret, 'utf-8')
    
    ''' Create a new HMAC 'signature', and return the string presentation. '''
    my_signature = 'v0=' + hmac.new(slack_signing_secret, basestring, hashlib.sha256).hexdigest()
    
    ''' Compare the the Slack provided signature to ours.
    If they are equal, the request should be verified successfully.
    Log the unsuccessful requests for further analysis
    (along with another relevant info about the request). '''
    if hmac.compare_digest(my_signature, slack_signature):
        return True
    else:
        logging.warning(f'Verification failed. my_signature: {my_signature}')
        return False

def get_slack_profile(user_id):
    contact_info = {}
    try:
        resp=slack_client.users_profile_get(user=user_id)
        if resp['ok']:
            contact_info= {
                'full_name' :   resp['profile']['real_name'],
                'display_name' :  resp['profile']['display_name'],
                'title' :  resp['profile']['title']
                }
        return contact_info
    except:
        pass
    return None

def build_response(message):
    resp = { "response_type" : "ephemeral",
            "text" : message,
            "type" : "mrkdwn"
            }
    return resp

def add_noaction_modal_section(title, trigger_id):
    resp = {
        'trigger_id': trigger_id,
        'type': 'modal',
        'title':{
            'type': 'plain_text',
            'text': title
        },
        'close': {
            'type': 'plain_text',
            'text': 'Ok'
        }
    }

    return resp

def add_fields_section(fields, plain_text=True):
    sections = []
    section = {
        'type' : 'section',
        'fields' : []
    }

    type = 'plain_text'

    if not plain_text:
        type = 'mrkdwn'

    index = 0
    for field in fields:
        if index > 0 and index % 10 == 0:
            sections.append(section)
            section = {
                'type' : 'section',
                'fields' : []
            }

        section['fields'].append({
            'type' : type,
            'text' : field
        })

        index += 1
    sections.append(section)
    return sections

def add_mrkdwn_section(text):
    section = {
        'type' : 'section',
        'text' : {
            'type' : 'mrkdwn',
            'text' : text
        }
    }

    return section

def is_valid_email(email):
    regex = '^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$'
    return re.search(regex, email) or 'mailto' in email

def get_slack_command(req):
    '''Verify the request is a valid Slack Slash Command'''
    request_body = parse_qs(req.get_body())   
    response_url = request_body.get(b'response_url')
    response_url = response_url[0].decode('ASCII')
    user_id = request_body.get(b'user_id')
    user_id = user_id[0].decode('ASCII')
    trigger_id = request_body.get(b'trigger_id')
    trigger_id = trigger_id[0].decode('ASCII')

    try:
        org = request_body.get(b'text')
        org = org[0].decode('ASCII')
        return (response_url, trigger_id, user_id, org)
    except TypeError:
        org = ''
        return (response_url, trigger_id, user_id, org)


def extract_user_id(escaped_str):
    #<@UV4CEG4QZ|warfieldn>
    regex = '^<\@(.*)\|.*>$'
    m = re.match(regex, escaped_str)

    if m:
        return m.group(1)