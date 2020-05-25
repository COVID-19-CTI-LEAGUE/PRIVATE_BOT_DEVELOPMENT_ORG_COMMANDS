import sqlalchemy
import os
import requests

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from sqlalchemy import func

from .utils import build_response

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
    echo=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    return session

def list_orgs(search_param):
    session = db_connect()

    if len(search_param) > 0:
        orgs = session.query(CTIContacts).filter(CTIContacts.organization.like(f'%{search_param}')).all()
    else:
        orgs = session.query(CTIContacts).order_by(CTIContacts.id).all()
    return orgs

def leave_org(response_url, user_id, org_name):
    session = db_connect()
    
    org = session.query(CTIContacts).filter(
        func.lower(CTIContacts.organization.astext) == func.lower(org_name)
    ).first()

    if org is None:
        resp = build_response(f'Organization {org_name} not found')
        requests.post(response_url, json=resp)
    else:
        if user_id == org.contacs['slack']:
            org.contacts['slack'].remove(user_id)

            if len(org.contacts['slack']) > 0:
                flag_modified(org, 'contacts')
                session.add(org)
                session.commit()
            else:
                session.delete(org)
                session.commit()

            resp = build_response(f'You have been removed from {org_name}')
            requests.post(response_url, json=resp)
        else:
            resp = build_response(f'You are not a contact for {org_name}')
            requests.post(response_url, json=resp)




