#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2002 Bruce J. DeGrasse
# Copyright (C) 2000-2007 Donald N. Allingham
# Copyright (C) 2007      Brian G. Matherly
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

"Generate files/Detailed Ancestral Report"

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
from gettext import gettext as _

#------------------------------------------------------------------------
#
# Gnome/GTK modules
#
#------------------------------------------------------------------------
import gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import gen.lib
from PluginUtils import register_report
from ReportBase import Report, ReportUtils, ReportOptions, \
     CATEGORY_TEXT, MODE_GUI, MODE_BKI, MODE_CLI
from ReportBase import Bibliography, Endnotes

import BaseDoc
import Utils
import DateHandler
from QuestionDialog import ErrorDialog
from BasicUtils import name_displayer as _nd

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
EMPTY_ENTRY = "_____________"

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class DetAncestorReport(Report):

    def __init__(self,database,person,options_class):
        """
        Creates the DetAncestorReport object that produces the report.
        
        The arguments are:

        database        - the GRAMPS database instance
        person          - currently selected person
        options_class   - instance of the Options class for this report

        This report needs the following parameters (class variables)
        that come in the options class.
        
        gen           - Maximum number of generations to include.
        pagebgg       - Whether to include page breaks between generations.
        firstName     - Whether to use first names instead of pronouns.
        fullDate      - Whether to use full dates instead of just year.
        listChildren  - Whether to list children.
        includeNotes  - Whether to include notes.
        includeAttrs  - Whether to include attributes
        blankPlace    - Whether to replace missing Places with ___________.
        blankDate     - Whether to replace missing Dates with ___________.
        calcAgeFlag   - Whether to compute age.
        dupPerson     - Whether to omit duplicate ancestors (e.g. when distant cousins mary).
        childRef      - Whether to add descendant references in child list.
        addImages     - Whether to include images.
        """
        Report.__init__(self,database,person,options_class)

        self.map = {}

        self.max_generations = options_class.handler.options_dict['gen']
        self.pgbrk         = options_class.handler.options_dict['pagebbg']
        self.fullDate      = options_class.handler.options_dict['fulldates']
        self.listChildren  = options_class.handler.options_dict['listc']
        self.includeNotes  = options_class.handler.options_dict['incnotes']
        self.usecall       = options_class.handler.options_dict['usecall']
        self.blankPlace    = options_class.handler.options_dict['repplace']
        self.blankDate     = options_class.handler.options_dict['repdate']
        self.calcAgeFlag   = options_class.handler.options_dict['computeage']
        self.dupPerson     = options_class.handler.options_dict['omitda']
        self.childRef      = options_class.handler.options_dict['desref']
        self.addImages     = options_class.handler.options_dict['incphotos']
        self.includeNames  = options_class.handler.options_dict['incnames']
        self.includeEvents = options_class.handler.options_dict['incevents']
        self.includeAddr   = options_class.handler.options_dict['incaddresses']
        self.includeSources= options_class.handler.options_dict['incsources']
        self.includeAttrs  = options_class.handler.options_dict['incattrs']

        self.gen_handles = {}
        self.prev_gen_handles= {}
        
        if self.blankDate:
            self.EMPTY_DATE = EMPTY_ENTRY
        else:
            self.EMPTY_DATE = ""

        if self.blankPlace:
            self.EMPTY_PLACE = EMPTY_ENTRY
        else:
            self.EMPTY_PLACE = ""

        self.bibli = Bibliography(Bibliography.MODE_PAGE)

    def apply_filter(self,person_handle,index):
        if (not person_handle) or (index >= 2**self.max_generations):
            return
        self.map[index] = person_handle

        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            self.apply_filter(family.get_father_handle(),index*2)
            self.apply_filter(family.get_mother_handle(),(index*2)+1)

    def write_report(self):
        self.apply_filter(self.start_person.get_handle(),1)

        name = _nd.display_name(self.start_person.get_primary_name())
        self.doc.start_paragraph("DAR-Title")
        title = _("Ancestral Report for %s") % name
        mark = BaseDoc.IndexMark(title,BaseDoc.INDEX_TYPE_TOC,1)
        self.doc.write_text(title,mark)
        self.doc.end_paragraph()

        keys = self.map.keys()
        keys.sort()
        generation = 0
        need_header = 1

        for key in keys :
            if generation == 0 or key >= 2**generation:
                if self.pgbrk and generation > 0:
                    self.doc.page_break()
                self.doc.start_paragraph("DAR-Generation")
                text = _("Generation %d") % (generation+1)
                mark = BaseDoc.IndexMark(text,BaseDoc.INDEX_TYPE_TOC,2)
                self.doc.write_text(text,mark)
                self.doc.end_paragraph()
                generation = generation + 1
                if self.childRef:
                    self.prev_gen_handles= self.gen_handles.copy()
                    self.gen_handles.clear()

            person_handle = self.map[key]
            person = self.database.get_person_from_handle(person_handle)
            self.gen_handles[person_handle] = key
            dupPerson = self.write_person(key)
            if dupPerson == 0:      # Is this a duplicate ind record
                if self.listChildren or self.includeEvents:
                    for family_handle in person.get_family_handle_list():
                        family = self.database.get_family_from_handle(family_handle)
                        mother_handle = family.get_mother_handle()
                        if mother_handle == None or                            \
                           person.get_gender() == gen.lib.Person.FEMALE:
                            if self.listChildren:
                                self.write_children(family)
                            if self.includeEvents:
                                self.write_family_events(family)
        if self.includeSources:
            Endnotes.write_endnotes(self.bibli,self.database,self.doc)

    def write_person(self, key):
        """Output birth, death, parentage, marriage and notes information """

        person_handle = self.map[key]
        person = self.database.get_person_from_handle(person_handle)
        plist = person.get_media_list()
        
        if self.addImages and len(plist) > 0:
            photo = plist[0]
            ReportUtils.insert_image(self.database,self.doc,photo)

        self.doc.start_paragraph("DAR-First-Entry","%s." % str(key))

        name = _nd.display_formal(person)
        mark = ReportUtils.get_person_mark(self.database, person)

        self.doc.start_bold()
        self.doc.write_text(name,mark)
        if name[-1:] == '.':
            self.doc.write_text("%s " % self.endnotes(person))
        else:
            self.doc.write_text("%s. " % self.endnotes(person))
        self.doc.end_bold()

        if self.dupPerson:
            # Check for duplicate record (result of distant cousins marrying)
            keys = self.map.keys()
            keys.sort()
            for dkey in keys:
                if dkey >= key: 
                    break
                if self.map[key] == self.map[dkey]:
                    self.doc.write_text(
                        _("%(name)s is the same person as [%(id_str)s].") % 
                        { 'name' : '', 'id_str' : str(dkey) })
                    self.doc.end_paragraph()
                    return 1    # Duplicate person

        # Check birth record

        first = ReportUtils.common_name(person,self.usecall)
        text = ReportUtils.born_str(self.database,person,first,
                                    self.EMPTY_DATE,self.EMPTY_PLACE)
        if text:
            birth_ref = person.get_birth_ref()
            if birth_ref:
                birth = self.database.get_event_from_handle(birth_ref.ref)
                text = text.rstrip(". ")
                text = text + self.endnotes(birth) + ". "
            self.doc.write_text(text)
            first = 0

        age,units = self.calc_age(person)
        text = ReportUtils.died_str(self.database,person,first,
                                    self.EMPTY_DATE,self.EMPTY_PLACE,age,units)
        if text:
            death_ref = person.get_death_ref()
            if death_ref:
                death = self.database.get_event_from_handle(death_ref.ref)
                text = text.rstrip(". ")
                text = text + self.endnotes(death) + ". "
            self.doc.write_text(text)
            first = 0

        text = ReportUtils.buried_str(self.database,person,first,
                                      self.EMPTY_DATE,self.EMPTY_PLACE)
        if text:
            self.doc.write_text(text)

        first = ReportUtils.common_name(person,self.usecall)

        self.write_parents(person, first)
        self.write_marriage(person)
        self.doc.end_paragraph()

        if key == 1:
            self.write_mate(person)

        notelist = person.get_note_list()
        if len(notelist) > 0 and self.includeNotes:
            self.doc.start_paragraph("DAR-NoteHeader")
            self.doc.write_text(_("Notes for %s") % name)
            self.doc.end_paragraph()
            for notehandle in notelist:
                note = self.database.get_note_from_handle(notehandle)
                self.doc.write_note(note.get(),note.get_format(),"DAR-Entry")

        first = True
        if self.includeNames:
            for alt_name in person.get_alternate_names():
                if first:
                    self.doc.start_paragraph('DAR-MoreHeader')
                    self.doc.write_text(_('More about %(person_name)s:') % { 
                        'person_name' : name })
                    self.doc.end_paragraph()
                    first = False
                self.doc.start_paragraph('DAR-MoreDetails')
                atype = str( alt_name.get_type() )
                self.doc.write_text(
                    _('%(name_kind)s: %(name)s%(endnotes)s') % {
                    'name_kind' : atype,
                    'name' : alt_name.get_regular_name(),
                    'endnotes' : self.endnotes(alt_name),
                    })
                self.doc.end_paragraph()

        if self.includeEvents:
            birth_ref = person.get_birth_ref()
            death_ref = person.get_death_ref()
            for event_ref in person.get_primary_event_ref_list():
                if event_ref == birth_ref or event_ref == death_ref:
                    continue
                
                if first:
                    self.doc.start_paragraph('DAR-MoreHeader')
                    self.doc.write_text(_('More about %(person_name)s:') % { 
                        'person_name' : _nd.display(person) })
                    self.doc.end_paragraph()
                    first = 0
                    
                self.write_event(event_ref)
                
        if self.includeAddr:
            for addr in person.get_address_list():
                if first:
                    self.doc.start_paragraph('DAR-MoreHeader')
                    self.doc.write_text(_('More about %(person_name)s:') % { 
                        'person_name' : name })
                    self.doc.end_paragraph()
                    first = False
                self.doc.start_paragraph('DAR-MoreDetails')
                
                text = ReportUtils.get_address_str(addr)
                date = DateHandler.get_date(addr)
                self.doc.write_text(_('Address: '))
                if date:
                    self.doc.write_text( '%s, ' % date )
                self.doc.write_text( text )
                self.doc.write_text( self.endnotes(addr) )
                self.doc.end_paragraph()
                
        if self.includeAttrs:
            attrs = person.get_attribute_list()
            if first and attrs:
                self.doc.start_paragraph('DAR-MoreHeader')
                self.doc.write_text(_('More about %(person_name)s:') % { 
                    'person_name' : name })
                self.doc.end_paragraph()
                first = False

            for attr in attrs:
                self.doc.start_paragraph('DAR-MoreDetails')
                text = _("%(type)s: %(value)s%(endnotes)s") % {
                    'type'     : attr.get_type(),
                    'value'    : attr.get_value(),
                    'endnotes' : self.endnotes(attr) }
                self.doc.write_text( text )
                self.doc.end_paragraph()

        return 0        # Not duplicate person
    
    def write_event(self, event_ref):
        text = ""
        event = self.database.get_event_from_handle(event_ref.ref)
        date = DateHandler.get_date(event)
        ph = event.get_place_handle()
        if ph:
            place = self.database.get_place_from_handle(ph).get_title()
        else:
            place = u''

        self.doc.start_paragraph('DAR-MoreDetails')
        evtName = str( event.get_type() )
        if date and place:
            text +=  _('%(event_name)s: %(date)s, %(place)s') % {
                       'event_name' : _(evtName),
                       'date' : date,
                       'place' : place }
        elif date:
            text += _('%(event_name)s: %(date)s') % {
                      'event_name' : _(evtName),
                      'date' : date}
        elif place:
            text += _('%(event_name)s: %(place)s') % {
                      'event_name' : _(evtName),
                      'place' : place }
        else:
            text += _('%(event_name)s: ') % {'event_name' : _(evtName)}

        if event.get_description():
            if text:
                text += ". "
            text += event.get_description()
            
        if text:
            text += _('%(endnotes)s.') % { 'endnotes' : self.endnotes(event) }
        
        self.doc.write_text(text)
        
        if self.includeAttrs:
            text = ""
            attr_list = event.get_attribute_list()
            attr_list.extend(event_ref.get_attribute_list())
            for attr in attr_list:
                if text:
                    text += "; "
                text += _("%(type)s: %(value)s%(endnotes)s") % {
                    'type'     : attr.get_type(),
                    'value'    : attr.get_value(),
                    'endnotes' : self.endnotes(attr) }
            text = " " + text
            self.doc.write_text(text)
        
        self.doc.end_paragraph()

        if self.includeNotes:
            # if the event or event reference has a note attached to it,
            # get the text and format it correctly
            notelist = event.get_note_list()
            notelist.extend(event_ref.get_note_list())
            for notehandle in notelist:
                note = self.database.get_note_from_handle(notehandle)
                self.doc.start_paragraph('DAR-MoreDetails')
                self.doc.write_text("test")
                self.doc.write_text(note.get())
                self.doc.end_paragraph()
                
    def write_parents(self, person, firstName):
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            mother_handle = family.get_mother_handle()
            father_handle = family.get_father_handle()
            if mother_handle:
                mother = self.database.get_person_from_handle(mother_handle)
                mother_name = _nd.display_name(mother.get_primary_name())
                mother_mark = ReportUtils.get_person_mark(self.database, mother)
            else:
                mother_name = ""
                mother_mark = ""
            if father_handle:
                father = self.database.get_person_from_handle(father_handle)
                father_name = _nd.display_name(father.get_primary_name())
                father_mark = ReportUtils.get_person_mark(self.database, father)
            else:
                father_name = ""
                father_mark = ""
                
            text = ReportUtils.child_str(person, father_name, mother_name,
                                         bool(person.get_death_ref()),
                                         firstName)
            if text:
                self.doc.write_text(text)
                if father_mark:
                    self.doc.write_text("",father_mark)
                if mother_mark:
                    self.doc.write_text("",mother_mark)

    def write_marriage(self, person):
        """ 
        Output marriage sentence.
        """
        is_first = True
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            spouse_handle = ReportUtils.find_spouse(person,family)
            spouse = self.database.get_person_from_handle(spouse_handle)
            text = ""
            spouse_mark = ReportUtils.get_person_mark(self.database, spouse)
            
            text = ReportUtils.married_str(self.database,person,family,
                                            self.endnotes,
                                            self.EMPTY_DATE,self.EMPTY_PLACE,
                                            is_first)

            if text:
                self.doc.write_text(text,spouse_mark)
                is_first = False

    def write_children(self, family):
        """ List children.
        """

        if not family.get_child_ref_list():
            return

        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            mother_name = _nd.display(mother)
        else:
            mother_name = _("unknown")

        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            father_name = _nd.display(father)
        else:
            father_name = _("unknown")

        self.doc.start_paragraph("DAR-ChildTitle")
        self.doc.write_text(_("Children of %s and %s") % 
                            (mother_name,father_name))
        self.doc.end_paragraph()

        cnt = 1
        for child_ref in family.get_child_ref_list():
            child_handle = child_ref.ref
            child = self.database.get_person_from_handle(child_handle)
            child_name = _nd.display(child)
            child_mark = ReportUtils.get_person_mark(self.database,child)

            if self.childRef and self.prev_gen_handles.get(child_handle):
                value = str(self.prev_gen_handles.get(child_handle))
                child_name += " [%s]" % value

            self.doc.start_paragraph("DAR-ChildList",ReportUtils.roman(cnt).lower() + ".")
            cnt += 1

            self.doc.write_text("%s. " % child_name,child_mark)
            self.doc.write_text(ReportUtils.born_str(self.database, child, 0,
                                                     self.EMPTY_DATE, self.EMPTY_PLACE))
            self.doc.write_text(ReportUtils.died_str(self.database, child, 0, 
                                                     self.EMPTY_DATE, self.EMPTY_PLACE))
            
            self.doc.end_paragraph()

    def write_family_events(self,family):
        
        if not family.get_event_ref_list():
            return

        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            mother_name = _nd.display(mother)
        else:
            mother_name = _("unknown")

        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            father_name = _nd.display(father)
        else:
            father_name = _("unknown")

        first = 1
        for event_ref in family.get_event_ref_list():
            if first:
                self.doc.start_paragraph('DAR-MoreHeader')
                self.doc.write_text(
                    _('More about %(mother_name)s and %(father_name)s:') % { 
                    'mother_name' : mother_name,
                    'father_name' : father_name })
                self.doc.end_paragraph()
                first = 0
            self.write_event(event_ref)

    def write_mate(self, mate):
        """Output birth, death, parentage, marriage and notes information """

        for family_handle in mate.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            person_name = ""
            ind_handle = None
            has_info = False
            person_key = ""
            if mate.get_gender() == gen.lib.Person.MALE:
                ind_handle = family.get_mother_handle()
            else:
                ind_handle = family.get_father_handle()
            if ind_handle:
                ind = self.database.get_person_from_handle(ind_handle)
                person_name = _nd.display(ind)
                person_mark = ReportUtils.get_person_mark(self.database,ind)
                firstName = ReportUtils.common_name(ind,self.usecall)

                for event_ref in ind.get_primary_event_ref_list():
                    event = self.database.get_event_from_handle(event_ref.ref)
                    if event:
                        etype = event.get_type()
                        if etype == gen.lib.EventType.BURIAL or \
                           etype == gen.lib.EventType.BIRTH  or \
                           etype == gen.lib.EventType.DEATH     :
                            has_info = True
                            break   
                if not has_info:
                    family_handle = ind.get_main_parents_family_handle()
                    if family_handle:
                        f = self.database.get_family_from_handle(family_handle)
                        if f.get_mother_handle() or f.get_father_handle():
                            has_info = True
            else:
                firstName = 0

            print_name = ""
            
            if person_name and has_info:
                self.doc.start_paragraph("DAR-Entry")

                self.doc.write_text(person_name,person_key)

                text = ReportUtils.born_str(self.database,ind,print_name,
                    self.EMPTY_DATE,self.EMPTY_PLACE)
                if text:
                    self.doc.write_text(text)
                    print_name = 0;

                age,units = self.calc_age(ind)
                text = ReportUtils.died_str(self.database,ind,print_name,
                    self.EMPTY_DATE,self.EMPTY_PLACE,age,units)
                if text:
                    self.doc.write_text(text)
                    print_name = 0;
                
                text = ReportUtils.buried_str(self.database,ind,print_name,
                        self.EMPTY_DATE,self.EMPTY_PLACE)
                if text:
                    self.doc.write_text(text)
                    print_name = 0;

                if print_name == 0:
                    print_name = firstName
                self.write_parents(ind, print_name)

                self.doc.end_paragraph()

            if person_name and mate.get_gender()==gen.lib.Person.MALE:
                if self.listChildren:
                    self.write_children(family)
                if self.includeEvents:
                    self.write_family_events(family)

    def calc_age(self,ind):
        """
        Calulate age. 
        
        Returns a tuple (age,units) where units is an integer representing
        time units:
            no age info:    0
            years:          1
            months:         2
            days:           3
        """
        if self.calcAgeFlag:
            return ReportUtils.old_calc_age(self.database,ind)
        else:
            return (0,0)

    def endnotes(self,obj):
        if not obj or not self.includeSources:
            return ""
        
        txt = Endnotes.cite_source(self.bibli,obj)
        if txt:
            txt = '<super>' + txt + '</super>'
        return txt

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class DetAncestorOptions(ReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        ReportOptions.__init__(self,name,person_id)

    def set_new_options(self):
        # Options specific for this report
        self.options_dict = {
            'gen'           : 10,
            'pagebbg'       : 0,
            'fulldates'     : 1,
            'listc'         : 1,
            'incnotes'      : 1,
            'incattrs'      : 0,
            'usecall'       : 1,
            'repplace'      : 0,
            'repdate'       : 0,
            'computeage'    : 1,
            'omitda'        : 1,
            'desref'        : 1,
            'incphotos'     : 0,
            'incnames'      : 0,
            'incevents'     : 0,
            'incaddresses'  : 0,
            'incsources'    : 0,
        }
        self.options_help = {
            'gen'           : ("=int","Generations",
                            "The number of generations to include in the report",
                            True),
            'pagebbg'       : ("=0/1","Page Break Between Generations",
                            ["No line break", "Insert line break"],
                            False),
            'fulldates'     : ("=0/1","Whether to use full dates instead of just year.",
                            ["Do not use full dates","Use full dates"],
                            True),
            'listc'         : ("=0/1","Whether to list children.",
                            ["Do not list children","List children"],
                            True),
            'incnotes'      : ("=0/1","Whether to include notes.",
                            ["Do not include notes","Include notes"],
                            True),
            'incattrs'      : ("=0/1","Whether to include attributes.",
                            ["Do not include attributes","Include attributes"],
                            True),
            'usecall'       : ("=0/1","Whether to use the call name as the first name.",
                            ["Do not use call name","Use call name"],
                            True),
            'repplace'      : ("=0/1","Whether to replace missing Places with blanks.",
                            ["Do not replace missing Places","Replace missing Places"],
                            True),
            'repdate'       : ("=0/1","Whether to replace missing Dates with blanks.",
                            ["Do not replace missing Dates","Replace missing Dates"],
                            True),
            'computeage'    : ("=0/1","Whether to compute age.",
                            ["Do not compute age","Compute age"],
                            True),
            'omitda'        : ("=0/1","Whether to omit duplicate ancestors.",
                            ["Do not omit duplicates","Omit duplicates"],
                            True),
            'desref'        : ("=0/1","Whether to add descendant references in child list.",
                            ["Do not add references","Add references"],
                            True),
            'incphotos'     : ("=0/1","Whether to include images.",
                            ["Do not include images","Include images"],
                            True),
            'incnames'      : ("=0/1","Whether to include other names.",
                            ["Do not include other names","Include other names"],
                            True),
            'incevents'     : ("=0/1","Whether to include events.",
                            ["Do not include events","Include events"],
                            True),
            'incaddresses': ("=0/1","Whether to include addresses.",
                            ["Do not include addresses","Include addresses"],
                            True),
            'incsources'    : ("=0/1","Whether to include source references.",
                            ["Do not include sources","Include sources"],
                            True),
        }

    def make_default_style(self,default_style):
        """Make the default output style for the Detailed Ancestral Report"""
        font = BaseDoc.FontStyle()
        font.set(face=BaseDoc.FONT_SANS_SERIF,size=16,bold=1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(BaseDoc.PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the title of the page.'))
        default_style.add_paragraph_style("DAR-Title",para)

        font = BaseDoc.FontStyle()
        font.set(face=BaseDoc.FONT_SANS_SERIF,size=14,italic=1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the generation header.'))
        default_style.add_paragraph_style("DAR-Generation",para)

        font = BaseDoc.FontStyle()
        font.set(face=BaseDoc.FONT_SANS_SERIF,size=10,italic=0, bold=1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_left_margin(1.0)   # in centimeters
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the children list title.'))
        default_style.add_paragraph_style("DAR-ChildTitle",para)

        font = BaseDoc.FontStyle()
        font.set(size=10)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=-0.75,lmargin=1.75)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the children list.'))
        default_style.add_paragraph_style("DAR-ChildList",para)

        font = BaseDoc.FontStyle()
        font.set(face=BaseDoc.FONT_SANS_SERIF,size=10,italic=0, bold=1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0,lmargin=1.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        default_style.add_paragraph_style("DAR-NoteHeader",para)

        para = BaseDoc.ParagraphStyle()
        para.set(lmargin=1.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style("DAR-Entry",para)

        para = BaseDoc.ParagraphStyle()
        para.set(first_indent=-1.0,lmargin=1.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the first personal entry.'))
        default_style.add_paragraph_style("DAR-First-Entry",para)

        font = BaseDoc.FontStyle()
        font.set(size=10,face=BaseDoc.FONT_SANS_SERIF,bold=1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0,lmargin=1.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the More About header.'))
        default_style.add_paragraph_style("DAR-MoreHeader",para)

        font = BaseDoc.FontStyle()
        font.set(face=BaseDoc.FONT_SERIF,size=10)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0,lmargin=1.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for additional detail data.'))
        default_style.add_paragraph_style("DAR-MoreDetails",para)

        Endnotes.add_endnote_styles(default_style)

    def add_user_options(self,dialog):
        """
        Override the base class add_user_options task to add a menu that allows
        the user to select the sort method.
        """
        self.max_gen = gtk.SpinButton(gtk.Adjustment(1,1,100,1))
        self.max_gen.set_value(self.options_dict['gen'])
        
        self.cb_pagebreak = gtk.CheckButton (_("Page break between generations"))
        self.cb_pagebreak.set_active (self.options_dict['pagebbg'])

        # Full date usage
        self.full_date_option = gtk.CheckButton(_("Use full dates instead of only the year"))
        self.full_date_option.set_active(self.options_dict['fulldates'])

        # Children List
        self.list_children_option = gtk.CheckButton(_("List children"))
        self.list_children_option.set_active(self.options_dict['listc'])

        # Print notes
        self.include_notes_option = gtk.CheckButton(_("Include notes"))
        self.include_notes_option.set_active(self.options_dict['incnotes'])
    
        # Print attributes
        self.include_attributes_option = gtk.CheckButton(_("Include attributes"))
        self.include_attributes_option.set_active(self.options_dict['incattrs'])

        # Print callname
        self.usecall = gtk.CheckButton(_("Use callname for common name"))
        self.usecall.set_active(self.options_dict['usecall'])

        # Replace missing Place with ___________
        self.place_option = gtk.CheckButton(_("Replace missing places with ______"))
        self.place_option.set_active(self.options_dict['repplace'])

        # Replace missing dates with __________
        self.date_option = gtk.CheckButton(_("Replace missing dates with ______"))
        self.date_option.set_active(self.options_dict['repdate'])

        # Add "Died at the age of NN" in text
        self.age_option = gtk.CheckButton(_("Compute age"))
        self.age_option.set_active(self.options_dict['computeage'])

        # Omit duplicate persons, occurs when distant cousins marry
        self.dupPersons_option = gtk.CheckButton(_("Omit duplicate ancestors"))
        self.dupPersons_option.set_active(self.options_dict['omitda'])

        #Add descendant reference in child list
        self.childRef_option = gtk.CheckButton(_("Add descendant reference in child list"))
        self.childRef_option.set_active(self.options_dict['desref'])

        #Add photo/image reference
        self.image_option = gtk.CheckButton(_("Include Photo/Images from Gallery"))
        self.image_option.set_active(self.options_dict['incphotos'])

        # Print alternative names
        self.include_names_option = gtk.CheckButton(_("Include alternative names"))
        self.include_names_option.set_active(self.options_dict['incnames'])

        # Print events
        self.include_events_option = gtk.CheckButton(_("Include events"))
        self.include_events_option.set_active(self.options_dict['incevents'])
        
        # Print addresses
        self.include_addresses_option = gtk.CheckButton(_("Include addresses"))
        self.include_addresses_option.set_active(self.options_dict['incaddresses'])

        # Print sources
        self.include_sources_option = gtk.CheckButton(_("Include sources"))
        self.include_sources_option.set_active(self.options_dict['incsources'])

        # Add new options. The first argument is the tab name for grouping options.
        # if you want to put everyting in the generic "Options" category, use
        # self.add_option(text,widget) instead of self.add_frame_option(category,text,widget)
        dialog.add_option(_('Generations'),self.max_gen)
        dialog.add_option ('', self.cb_pagebreak)
        dialog.add_frame_option(_('Content'),'',self.usecall)
        dialog.add_frame_option(_('Content'),'',self.full_date_option)
        dialog.add_frame_option(_('Content'),'',self.list_children_option)
        dialog.add_frame_option(_('Content'),'',self.age_option)
        dialog.add_frame_option(_('Content'),'',self.dupPersons_option)
        dialog.add_frame_option(_('Content'),'',self.childRef_option)
        dialog.add_frame_option(_('Include'),'',self.image_option)
        dialog.add_frame_option(_('Include'),'',self.include_notes_option)
        dialog.add_frame_option(_('Include'),'',self.include_attributes_option)
        dialog.add_frame_option(_('Include'),'',self.include_names_option)
        dialog.add_frame_option(_('Include'),'',self.include_events_option)
        dialog.add_frame_option(_('Include'),'',self.include_addresses_option)
        dialog.add_frame_option(_('Include'),'',self.include_sources_option)
        dialog.add_frame_option(_('Missing information'),'',self.place_option)
        dialog.add_frame_option(_('Missing information'),'',self.date_option)

    def parse_user_options(self,dialog):
        """
        Parses the custom options that we have added.
        """
        self.options_dict['gen'] = self.max_gen.get_value_as_int()
        self.options_dict['pagebbg'] = int(self.cb_pagebreak.get_active ())
        self.options_dict['fulldates'] = int(self.full_date_option.get_active())
        self.options_dict['listc'] = int(self.list_children_option.get_active())
        self.options_dict['incnotes'] = int(self.include_notes_option.get_active())
        self.options_dict['incattrs'] = int(self.include_attributes_option.get_active())
        self.options_dict['usecall'] = int(self.usecall.get_active())
        self.options_dict['repplace'] = int(self.place_option.get_active())
        self.options_dict['repdate'] = int(self.date_option.get_active())
        self.options_dict['computeage'] = int(self.age_option.get_active())
        self.options_dict['omitda'] = int(self.dupPersons_option.get_active())
        self.options_dict['desref'] = int(self.childRef_option.get_active())
        self.options_dict['incphotos'] = int(self.image_option.get_active())
        self.options_dict['incnames'] = int(self.include_names_option.get_active())
        self.options_dict['incevents'] = int(self.include_events_option.get_active())
        self.options_dict['incaddresses'] = int(self.include_addresses_option.get_active())
        self.options_dict['incsources'] = int(self.include_sources_option.get_active())

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
register_report(
    name = 'det_ancestor_report',
    category = CATEGORY_TEXT,
    report_class = DetAncestorReport,
    options_class = DetAncestorOptions,
    modes = MODE_GUI | MODE_BKI | MODE_CLI,
    translated_name = _("Detailed Ancestral Report"),
    status=(_("Beta")),
    description= _("Produces a detailed ancestral report"),
    author_name="Bruce DeGrasse",
    author_email="bdegrasse1@attbi.com"
    )
