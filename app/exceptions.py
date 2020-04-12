class OrgLookupException(Exception):
    def __init__(self, msg=None):
        if msg is None:
            msg = "An error has occurred in the OrgLookup command"
        super(OrgLookupException, self).__init__(msg)
