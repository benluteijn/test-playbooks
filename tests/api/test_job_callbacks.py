import pytest
import uuid
import time
import httplib
import json
import urllib2
import common.tower.license
import common.utils
import common.exceptions
from tests.api import Base_Api_Test

# module-wide fixtures
pytestmark = pytest.mark.usefixtures('authtoken', 'backup_license', 'install_license_1000')

@pytest.fixture(scope="class")
def host_config_key():
    return str(uuid.uuid4())

@pytest.fixture(scope="function")
def inventory_localhost(request, authtoken, api_hosts_pg, random_inventory):
    payload = dict(name="localhost",
                   description="host-%s" % common.utils.random_unicode(),
                   inventory=random_inventory.id,)
    obj = api_hosts_pg.post(payload)
    request.addfinalizer(obj.delete)
    return obj

@pytest.fixture(scope="function")
def inventory_127001(request, authtoken, api_hosts_pg, random_inventory):
    payload = dict(name="127.0.0.1",
                   description="host-%s" % common.utils.random_unicode(),
                   inventory=random_inventory.id,)
    obj = api_hosts_pg.post(payload)
    request.addfinalizer(obj.delete)
    return obj

@pytest.fixture(scope="function")
def inventory_current(request, authtoken, api_hosts_pg, random_inventory):
    my_ip = json.load(urllib2.urlopen('http://httpbin.org/ip'))['origin']
    payload = dict(name=my_ip,
                   description="test host %s" % common.utils.random_unicode(),
                   inventory=random_inventory.id,)
    obj = api_hosts_pg.post(payload)
    request.addfinalizer(obj.delete)
    return obj

@pytest.fixture(scope="function")
def random_job_template_with_limit(request, authtoken, api_job_templates_pg, random_project, random_inventory, random_ssh_credential):
    '''Create a job_template with a valid machine credential, but a limit parameter that matches nothing'''

    payload = dict(name="job_template-%s" % common.utils.random_unicode(),
                   description="Random job_template with limit - %s" % common.utils.random_unicode(),
                   inventory=random_inventory.id,
                   job_type='run',
                   project=random_project.id,
                   limit='No_Match',
                   credential=random_ssh_credential.id,
                   playbook='site.yml', ) # This depends on the project selected
    obj = api_job_templates_pg.post(payload)
    request.addfinalizer(obj.delete)
    return obj

