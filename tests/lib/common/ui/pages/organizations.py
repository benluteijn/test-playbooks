from selenium.webdriver.common.by import By
from common.ui.pages import Base, BaseRegion
from common.ui.pages.forms import Form_Page, input_getter_by_name, input_setter_by_name
from common.ui.pages.regions.stream_container import Activity_Stream_Region
from common.ui.pages.regions.accordion import Accordion_Region, Accordion_Content
from common.ui.pages.regions.buttons import Activity_Stream_Button, Add_Button, Help_Button, Select_Button
from common.ui.pages.regions.lists import SortTable_Region
from common.ui.pages.regions.dialogs import Prompt_Dialog
from common.ui.pages.regions.search import Search_Region
from common.ui.pages.regions.pagination import Pagination_Region


class MainTab_Page(Base):
    '''Describes a main tab-based page which includes a search region, table and pagination'''
    _tab_title = "Organizations"
    _related = {
        'add': None,
        'edit': None,
        'delete': 'Prompt_Dialog',
        'activity_stream': None,
    }
    _locators = {
        'table': (By.CSS_SELECTOR, 'FIXME'),
        'pagination': (By.CSS_SELECTOR, 'FIXME'),
    }

    def open(self, id):
        # Using _tab_title in the following manner is lame
        super(MainTab_Page, self).open('/#/%s/%d' % (self._tab_title.lower(), id))
        return self.get_related('edit')(self.testsetup)

    @property
    def add_btn(self):
        return Add_Button(self.testsetup, _item_class=self.get_related('add'))

    @property
    def activity_stream_btn(self):
        return Activity_Stream_Button(self.testsetup, _item_class=self.get_related('activity_stream'))

    @property
    def table(self):
        # FIXME - doesn't work yet
        _region_map = {
            'edit-action': Organization_Edit_Page,
            'delete-action': Prompt_Dialog,
        }
        return SortTable_Region(self.testsetup, _root_locator=self._locators['table'], _region_map=_region_map)

    @property
    def pagination(self):
        return Pagination_Region(self.testsetup, _root_locator=self._locators['pagination'], _item_class=self.__class__)

    @property
    def search(self):
        return Search_Region(self.testsetup, _item_class=self.__class__)


class Organizations_Page(MainTab_Page):
    '''Describes organizations page'''
    _tab_title = "Organizations"
    _related = {
        'add': 'Organization_Create_Page',
        'edit': 'Organization_Edit_Page',
        'delete': 'Prompt_Dialog',
        'activity_stream': 'Organizations_Activity_Page',
    }
    _locators = {
        'table': (By.CSS_SELECTOR, '#organizations_table'),
        'pagination': (By.CSS_SELECTOR, '#organization-pagination'),
    }


class Organizations_Activity_Page(Activity_Stream_Region):
    '''Activity stream page for all organizations'''
    _tab_title = "Organizations"
    _related = {
        'close': 'Organizations_Page',
    }


class Organization_Create_Page(Form_Page):
    '''Describes the organization edit page'''

    _tab_title = "Organizations"
    _breadcrumb_title = 'Create Organization'
    _related = {
        'save': 'Organizations_Page',
    }
    _locators = {
        'name': (By.CSS_SELECTOR, '#organization_name'),
        'description': (By.CSS_SELECTOR, '#organization_description'),
        'save_btn': (By.CSS_SELECTOR, '#organization_save_btn'),
        'reset_btn': (By.CSS_SELECTOR, '#organization_reset_btn'),
    }

    name = property(input_getter_by_name('name'), input_setter_by_name('name'))
    description = property(input_getter_by_name('description'), input_setter_by_name('description'))


class Organization_Users_Page(Base):
    '''Describes the organization users page'''
    _tab_title = "Organizations"
    _breadcrumb_title = "Add Users"
    _related = {
        'add': 'FIXME',
        'help': 'FIXME',
    }
    _locators = {
        'table': (By.CSS_SELECTOR, '#users_table'),
    }

    @property
    def add_btn(self):
        return Add_Button(self.testsetup, _item_class=self.get_related('add'))

    @property
    def help_btn(self):
        return Help_Button(self.testsetup, _item_class=self.get_related('help'))

    @property
    def users(self):
        return SortTable_Region(self.testsetup, _root_locator=self._locators['table'])


class Organization_Admins_Page(Organization_Users_Page):
    '''Describes the organization admin page'''
    _tab_title = "Organizations"
    _breadcrumb_title = "Add Administrators"
    _locators = {
        'table': (By.CSS_SELECTOR, '#admins_table')
    }

    @property
    def help_btn(self):
        return Help_Button(self.testsetup, _item_class=self.get_related('help'))


class Organization_Edit_Page(Organization_Create_Page):
    _tab_title = "Organizations"
    _related = {
        'Properties': Organizations_Page.__module__ + '.Organization_Properties_Region',
        'Users': Organizations_Page.__module__ + '.Organization_Users_Region',
        'Administrators': Organizations_Page.__module__ + '.Organization_Administrators_Region',
    }

    @property
    def _breadcrumb_title(self):
        '''The breadcrumb title should always match organization name'''
        return self.name

    @property
    def accordion(self):
        '''Returns an Accordion_Region object describing the organization accordion'''
        return Accordion_Region(self.testsetup, _related=self._related)


class Organization_Properties_Region(BaseRegion, Organization_Create_Page):
    '''Describes the organization edit accordion region'''
    _related = Organization_Create_Page._related
    _related.update({
        'activity_stream': 'Organization_Activity_Page',
    })

    @property
    def activity_stream_btn(self):
        return Activity_Stream_Button(self.testsetup, _item_class=self.get_related('activity_stream'))


class Organization_Activity_Page(Activity_Stream_Region):
    '''Activity stream page for a single organizations'''
    _tab_title = "Organizations"
    _related = {
        'close': 'Organization_Edit_Page',
    }


class Organization_Users_Region(Accordion_Content):
    '''Describes the properties accordion region'''
    _tab_title = "Organizations"
    _related = {
        'add': 'Organization_Add_Users_Page',
    }


class Organization_Add_Users_Page(Base):
    '''Describes the page for adding users to an organization'''
    _tab_title = "Organizations"
    _breadcrumb_title = 'Add Users'
    _related = {
        'select': 'Organization_Edit_Page',
    }
    _locators = {
        'table': (By.CSS_SELECTOR, '#users_table'),
        'pagination': (By.CSS_SELECTOR, '#user-pagination'),
    }

    @property
    def help_btn(self):
        return Help_Button(self.testsetup)

    @property
    def select_btn(self):
        return Select_Button(self.testsetup, _item_class=self.get_related('select'))

    @property
    def table(self):
        return SortTable_Region(self.testsetup, _root_locator=self._locators['table'])

    @property
    def pagination(self):
        return Pagination_Region(self.testsetup, _root_locator=self._locators['pagination'], _item_class=self.__class__)

    @property
    def search(self):
        return Search_Region(self.testsetup, _item_class=self.__class__)


class Organization_Administrators_Region(Accordion_Content):
    '''Describes the admins accordion region'''
    _tab_title = "Organizations"
    _related = {
        'add': 'Organization_Add_Administrators_Page',
    }


class Organization_Add_Administrators_Page(Organization_Add_Users_Page):
    '''Describes the page for adding admins to an organization'''
    _breadcrumb_title = 'Add Administrators'
    _locators = {
        'table': (By.CSS_SELECTOR, '#admins_table'),
        'pagination': (By.CSS_SELECTOR, '#admin-pagination'),
    }
