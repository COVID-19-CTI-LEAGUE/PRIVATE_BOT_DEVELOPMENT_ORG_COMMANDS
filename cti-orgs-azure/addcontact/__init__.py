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
    if not utils.is_request_authorized(req):
        return func.HttpResponse(
            'Unauthorized',
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
