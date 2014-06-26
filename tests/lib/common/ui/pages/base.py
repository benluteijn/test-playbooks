#!/usr/bin/env python

import page
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

class Base(page.Page):
    '''
    Base class for global project specific functions
    '''
    @property
    def page_title(self):
        WebDriverWait(self.selenium, self.timeout).until(lambda s: self.selenium.title)
        return self.selenium.title

    @property
    def header(self):
        return Base.HeaderRegion(self.testsetup)

    @property
    def flash(self):
        return Base.FlashRegion(self.testsetup)

    @property
    def is_logged_in(self):
        return self.header.is_logged_in

    @property
    def current_subpage(self):
        submenu_name = self.selenium.find_element_by_tag_name("body").get_attribute("id")
        return self.submenus[submenu_name](self.testsetup)  # IGNORE:E1101

    @property
    def csrf_token(self):
        csrf_meta = self.selenium.find_element_by_css_selector("meta[name=csrf-token]")
        return csrf_meta.get_attribute('content')

    @csrf_token.setter
    def csrf_token(self, value):
        # Changing the CSRF Token on the fly via the DOM by iterating
        # over the meta tags
        script = '''
            var elements = document.getElementsByTagName("meta");
            for (var i=0, element; element = elements[i]; i++) {
                var ename = element.getAttribute("name");
                if (ename != null && ename.toLowerCase() == "csrf-token") {
                    element.setAttribute("content", "%s");
                    break;
                }
            }
        ''' % value
        self.selenium.execute_script(script)

    def go_to_login_page(self):
        self.selenium.get(self.base_url)

    class HeaderRegion(page.Page):
        # LoggedIn
        _logout_link_locator = (By.ID, "main_logout")
        _user_indicator_locator = (By.ID, "main_view_user")
        _site_navigation_menus_locator = (By.CSS_SELECTOR, "#main_tabs > li")
        _site_navigation_min_number_menus = 8

        @property
        def is_logout_visible(self):
            return self.is_element_visible(*self._logout_link_locator)

        @property
        def is_logged_in(self):
            return self.is_element_visible(*self._user_indicator_locator) and self.is_logout_visible

        def logout(self):
            logout_link = options.find_element(*self._logout_link_locator)
            ActionChains(self.selenium).move_to_element(logout_link).click().perform()
            from login import LoginPage
            return LoginPage(self.testsetup)

        def site_navigation_menu(self, value):
            # used to access on specific menu
            for menu in self.site_navigation_menus:
                if menu.name == value:
                    return menu
            raise Exception("Menu not found: '%s'. Menus: %s" % (value, [menu.name for menu in self.site_navigation_menus]))

        @property
        def site_navigation_menus(self):
            # returns a list containing all the site navigation menus
            WebDriverWait(self.selenium, self.timeout).until(
                lambda s: len(s.find_elements(*self._site_navigation_menus_locator))
                >= self._site_navigation_min_number_menus)
            from regions.header_menu import HeaderMenu
            return [HeaderMenu(self.testsetup, web_element) for web_element in self.selenium.find_elements(*self._site_navigation_menus_locator)]

    class FlashRegion(page.Page):
        _flash_div_locator = (By.CSS_SELECTOR, "div#flash_text_div")
        _flash_message_locator = (By.CSS_SELECTOR, "ul li")

        def __init__(self, setup):
            self.testsetup = setup
            self._root_element = self.testsetup.selenium.find_element(*self._flash_div_locator)

        @property
        def message(self):
            return self._root_element.find_element(*self._flash_message_locator).text
