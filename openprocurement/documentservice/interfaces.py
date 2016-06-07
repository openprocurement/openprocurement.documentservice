from zope.interface import (
    Attribute,
    Interface,
    )


class IStorage(Interface):
    """ Storage Interface
    """
    def register(file_name, md5):
        pass

    def upload(uuid, post_file):
        pass

    def get(uuid):
        pass
