# -*- coding: utf-8 -*-

"""
Web Relations Tree generator.
"""

import json
import os
import shutil
import sys

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext
from gramps.gen.config import config
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.menu import (StringOption, PersonOption, DestinationOption)
from gramps.gen.lib import Person
from gramps.gen.utils.file import media_path_full
from gramps.gui.thumbnails import get_thumbnail_path


#------------------------------------------------------------------------
# WebRelTreeReport
#------------------------------------------------------------------------
class WebRelTreeReport(Report):
    """
    Create WebRelTreeReport object that produces the report.
    """
    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        self.options = options
        self.user = user

    def write_report(self):
        self.dirname = self.options.menu.get_option_by_name('target').get_value()
        if not os.path.isdir(self.dirname):
            try:
                os.mkdir(self.dirname)
            except IOError as exc:
                self.user.notify_error(_('Could not create the directory: %s') % exc)
                return
        self.thumb_dirname = os.path.join(self.dirname, 'thumbs')
        if not os.path.isdir(self.thumb_dirname):
            try:
                os.mkdir(self.thumb_dirname)
            except IOError as exc:
                self.user.notify_error(_('Could not create the directory: %s') % exc)
                return
        persons = []
        gender_map = {
            Person.MALE: 'm',
            Person.FEMALE: 'f',
        }
        # read data from database
        person_handles = self.database.get_person_handles()
        with self.user.progress(
                _('Web Relations Tree Report'), _('Creating individual pages'),
                len(person_handles)) as step:
            for handle in person_handles:
                person = self.database.get_person_from_handle(handle)
                persons.append({
                    'id': person.gramps_id,
                    'name': _person_short_name(person),
                    'fullname': _person_long_name(person),
                    'url': self._gen_url(person),
                    'icon': self._gen_icon(person),
                    'bdate': self._fmt_event(person.get_birth_ref()),
                    'ddate': self._fmt_event(person.get_death_ref()),
                    'gender': gender_map.get(person.get_gender()),
                    'childOf': [self.database.get_family_from_handle(handle).gramps_id
                                for handle in person.get_parent_family_handle_list()],
                    'parentOf': [self.database.get_family_from_handle(handle).gramps_id
                                 for handle in person.get_family_handle_list()],
                })
                step()
        # read family data from database
        person_handles = self.database.get_person_handles()
        # write file
        with open(os.path.join(self.dirname, 'persons.js'), 'w') as fdescr:
            fdescr.write('personsSource = ')
            json.dump(persons, fdescr, indent=2)
            fdescr.write(
                ';\nvar startPersonId = "%s";\n' %
                self.options.menu.get_option_by_name('person_id').get_value())

    def _gen_url(self, person):
        narweb_url = self.options.menu.get_option_by_name('narweb_prefix').get_value()
        if narweb_url:
            fname = person.get_handle()
            path = [narweb_url, 'ppl', fname[-1].lower(), fname[-2].lower(), fname + '.html']
            return '/'.join([e.strip('/') for e in path])

    def _gen_icon(self, person):
        media_refs = person.get_media_list()
        if len(media_refs) == 0:
            return
        media_ref = media_refs[0]
        region = media_ref.get_rectangle()
        photo_handle = media_ref.get_reference_handle()
        photo = self.database.get_object_from_handle(photo_handle)
        mimetype = photo.get_mime_type()
        if mimetype:
            full_path = media_path_full(self.database, photo.get_path())
            src_path = get_thumbnail_path(full_path, mimetype, region)
            dst_path = os.path.join(
                self.thumb_dirname, photo_handle +
                (('%d,%d-%d,%d.png' % region) if region else '.png'))
            shutil.copyfile(src_path, dst_path)
            return os.path.join('thumbs', os.path.basename(dst_path))

    def _fmt_event(self, event_ref):
        if event_ref is None:
            return None
        handle = event_ref.get_reference_handle()
        if handle is None:
            return None
        event = self.database.get_event_from_handle(handle)
        if event is None:
            return None
        date = event.get_date_object()
        if date is None:
            return None
        year = date.get_year()
        if year == 0:
            return None
        month = date.get_month()
        day = date.get_day()
        return '%0.4d-%0.2d-%0.2d' % (year, month, day)


# ---------------------------------------------------------------------------------------
# WebRelTreeOptions; Creates the Menu
#----------------------------------------------------------------------------------------
class WebRelTreeOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, dbase):
        self.__db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """
        Add options to the menu for this report.
        """
        category_name = _('Report Options')

        dbname = self.__db.get_dbname()
        def_dir = dbname + '_WEBRELTREE'
        self.__target = DestinationOption(
            _('Destination'), os.path.join(config.get('paths.website-directory'), def_dir))
        self.__target.set_help( _('The destination directory for the web files'))
        self.__target.set_directory_entry(True)
        menu.add_option(category_name, 'target', self.__target)

        self.__person_id = PersonOption(_('Filter Person'))
        self.__person_id.set_help(_('The center person for the filter'))
        menu.add_option(category_name, 'person_id', self.__person_id)

        default_prefix = '../../' + dbname + '_NARWEB/'
        self.__narweb_prefix = StringOption(_('Link prefix'), default_prefix)
        self.__narweb_prefix.set_help(_('A Prefix on the links to take you to '
                                        'Narrated Web Report'))
        menu.add_option(category_name, 'narweb_prefix', self.__narweb_prefix)


def _person_short_name(person):
    pname = person.get_primary_name()
    short_name = [pname.first_name]
    for s in pname.surname_list:
        if not s.surname:
            continue
        if s.primary:
            short_name.insert(0, s.surname)
            break
    return ' '.join(short_name)


def _person_long_name(person):
    pname = person.get_primary_name()
    long_name = [pname.first_name]
    for s in pname.surname_list:
        if not s.surname:
            continue
        if s.primary:
            long_name.insert(0, s.surname)
        else:
            long_name.append(s.surname)
    return ' '.join(long_name)
