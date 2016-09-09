# -*- coding: utf-8 -*-
# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from operator import attrgetter
from openerp import fields
from openerp.exceptions import UserError
from openerp.osv import fields as columns
from .cmis_meta_field import CmisMetaField


class CmisFolder(fields.Field):
    """ A reference to a cmis:folder. (cmis:objectId)

    :param backend_name:

        The attribute ``backend_name`` is mandatory if more than one backend
        id configured. Otherwize you must have configured one backend ir order
        to prevent errors when loading a view that includes this kind of field.

    :param allow_create: Allow create from UI (by default True)

    :param allow_delete: Allow delete from UI (by default False)

    :param create_method: name of a method that create the field into the
        CMIS repository. The method must assign the field on all records of the
        invoked recordset. The method is called with the field definition
        instance and the bakend as paramaters
        (optional)

    :param create_parent_get: name of a method that return the cmis:objectId of
        the folder to use as parent. The method is called with the field
        definition instance and the bakend as paramaters.
        (optional: by default the folder is
        created  as child of backend.initial_directory_write + '/' model._name)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: 'cmis:objectId'}

    :param create_name_get: name of a method that return the name of the
        folder to create into the CMIS repository. The method is called with
        the field definition instance and the bakend as paramaters.
        (optional: by default instance.name_get)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: 'name'}

    :parem create_properties_get: name of a method that return a dictionary of
        CMIS properties ro use to create the folder. The method is called
        with the field definition instance and the bakend as paramaters
        (optional: default empty)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: {'cmis:xxx': 'val1', ...}}

    """
    type = 'char'  # Postgresl
    # ttype is the type registered into the Field registry. The registry is
    # used to instanciate the fields defined throughout the UI based
    ttype = 'cmis_folder'
    widget = 'cmis_folder'  # Web widget
    _slots = {
        'backend_name': None,
        'create_method': None,
        'create_name_get': 'name_get',
        'create_parent_get': None,
        'create_properties_get': None,
        'allow_create': True,
        'allow_delete': False
    }

    __metaclass__ = CmisMetaField

    def __init__(self, backend_name=None, string=None, **kwargs):
        super(CmisFolder, self).__init__(
            backend_name=backend_name, string=string, **kwargs)

    def get_description(self, env):
        """ Return a dictionary that describes the field ``self``. """
        desc = super(CmisFolder, self).get_description(env)
        desc['type'] = self.widget
        return desc

    def _description_backend(self, env):
        backend = self.get_backend(env)
        return backend.get_web_description()[backend.id]

    _description_allow_create = property(attrgetter('allow_create'))
    _description_allow_delete = property(attrgetter('allow_delete'))

    def get_backend(self, env):
        return env['cmis.backend'].get_by_name(name=self.backend_name)

    def create_value(self, records):
        """Create a new folder for each record into the cmis container and
        store the value as field value
        """
        for record in records:
            self._check_null(record)
        backend = self.get_backend(records.env)
        if self.create_method:
            fct = self.create_method
            if not callable(fct):
                fct = getattr(records, fct)
            fct(self, backend)
            return
        self._create_in_cmis(records, backend)

    def _create_in_cmis(self, records, backend):
        names = self.get_create_names(records, backend)
        parents = self.get_create_parents(records, backend)
        properties = self.get_create_properties(records, backend)
        repo = backend.get_cmis_repository()
        for record in records:
            name = names[record.id]
            parent = parents[record.id]
            props = properties[record.id] or {}
            value = repo.createFolder(
                parent, name, props)
            self.__set__(record, value.getObjectId())

    def _check_null(self, record, raise_exception=True):
        val = self.__get__(record, record)
        if val and raise_exception:
            raise UserError('A value is already assigned to %s' % self)
        return val

    def get_create_names(self, records, backend):
        """return the names of the folders to create into the CMIS repository
        for the given recordset.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: 'name'}

        """
        if self.create_name_get == 'name_get':
            return dict(records.name_get())
        fct = self.create_name_get
        if not callable(fct):
            fct = getattr(records, fct)
        return fct(self, backend)

    def get_create_parents(self, records, backend):
        """return the cmis:objectId of the cmis folder to use as parent of the
        new folder.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: 'cmis:objectId'}

        """
        if self.create_parent_get:
            fct = self.create_parent_get
            if not callable(fct):
                fct = getattr(records, fct)
            return fct(self, backend)
        path = self.get_default_parent_path(records, backend)
        parent_cmis_object = backend.get_folder_by_path(
            path, create_if_not_found=True)
        return dict.fromkeys(records.ids, parent_cmis_object)

    def get_create_properties(self, records, backend):
        """Return the properties to use to created the folder into the CMIS
        container.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: {'cmis:xxx': 'val1', ...}}

        """
        if self.create_properties_get:
            fct = self.create_properties_get
            if not callable(fct):
                fct = getattr(records, fct)
            return fct(self, backend)
        return dict.fromkeys(records.ids, None)

    def get_default_parent_path(self, records, backend):
        """Return the default path into the cmis container to use as parent
        on folder create. By default:
        backend.initial_directory_write / record._name
        """
        return '/'.join([backend.initial_directory_write,
                         records[0]._name.replace('.', '_')])