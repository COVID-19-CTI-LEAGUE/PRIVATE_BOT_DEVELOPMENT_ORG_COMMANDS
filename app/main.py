import bmemcached
import hmac
import os
import sqlalchemy
import sqreen

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

sqreen.start()
##ORM
class CTIContact(db.Model):
    __tablename__ = 'cti_contacts'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(MutableDict.as_mutable(JSONB))

    def __init__(self, data):
        self.data = data

    def __repr__(self):
            return '<id {}>'.format(self.id)

class CTIHelp(db.Model):
        __tablename__ = 'cti_help'
        id = db.Column(db.Integer, primary_key=True)
        data = db.Column(MutableDict.as_mutable(JSONB))

        def __init__(self, data):
                sefl.data = data;

        def __repr__(self):
                return '<id {}>'.format(self.id)

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

    all_ccs = db.session.query(CTIContact).all()
    resp = {}
    resp['blocks'] = []
    orgs = []

    if len(text) == 0:
        message = "Current registered organizations:"
        for cc in all_ccs:
            orgs.append(cc.data['organization'])
    else:
        message = "Organizations matching your search:\n"
        for cc in all_ccs:
            if text.lower() in cc.data['organization'].lower():
                orgs.append(cc.data['organization'])

    resp['blocks'].append(add_mrkdwn_section(message))
    fields = add_fields_section(orgs)
    resp['blocks'].append(fields)
    print(resp)
    return jsonify(resp)

@app.route('/leaveorg', methods=['POST'])
@slack_sig_auth
def leaveorg():
    text=request.form['text']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)

    cc = db.session.query(CTIContact).filter(
        func.lower(CTIContact.data['organization'].astext) == func.lower(text)
    ).first()

    if cc is None:
        resp = build_response('Organization {} not found'.format(text))
        return jsonify(resp)
    else:
        if user_id in cc.data['contacts']:
            cc.data['contacts'].remove(user_id)

            if len(cc.data['contacts']) > 0:
                flag_modified(cc, 'data')
                db.session.add(cc)
                db.session.commit()
            else:
                db.session.delete(cc)
                db.session.commit()
            resp = build_response('You have been removed from {}'.format(text))
            return jsonify(resp)
        else:
            resp = build_response('You are not a contact for {}'.format(text))
            return jsonify(resp)

@app.route('/delorg', methods=['POST'])
@slack_sig_auth
def deleteorg():
    text=request.form['text']
    user_id=request.form['user_id']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)

    cc = db.session.query(CTIContact).filter(
        func.lower(CTIContact.data['organization'].astext) == func.lower(text)
    ).first()

    if cc is None:
        resp = build_response('Organization {} not found'.format(text))
        return jsonify(resp)

    if user_id in cc.data['contacts']:
        db.session.delete(cc)
        db.session.commit()
        resp = build_response('Organization {} has been removed'.format(text))
        return jsonify(resp)
    else:
        resp = build_response('You are not a member of {}'.format(text))
        return jsonify(resp)

@app.route('/listmyorgs', methods=['POST'])
@slack_sig_auth
def listmyorgs():
    text=request.form['text']
    user_id=request.form['user_id']

    all_ccs = db.session.query(CTIContact).all()

    message = "You are a contact for the following organizations:\n"
    resp = {}
    resp['blocks'] = []
    resp['blocks'].append(add_mrkdwn_section(message))
    orgs = []

    for cc in all_ccs:
        if user_id in cc.data['contacts']:
            orgs.append(cc.data['organization'])

    fields = add_fields_section(orgs)
    resp['blocks'].append(fields)

    print(resp)
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

    cc = db.session.query(CTIContact).filter(
        func.lower(CTIContact.data['organization'].astext) == func.lower(args[0])
    ).first()

    if cc is None:
        resp = build_response('Organization {} not found'.format(text))
        return jsonify(resp)
    else:
        if user_id in cc.data['contacts']:
            cc.data['organization'] = args[1]
            flag_modified(cc, 'data')
            db.session.add(cc)
            db.session.commit()

            resp = build_response('Organization {} renamed to {}'.format(args[0], args[1]))
            return jsonify(resp)
        else:
            resp = build_response('You are not a member of {}'.format(args[0]))
            return jsonify(resp)


@app.route('/listmembers', methods=['POST'])
@slack_sig_auth
def listmembers():
    text=request.form['text']
    user_name=request.form['user_name']

    if len(text) == 0:
        resp = build_response('Missing organization')
        return jsonify(resp)
    else:
        cc = db.session.query(CTIContact).filter(
        ##    CTIContact.data.contains({'organization' : text})
            func.lower(CTIContact.data['organization'].astext) == func.lower(text)
            ).first()

        if cc is None:
            resp = build_response('Organization {} not found'.format(text))
            return jsonify(resp)

        contacts = []
        for contact in cc.data['contacts']:
            contact_info = get_slack_profile(contact)
            if contact_info is not None:
                contact_str = "{} (<@{}>)".format(contact_info['full_name'], contact)
            else:
                contact_str = "{}".format(contact);
            contacts.append(contact_str)

        resp = {}
        resp['blocks'] = []
        resp['blocks'].append(add_mrkdwn_section('Contacts for {}'.format(text)))

        fields = add_fields_section(contacts)
        resp['blocks'].append(fields)
        print(resp)

        return jsonify(resp)

@app.route('/addcontact', methods=['POST'])
@slack_sig_auth
def addcontact():
    text=request.form['text']
    user_name=request.form['user_name']
    user_id=request.form['user_id']

    #error checking
    message = ""
    if len(text) == 0:
        message = "Missing organization(s) you want to be a member of"
    else:
        orgs = text.split(',')
        plural =""
        if len(orgs) > 0:
            plural="s"

        message = "You have been added to the following organization%s: %s" % (plural, orgs)
        for org in orgs:
            org = org.lstrip(' ')
            org = org.rstrip(' ')
            org = org.replace('<', '')
            org = org.replace('>', '')
            cc = db.session.query(CTIContact).filter(
                func.lower(CTIContact.data['organization'].astext) == func.lower(org)
            ).first()
            if cc is None:
                cc = CTIContact(
                    data = {'organization' : org,
                            'contacts' : [user_id]}
                )
                db.session.add(cc)
                db.session.commit()
            else:
                if user_id not in cc.data['contacts']:
                    cc.data['contacts'].append(user_id)
                    flag_modified(cc, 'data')
                    db.session.add(cc)
                    db.session.commit()
                else:
                    resp = build_response('Nice try, you already are part of {}'.format(org))
                    return jsonify(resp)

    resp = build_response(message)
    return jsonify(resp)
