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
    if not utils.is_request_authorized(req):
        return func.HttpResponse(
            'Forbidden',
            status_code=403
        )
    
    response_url, trigger_id, user_id, org = utils.get_slack_command(req)

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

