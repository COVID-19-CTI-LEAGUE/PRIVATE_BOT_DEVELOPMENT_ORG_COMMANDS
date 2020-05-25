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

import azure.functions as func

from urllib.parse import parse_qs

from ..shared_code import db, utils


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    
    # Check for Slack Headers
    if 'X-Auth-Bypass' not in req.headers and 'X-Slack-Request-Timestamp' and 'X-Slack-Signature' in req.headers:
            slack_request_timestamp = req.headers['X-Slack-Request-Timestamp']
            slack_signature = req.headers['X-Slack-Signature']
    else:
        slack_signature = None
        logging.info('Signature: Missing')
        if 'X-Auth-Bypass' not in req.headers:
            return func.HttpResponse(
                'Unauthorized: Do not pass Go, Do not collect $200.00!\n',
                status_code=403
            )
    
    request_body = req.get_body()
    request_body = request_body.decode('ASCII')

    if slack_signature:
        sig_verified = utils.verify_slack_request(slack_signature, slack_request_timestamp, request_body)
    else:
        sig_verified = False
    
    if sig_verified or 'X-Auth-Bypass' in req.headers:
        logging.info('Signature Check: Passed')
    else:
        logging.info(f'Signature Check: Failed\n Request Body: {request_body}')
        # (Un)comment for local debugging
        return func.HttpResponse(
             'Unauthorized: You get nothing! You lose! Good day, sir!\n',
             status_code=403
        )
    
    response_url, trigger_id, user_id, org = get_slack_command(req)

    orgs = db.list_orgs(org)
    sorted_orgs = []

    message = ""
    title = ""

    if len(org) > 0:
        title = "Organizations matching your search:\n"
    else:
        title = "Current registered organizations:\n"

    for org in orgs:
        sorted_orgs.append(org.organization)
    
    sorted_orgs = sorted(sorted_orgs)

    for org in sorted_orgs:
        message += f'- {org}\n'
    
    resp = utils.add_noaction_modal_section(title, trigger_id)
    fields = utils.add_fields_section(sorted_orgs)

    resp['blocks'] = []

    for field in fields:
        resp['blocks'].append(field)

    #requests.post(response_url, json=resp)

    return func.HttpResponse(
        json.dumps(resp),
        mimetype="application/json"
    )

    

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

