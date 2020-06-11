import sqlalchemy
import os
import requests

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from sqlalchemy import func

from .utils import build_response, add_mrkdwn_section, add_fields_section, get_slack_profile, is_valid_email, extract_user_id

db_host = os.environ['DB_HOST']
db_user = os.environ['DB_USER']
db_pass = os.environ['DB_PASS']



Base = declarative_base()

class CTIContacts(Base):
    __tablename__ = 'cti_contacts'
    
    id = sqlalchemy.Column(sqlalchemy.BigInteger, primary_key=True)
    organization = sqlalchemy.Column(sqlalchemy.Text)
    contacts = sqlalchemy.Column(sqlalchemy.JSON)

    def __repr__(self):
        return f'<Org(name={self.organization}, contacts={self.contacts}'



def db_connect():
    engine = sqlalchemy.create_engine(
    f'mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}:3306/cti_orgs',
    echo=False)

    Session = sessionmaker(bind=engine)
    session = Session()

    return session

def list_orgs(search_param):
    session = db_connect()

    if len(search_param) > 0:
        orgs = session.query(CTIContacts).filter(CTIContacts.organization.like(f'%{search_param}%')).all()
    else:
        orgs = session.query(CTIContacts).order_by(CTIContacts.id).all()
    return orgs

def leave_org(user_id, org_name):
    session = db_connect()

    orgs = session.query(CTIContacts).all()

    org = None
    for o in orgs:
        if org_name.lower() == o.organization.lower():
            org = o

    resp = {}
    if org is None:
        resp = build_response(f'Organization {org_name} not found')
    else:
        if user_id == org.contacts['slack']:
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
    
    return resp


def list_my_orgs(user_id, email):
    session = db_connect()

    orgs = session.query(CTIContacts).all()
    resp = {}
    resp['blocks'] = []
    if len(email) == 0:
        #lookup only by slack user ID
        my_orgs = []
        resp['blocks'].append(add_mrkdwn_section('You are a contact for the following organization(s):'))
        for org in orgs:
            if user_id in org.contacts['slack']:
                my_orgs.append(org.organization)
        fields = add_fields_section(my_orgs)

        for field in fields:
            resp['blocks'].append(field)
    else:
        email_orgs = []
        resp['blocks'].append(add_mrkdwn_section(f'{email} is a contact for the following organization(s):'))
        for org in orgs:
            if email in org.contacts['emails']:
                email_orgs.append(org.organization)
            fields = add_fields_section(email_orgs)
        for field in fields:
            resp['blocks'].append(field)
    
    return resp

def list_members(org_search):
    session = db_connect()

    orgs = session.query(CTIContacts).filter(CTIContacts.organization.like(f'%{org_search}%')).all()
    resp = {}

    if orgs is None or len(orgs) == 0:
        resp = build_response(f'Organization {org_search} not found')
        return resp
    
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
    return resp

def add_contact(user_id, org_name, third_party=None):
    session = db_connect()
    
    org = session.query(CTIContacts).filter_by(organization=org_name).first()
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
    
    if third_party is None:
        #self-registration
        if user_id not in org.contacts['slack']:
            org.contacts['slack'].append(user_id)
            flag_modified(org, 'contacts')
            session.add(org)
            session.commit()
            resp = build_response(f'You have been added as a contact for {org_name}')
        else:
            resp = build_response(f'You are already a member of {org_name}')
    else:
        if is_valid_email(third_party):
            #email registration
            if third_party not in org.contacts['emails']:
                org.contacts['emails'].append(third_party)
                flag_modified(org, 'contacts')
                session.add(org)
                session.commit()
                resp = build_response(f'{third_party} registered as a contact for {org_name}')
            else:
                resp = build_response(f'{third_party} already registered for {org_name}')
        else:
            third_party = extract_user_id(third_party)
            if third_party not in org.contacts['slack']:
                org.contacts['slack'].append(third_party)
                flag_modified(org, 'contacts')
                session.add(org)
                session.commit()
                resp = build_response(f'<@{third_party}> added as a contact for {org_name}')
            else:
                resp = build_response(f'<@{third_party}> is already a contact for {org_name}')
    
    return resp


def delete_org(user_id, org_name):
    session = db_connect()

    org = session.query(CTIContacts).filter(organization=org_name).first()
    resp = {}

    if org is None:
        resp = build_response(f'Organization {org_name} not found')
        return resp
    
    slack_contacts = org.contacts['slack']

    if len(slack_contacts) > 0:
        owner_id = slack_contacts[0]

        if user_id == owner_id:
            session.delete(org)
            session.commit()
            resp = build_response(f'Organization {org_name} has been removed')
        else:
            resp = build_response(f'Unauthorized. Please ask <@{owner_id}> to request deletion')
    else:
        resp = build_response('Please contact <@admins> for assistance')
    
    return resp


def modify_org(user_id, org_name, new_org_name):
    session = db_connect()

    new_org_name = new_org_name.replace('<', '')
    new_org_name = new_org_name.replace('>', '')
    new_org_name = new_org_name.lstrip(' ')
    new_org_name = new_org_name.rstrip(' ')

    org = session.query(CTIContacts).filter(organization=org_name).first()
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

    return resp 
            













