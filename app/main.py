import bmemcached
import hmac
import os
import sqlalchemy

from flask import Flask
from flask import abort, jsonify
from flask import request, make_response

from flask_sqlalchemy import SQLAlchemy
from flask_heroku import Heroku
from flask_slacksigauth import slack_sig_auth

from sqlalchemy import column, exists, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import flag_modified

from app.utils import *
from app.exceptions import OrgLookupException

from config import ProductionConfig

app = Flask(__name__)
app.config.from_object(ProductionConfig())
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

heroku = Heroku(app)
db = SQLAlchemy(app)

##ORM
class CTIContact(db.Model):
    __tablename__ = 'cti_contacts'
    id = sqlalchemy.Column(sqlalchemy.BigInteger, primary_key=True)
    organization = sqlalchemy.Column(sqlalchemy.Text)
    contacts = sqlalchemy.Column(sqlalchemy.JSON)

    def __repr__(self):
        return f'<Org(name={self.organization}, contacts={self.contacts}'

##routes
##@app.errorhandler(Exception)
##def handle_exceptions(e):
##    return jsonify(error='An error has occurred, please contact @emilio'), 500

@app.errorhandler(403)
def not_authorized(e):
    return jsonify(error=str(e)), 403

@app.route('/listorgs', methods=['POST'])
@slack_sig_auth
def listorgs():
    text=request.form['text']
    user_name=request.form['user_name']
    trigger_id=request.form['trigger_id']

    #all_ccs = db.session.query(CTIContact).order_by(CTIContact.id).all()
    orgs = []
    sorted_orgs = []
    message = ""
    title = ""

    if len(text) == 0:
        title = "Current registered organizations:\n"
        orgs = db.session.query(CTIContact).order_by(CTIContact.id).all()
    else:
        title = "Organizations matching your search:\n"
        orgs = db.session.query(CTIContact).filter(CTIContact.organization.like(f'%{text}%')).all()

    for org in orgs:
        sorted_orgs.append(org.organization)

    sorted_orgs = sorted(sorted_orgs)
    for org in sorted_orgs:
        message += "- {}\n".format(org)

    resp = add_noaction_modal_section(title, trigger_id)
    fields = add_fields_section(sorted_orgs)

    resp['blocks'] = []

    for field in fields:
        resp['blocks'].append(field)
    #resp = build_response(message)
    return jsonify(resp)

@app.route('/leaveorg', methods=['POST'])
@slack_sig_auth
def leaveorg():
    text=request.form['text']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)

    orgs = db.session.query(CTIContact).all()

    org = None
    for o in orgs:
        if org_name.lower() == o.organization.lower():
            org = o

    resp = {}
    if org is None:
        resp = build_response(f'Organization {org_name} not found')
    else:
        if user_id in org.contacts['slack']:
            org.contacts['slack'].remove(user_id)

            if len(org.contacts['slack']) > 0:
                flag_modified(org, 'contacts')
                session.add(org)
                session.commit()
            else:
                session.delete(org)
                session.commit()

            resp = build_response(f'You have been removed from {org_name}')
        else:
            resp = build_response(f'You are not a contact for {org_name}')

    return jsonify(resp)

@app.route('/delorg', methods=['POST'])
@slack_sig_auth
def deleteorg():
    text=request.form['text']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)

    org = db.session.query(CTIContact).filter(organization=org_name).first()
    resp = {}

    if org is None:
        resp = build_response(f'Organization {org_name} not found')
        return resp

    slack_contacts = org.contacts['slack']

    if len(slack_contacts) > 0:
        owner_id = slack_contacts[0]

        if user_id == owner_id:
            db.session.delete(org)
            db.session.commit()
            resp = build_response(f'Organization {org_name} has been removed')
        else:
            resp = build_response(f'Unauthorized. Please ask <@{owner_id}> to request deletion')
    else:
        resp = build_response('Please contact <@admins> for assistance')

    return jsonify(resp)

