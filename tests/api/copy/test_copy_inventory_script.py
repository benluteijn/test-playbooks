import pytest

from tests.api import Base_Api_Test
from tests.lib.helpers.copy_utils import check_identical_fields, check_unequal_fields


@pytest.mark.api
@pytest.mark.usefixtures('authtoken', 'install_enterprise_license_unlimited')
class Test_Copy_Inventory_Script(Base_Api_Test):

    identical_fields = ['type', 'description', 'script', 'organization']
    unequal_fields = ['id', 'created', 'modified']

    def test_copy_normal(self, copy_for_test, factories):
        v2_inventory_script = factories.v2_inventory_script()
        new_inventory_script = copy_for_test(v2_inventory_script)
        check_identical_fields(v2_inventory_script, new_inventory_script, self.identical_fields)
        check_unequal_fields(v2_inventory_script, new_inventory_script, self.unequal_fields)