@pytest.mark.skip_selenium
@pytest.mark.destructive
class Test_Job_Callback(Base_Api_Test):
    def test_config(self, random_job_template, random_job_template_no_credential, host_config_key):
        '''Configure job_template(s) to allow callbacks'''
        template_pg = random_job_template.patch(allow_callbacks=True, host_config_key=host_config_key)
        assert template_pg.host_config_key == host_config_key

        template_pg = random_job_template_no_credential.patch(allow_callbacks=True, host_config_key=host_config_key)
        assert template_pg.host_config_key == host_config_key

    def test_get(self, api_jobs_pg, ansible_runner, random_job_template, inventory_current, host_config_key):
        '''Assert a GET on the /callback resource returns a list of matching hosts'''
        assert random_job_template.host_config_key == host_config_key
        callback_pg = random_job_template.get_related('callback')
        assert callback_pg.host_config_key == host_config_key
        all_inventory_hosts = inventory_current.get_related('inventory').get_related('hosts')
        assert len(callback_pg.matching_hosts) == all_inventory_hosts.count
        for inv_host in all_inventory_hosts.results:
            assert inv_host.name in callback_pg.matching_hosts

    def test_launch_nohosts(self, api_jobs_pg, ansible_runner, random_job_template, host_config_key):
        '''Verify launch failure when no matching inventory host can be found'''
        assert random_job_template.host_config_key == host_config_key
        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template.json['related']['callback'],
                    body="host_config_key=%s" % host_config_key,)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['failed']
        assert result['status'] == httplib.BAD_REQUEST
        assert result['json']['msg'] == 'No matching host could be found!'

    def test_launch_badkey(self, api_jobs_pg, ansible_runner, random_job_template, inventory_localhost, host_config_key):
        '''Verify launch failure when providing incorrect host_config_key'''
        assert random_job_template.host_config_key == host_config_key
        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template.json['related']['callback'],
                    body="host_config_key=BOGUS",)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['failed']
        assert result['status'] == httplib.FORBIDDEN
        assert result['json']['detail'] == 'You do not have permission to perform this action.'

    def test_launch_no_credential(self, api_jobs_pg, ansible_runner, random_job_template_no_credential, inventory_localhost, host_config_key):
        '''Verify launch failure when launching a job_template with no credentials'''
        assert random_job_template_no_credential.host_config_key == host_config_key
        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template_no_credential.json['related']['callback'],
                    body="host_config_key=%s" % host_config_key,)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['failed']
        assert result['status'] == httplib.BAD_REQUEST
        assert result['json']['msg'] == 'Cannot start automatically, user input required!'

    def test_launch_multiple_hosts(self, api_jobs_pg, ansible_runner, random_job_template_no_credential, inventory_localhost, inventory_127001, host_config_key):
        '''Verify launch failure when launching a job_template where multiple hosts match '''

        assert random_job_template_no_credential.host_config_key == host_config_key
        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template_no_credential.json['related']['callback'],
                    body="host_config_key=%s" % host_config_key,)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['failed']
        assert result['status'] == httplib.BAD_REQUEST
        assert result['json']['msg'] == 'Multiple hosts matched the request!'

    def test_launch_success_limit(self, api_jobs_pg, ansible_runner, random_job_template_with_limit, inventory_localhost, host_config_key):
        '''Assert that launching a callback job against a job_template with an existing 'limit' parameter successfully launches, but the job fails because no matching hosts were found.'''

        random_job_template_with_limit = random_job_template_with_limit.patch(host_config_key=host_config_key)
        assert random_job_template_with_limit.host_config_key == host_config_key

        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template_with_limit.json['related']['callback'],
                    body="host_config_key=%s" % host_config_key,)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['status'] == httplib.ACCEPTED
        assert not result['changed']
        assert 'failed' not in result, "Callback failed\n%s" % result
        assert result['content_length'].isdigit() and int(result['content_length']) == 0

        # FIXME - assert 'Location' header points to launched job
        # https://github.com/ansible/ansible-commander/commit/05febca0857aa9c6575a193072918949b0c1227b

        # Wait for job to complete
        jobs_pg = random_job_template_with_limit.get_related('jobs').get(launch_type='callback', order_by='-id')
        assert jobs_pg.count == 1
        job_pg = jobs_pg.results[0].wait_until_completed(timeout=4)

        assert job_pg.launch_type == "callback"

        # Assert job failed because no hosts were found
        assert job_pg.status == "failed"
        assert job_pg.result_stdout.startswith("ERROR: provided hosts list is empty")

    def test_launch_success(self, api_jobs_pg, ansible_runner, random_job_template, inventory_localhost, host_config_key):
        '''Assert that launching a callback job against a job_template with an existing 'limit' parameter successfully launches, and the job successfully runs on a single host..'''

        assert random_job_template.host_config_key == host_config_key
        args = dict(method="POST",
                    status_code=202,
                    url="http://localhost/%s" % random_job_template.json['related']['callback'],
                    body="host_config_key=%s" % host_config_key,)
        args["HEADER_Content-Type"] = "application/x-www-form-urlencoded"
        result = ansible_runner.uri(**args)

        assert result['status'] == httplib.ACCEPTED
        assert not result['changed']
        assert 'failed' not in result, "Callback failed\n%s" % result
        assert result['content_length'].isdigit() and int(result['content_length']) == 0

        # FIXME - assert 'Location' header points to launched job
        # https://github.com/ansible/ansible-commander/commit/05febca0857aa9c6575a193072918949b0c1227b

        # Wait for job to complete
        jobs_pg = random_job_template.get_related('jobs').get(launch_type='callback', order_by='-id')
        assert jobs_pg.count == 1
        job_pg = jobs_pg.results[0].wait_until_completed(timeout=4)

        assert job_pg.launch_type == "callback"

        # Make sure there is no traceback in result_stdout or result_traceback
        assert job_pg.is_successful, \
            "Job unsuccessful (%s)\nJob result_stdout: %s\nJob result_traceback: %s\nJob explanation: %s" % \
            (job_pg.status, job_pg.result_stdout, job_pg.result_traceback, job_pg.job_explanation)

        # Assert only a single host was affected
        host_summaries_pg = job_pg.get_related('job_host_summaries')
        assert host_summaries_pg.count == 1

        # Assert the expected host matches
        assert host_summaries_pg.results[0].host == job_pg.id
