"""Base class for CLI tests.
"""
import pytest


@pytest.mark.skip_selenium
class BaseCLITest(object):
    """
    Base class for tower_cli tests
    """
    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        plugin = pytest.config.pluginmanager.getplugin("plugins.pytest_restqa.pytest_restqa")
        assert plugin, 'Unable to find pytest_restqa plugin'
        cls.testsetup = plugin.TestSetup

    @property
    def credentials(self):
        """convenient access to credentials"""
        return self.testsetup.credentials

    @property
    def api(self):
        """convenient access to api"""
        return self.testsetup.api

    @classmethod
    def teardown_class(cls):
        """
        Perform any required test teardown
        """

    def has_credentials(self, ctype, sub_ctype=None, fields=None):
        """
        assert whether requested credentials are present
        """

        # Make sure credentials.yaml has ctype we need
        assert ctype in self.testsetup.credentials, \
            "No '%s' credentials defined in credentals.yaml" % ctype
        creds = self.testsetup.credentials[ctype]

        # Ensure requested sub-type is present
        if sub_ctype:
            assert sub_ctype in creds, \
                "No '%s' '%s' credentials defined in credentals.yaml" % \
                (ctype, sub_ctype)
            creds = creds[sub_ctype]

        # Ensure requested fields are present
        if fields is not None:
            assert all([field in creds for field in fields]), \
                "Not all requested credential fields for section '%s' defined credentials.yaml" % \
                ctype

        return True