@app.route('/listmyorgs', methods=['POST'])
@slack_sig_auth
def listmyorgs():
    text=request.form['text']
    user_id=request.form['user_id']

    orgs = db.session.query(CTIContact).all()
    resp = {}
    resp['blocks'] = []

    my_orgs = []
    resp['blocks'].append(add_mrkdwn_section('You are a contact for the following organization(s):'))
    for org in orgs:
        if user_id in org.contacts['slack']:
            my_orgs.append(org.organization)

    if len(my_orgs) == 0:
        resp['blocks'].append(add_mrkdwn_section('You are not a member of any organization'))
    else:
        fields = add_fields_section(my_orgs)

        for field in fields:
            resp['blocks'].append(field)

    return jsonify(resp)

@app.route('/modorg', methods=['POST'])
@slack_sig_auth
def modorg():
    text=request.form['text']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp=build_response('Usage: /modorg <existing org> <new name>')
        return jsonify(resp)

    args = text.split(' ')

    if len(args) < 2:
        resp=build_response('Usage: /modorg <existing org> <new name>')
        return jsonify(resp)

    org_name = args[0]
    new_org_name = args[1]
    new_org_name = new_org_name.replace('<', '')
    new_org_name = new_org_name.replace('>', '')
    new_org_name = new_org_name.lstrip(' ')
    new_org_name = new_org_name.rstrip(' ')

    org = db.session.query(CTIContact).filter(organization=org_name).first()
    resp = {}

    if org is None:
        resp = build_response(f'Organization {org_name} not found')
        return resp

    slack_contacts = org.contacts['slack']

    if len(slack_contacts) > 0:
        owner_id = slack_contacts[0]

        if user_id == owner_id:
            org.organization = new_org_name
            flag_modified(org, 'organization')
            session.add(org)
            session.commit()
            resp = build_response(f'Organization {org_name} has been renamed to {new_org_name}')
        else:
            resp = build_response(f'Unauthorized. Please ask <@{owner_id}> to request modification')
    else:
        resp = build_response('Please contact <@admins> for assistance')

    return jsonify(resp)


@app.route('/listmembers', methods=['POST'])
@slack_sig_auth
def listmembers():
    text=request.form['text']
    user_name=request.form['user_name']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)

    orgs = db.session.query(CTIContact).filter(CTIContact.organization.like(f'%{text}%')).all()
    resp = {}

    if orgs is None or len(orgs) == 0:
        resp = build_response(f'Organization {org_search} not found')
        return jsonify(resp)

    resp['blocks'] = []

    for org in orgs:
        resp['blocks'].append(add_mrkdwn_section(f'Contacts for {org.organization}'))
        contacts = []
        for slack in org.contacts['slack']:
            user_profile = get_slack_profile(slack)
            if user_profile is not None:
                contacts.append('{} (<@{}>)'.format(user_profile['full_name'], slack))
        for email in org.contacts['emails']:
            contacts.append(email)

        fields = add_fields_section(contacts, False)

        for field in fields:
            resp['blocks'].append(field)

    print(resp)
    return jsonify(resp)

@app.route('/addcontact', methods=['POST'])
@slack_sig_auth
def addcontact():
    text=request.form['text']
    user_name=request.form['user_name']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp = build_response("Missing organization(s) you want to be a member of")
        return jsonify(resp)
    org_name = text
    org = db.session.query(CTIContact).filter_by(organization=org_name).first()
    resp = {}
    org_name = org_name.replace('<', '')
    org_name = org_name.replace('>', '')
    org_name = org_name.lstrip(' ')
    org_name = org_name.rstrip(' ')
    org_name = org_name.replace("\"", "")
    org_name = org_name.replace("'", "")

    if len(org_name) < 1:
        resp = add_mrkdwn_section('Organization name cannot be blank')
        return resp

    if org is None:
        org = CTIContacts(organization=org_name, contacts= {'slack' : [], 'emails' : []})

    #self-registration
    if user_id not in org.contacts['slack']:
        org.contacts['slack'].append(user_id)
        flag_modified(org, 'contacts')
        session.add(org)
        session.commit()
        resp = build_response(f'You have been added as a contact for {org_name}')
    else:
        resp = build_response(f'You are already a member of {org_name}')

    return jsonify(resp)
