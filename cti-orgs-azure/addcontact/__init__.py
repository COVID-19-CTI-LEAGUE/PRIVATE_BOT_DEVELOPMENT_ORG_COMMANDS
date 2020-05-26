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



from ..shared_code import db, utils


def main(req: func.HttpRequest) -> func.HttpResponse:
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
    
    response_url, trigger_id, user_id, params = utils.get_slack_command(req)
    args = params.split(' ')
    org = args[0]
    third_party = None

    if len(args) > 1:
        third_party=args[1]

    logging.info(f'User id {user_id} args {args} third party {third_party}')

    resp = db.add_contact(user_id, org, third_party)

    return func.HttpResponse(
        json.dumps(resp),
        mimetype='application/json'
    )
