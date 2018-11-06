"""# Create projects in /var/lib/awx/projects and verify
# 1) projects starting with '.' or '_' are excluded from config['project_local_paths']
# 2) project appears under config['project_local_paths']
"""

import os

import towerkit.exceptions as exc
import pytest
import fauxfactory

from tests.api import APITest


@pytest.fixture(scope="function")
def project_with_queued_updates(project_ansible_playbooks_git_nowait):
    # Initiate several project updates
    update_pg = project_ansible_playbooks_git_nowait.get_related('update')
    for i in range(4):
        update_pg.post({})
    return project_ansible_playbooks_git_nowait


@pytest.fixture(scope="function")
def project_with_galaxy_requirements(request, authtoken, organization):
    # Create project
    payload = dict(name="project-with-galaxy-requirements - %s" % fauxfactory.gen_utf8(),
                   scm_type='git',
                   scm_url='https://github.com/jlaska/ansible-playbooks',
                   scm_branch='with_requirements',
                   scm_clean=False,
                   scm_delete_on_update=False,
                   scm_update_on_launch=False,)
    obj = organization.get_related('projects').post(payload)
    request.addfinalizer(obj.silent_delete)
    return obj


@pytest.mark.api
@pytest.mark.destructive
@pytest.mark.usefixtures('authtoken', 'install_enterprise_license_unlimited')
class Test_Projects(APITest):

    def check_secret_fields(self, string_to_check, *secrets):
        for secret in secrets:
            assert secret not in string_to_check

    def get_project_update_galaxy_update_task(self, project, job_type='run'):
        task_icontains = "fetch galaxy roles from requirements.yml"
        res = project.related.project_updates.get(job_type=job_type, order_by='-created') \
                                             .results[0].related.events \
                                             .get(task__icontains=task_icontains, event__startswith='runner_on_', order_by='counter')
        assert 2 == res.count, \
                "Expected to find 2 job events matching task={},event__startswith={} for project update {}".format(
                        task_icontains, 'runner_on_', project.related.last_update)
        return (res.results)

    @pytest.mark.requires_single_instance
    def test_manual_project(self, project_ansible_playbooks_manual):
        """Verify tower can successfully creates a manual project (scm_type='').
        This includes verifying UTF-8 local-path.
        """
        # if we make it through the fixure, post worked
        # assert various project attributes are empty ('')
        for attr in ('scm_type', 'scm_url', 'scm_branch'):
            assert hasattr(project_ansible_playbooks_manual, attr), \
                "Unhandled project attribute: %s" % attr
            attr_value = getattr(project_ansible_playbooks_manual, attr)
            assert attr_value == '', \
                "Unexpected project.%s (%s != %s)" % \
                (attr, attr_value, '')

        # assert various project attributes are false
        for attr in ('scm_clean', 'scm_delete_on_update', 'last_job_failed',
                     'scm_update_on_launch', 'last_update_failed',):

            assert hasattr(project_ansible_playbooks_manual, attr), \
                "Unhandled project attribute: %s" % attr
            attr_value = getattr(project_ansible_playbooks_manual, attr)
            assert attr_value is False, \
                "Unexpected project.%s (%s != %s)" % \
                (attr, attr_value, False)

        # assert related.update.can_update == false
        update_pg = project_ansible_playbooks_manual.get_related('update')
        assert not update_pg.json['can_update'], \
            "Manual project incorrectly has can_update:%s" % \
            (update_pg.json['can_update'],)

        # assert related.project_updates.count == 0
        for related_attr in ('project_updates', 'schedules'):
            related_pg = project_ansible_playbooks_manual.get_related(related_attr)
            assert related_pg.count == 0, \
                "A manual project has %d %s, but should have %d %s" % \
                (related_pg.count, related_attr, 0, related_attr)

    # Override the project local_path to workaround unicode issues
    @pytest.mark.requires_single_instance
    @pytest.mark.fixture_args(local_path="project_dir_%s" % fauxfactory.gen_alphanumeric())
    def test_change_from_manual_to_scm_project(self, project_ansible_playbooks_manual):
        """Verify tower can successfully convert a manual project, into a scm
        managed project.
        """
        # change the scm_type to 'git'
        project_pg = project_ansible_playbooks_manual.patch(
            scm_type='git',
            scm_url='https://github.com/jlaska/ansible-playbooks.git',
        )

        # update the project and wait for completion
        latest_update_pg = project_pg.update().wait_until_completed()

        # assert project_update was successful
        assert latest_update_pg.is_successful, "Project update unsuccessful - %s" % latest_update_pg

        # update the project endpoint
        project_pg.get()

        # assert project is marked as successful
        assert project_pg.is_successful, "After a successful project update, " \
            "the project is not marked as successful - id:%s" % project_pg.id

    @pytest.mark.requires_single_instance
    @pytest.mark.ansible_integration
    def test_update_with_private_git_repository(self, ansible_runner, api_config_pg, project_ansible_docsite_git):
        """Tests that project updates succeed with private git repositories."""
        # find project path
        local_path = project_ansible_docsite_git.local_path
        expected_project_path = os.path.join(api_config_pg.project_base_dir, local_path)

        # assert project directory created
        contacted = ansible_runner.stat(path=expected_project_path)
        for result in contacted.values():
            assert result['stat']['exists'], "The expected project directory was not found (%s)." % \
                expected_project_path

    @pytest.mark.parametrize('timeout, status, job_explanation', [
        (0, 'successful', ''),
        (60, 'successful', ''),
        (1, 'failed', 'Job terminated due to timeout'),
    ], ids=['no timeout', 'under timeout', 'over timeout'])
    def test_update_with_timeout(self, project, timeout, status, job_explanation):
        """Tests project updates with timeouts."""
        project.patch(timeout=timeout)

        # launch project update and assess spawned update
        update_pg = project.update().wait_until_completed()
        assert update_pg.status == status, \
            "Unexpected project update status. Expected '{0}' but received '{1}.'".format(status, update_pg.status)
        assert update_pg.job_explanation == job_explanation, \
            "Unexpected update job_explanation. Expected '{0}' but received '{1}.'".format(job_explanation, update_pg.job_explanation)
        assert update_pg.timeout == project.timeout, \
            "Update_pg has a different timeout value ({0}) than its project ({1}).".format(update_pg.timeout, project.timeout)

    @pytest.mark.parametrize("scm_type,mod_kwargs", [
        ('hg', {'scm_branch': '09e81486069b4e38e62c24d7d7a529fc975d4a31'}),
        ('git', {'scm_branch': 'with_requirements'}),
        ('hg', {'scm_type': 'git', 'scm_url': 'https://github.com/jlaska/ansible-playbooks.git'}),
        ('git', {'scm_url': 'https://github.com/alancoding/ansible-playbooks.git'})
    ], ids=['hg-branch', 'git-branch', 'scm_type', 'git-url'])
    def test_auto_update_on_modification_of_scm_fields(self, factories, scm_type, mod_kwargs):
        project = factories.v2_project(scm_type=scm_type)
        assert project.related.project_updates.get().count == 1

        # verify that changing update-relevant parameters causes new update
        project.patch(**mod_kwargs)
        assert project.related.project_updates.get().count == 2

    def test_cancel_queued_update(self, project_ansible_git_nowait):
        """Verify the project->current_update->cancel endpoint behaves as expected when canceling a
        queued project_update.  Note, the project_ansible_git repo is used
        because the repo is large enough that the git-clone should take enough
        time to trigger a project_update cancel.
        """
        update_pg = project_ansible_git_nowait.get_related('current_update')
        cancel_pg = update_pg.get_related('cancel')
        assert cancel_pg.can_cancel, "Unable to cancel project_update (can_cancel:%s)" % cancel_pg.can_cancel

        # cancel job
        cancel_pg.post()

        # wait for project_update to complete
        update_pg = update_pg.wait_until_completed()

        # assert project_update status is canceled
        assert update_pg.status == 'canceled', "Unexpected project_update " \
            "status after cancelling project update (expected status:canceled) " \
            "- %s" % update_pg

        # update project resource
        project_ansible_git_nowait = project_ansible_git_nowait.wait_until_completed()

        # assert project status is failed
        assert project_ansible_git_nowait.status == 'canceled', \
            "Unexpected project status after cancelling project update" \
            "(expected status:canceled) - %s" % project_ansible_git_nowait

    def test_cancel_running_update(self, project_ansible_git_nowait):
        """Verify the project->current_update->cancel endpoint behaves as expected
        when canceling a running project_update.  Note, the project_ansible_git
        repo is used because the repo is large enough that the git-clone should
        take enough time to trigger a project_update cancel.
        """
        update_pg = project_ansible_git_nowait.get_related('current_update')
        cancel_pg = update_pg.get_related('cancel')
        assert cancel_pg.can_cancel, "Unable to cancel project_update (can_cancel:%s)" % cancel_pg.can_cancel

        # wait for project_update to be running
        update_pg = update_pg.wait_until_status('running')

        # cancel job
        cancel_pg.post()

        # wait for project_update to complete
        # ansible.git includes submodules, which can take time to update
        update_pg = update_pg.wait_until_completed(timeout=60 * 4)

        # assert project_update status is canceled
        assert update_pg.status == 'canceled', "Unexpected project_update " \
            "status after cancelling project update (expected status:canceled) " \
            "- %s" % update_pg

        # update project resource
        project_ansible_git_nowait = project_ansible_git_nowait.wait_until_completed()

        # assert project status is failed
        assert project_ansible_git_nowait.status == 'canceled', "Unexpected " \
            "project status after cancelling project update (expected " \
            "status:canceled) - %s" % project_ansible_git_nowait

    def test_update_cascade_delete(self, project_ansible_playbooks_git, api_project_updates_pg):
        """Verify that associated project updates get cascade deleted with project
        deletion.
        """
        project_id = project_ansible_playbooks_git.id

        # assert that we have a project update
        assert api_project_updates_pg.get(project=project_id).count == 1, \
            "Unexpected number of project updates. Expected one update."

        # delete project and assert that project updates deleted
        project_ansible_playbooks_git.delete()
        assert api_project_updates_pg.get(project=project_id).count == 0, \
            "Unexpected number of project updates after deleting project. Expected zero updates."

    def test_conflict_exception_with_running_project_update(self, factories):
        project = factories.v2_project()
        update = project.update()

        with pytest.raises(exc.Conflict) as e:
            project.delete()
        assert e.value[1] == {'error': 'Resource is being used by running jobs.', 'active_jobs': [{'type': 'project_update', 'id': update.id}]}

        assert update.wait_until_completed().is_successful
        assert project.get().is_successful

    def test_delete_related_fields(self, install_enterprise_license_unlimited, project_ansible_playbooks_git):
        """Verify that related fields on a deleted resource respond as expected"""
        # delete all the projects
        project_ansible_playbooks_git.delete()

        # assert related resources are notfound (404)
        for related in ('last_job', 'last_update', 'schedules', 'activity_stream', 'project_updates', 'teams', 'playbooks', 'update'):
            with pytest.raises(exc.NotFound):
                assert project_ansible_playbooks_git.get_related(related)

    @pytest.mark.requires_single_instance
    @pytest.mark.ansible_integration
    def test_project_with_galaxy_requirements(self, factories, ansible_runner, project_with_galaxy_requirements, api_config_pg):
        """Verify that project requirements are downloaded when specified in a requirements file."""
        last_update_pg = project_with_galaxy_requirements.wait_until_completed().get_related('last_update')
        assert last_update_pg.is_successful, "Project update unsuccessful - %s" % last_update_pg

        # create a JT with our project and launch a job with this JT
        # note: we do this since only 'run' project updates download galaxy roles
        job_template_pg = factories.job_template(project=project_with_galaxy_requirements, playbook="debug.yml")
        job_pg = job_template_pg.launch().wait_until_completed()
        assert job_pg.is_successful, "Job unsuccessful - %s." % job_pg

        # assert that expected galaxy requirements were downloaded
        expected_role_path = os.path.join(api_config_pg.project_base_dir,
                                          last_update_pg.local_path, "roles/yatesr.timezone")
        contacted = ansible_runner.stat(path=expected_role_path)
        for result in contacted.values():
            assert result['stat']['exists'], "The expected galaxy role requirement was not found (%s)." % \
                expected_role_path

    def test_project_with_galaxy_requirements_processed_on_scm_change(self, factories, job_template_that_writes_to_source):
        project_with_requirements = factories.v2_project(scm_url='https://github.com/jlaska/ansible-playbooks.git',
                                                         scm_branch='with_requirements')
        jt_with_requirements = factories.v2_job_template(project=project_with_requirements,
                                                         playbook='debug.yml')

        assert jt_with_requirements.launch().wait_until_completed().is_successful, \
            "First job template run for a project always triggers the processing of requirements.yml"
        assert job_template_that_writes_to_source.launch().wait_until_completed().is_successful, \
            "Failed to update remote repository with a commit. This is needed to trigger processing of requirements.yml"
        assert project_with_requirements.update().wait_until_completed().is_successful, \
            "Project update that pulls down newly written SCM commits failed."

        assert jt_with_requirements.launch().wait_until_completed().is_successful, \
            "Job Template that triggers SCM update that processes requirements.yml failed"
        (event_unforced, event_forced) = self.get_project_update_galaxy_update_task(project_with_requirements)

        assert 'runner_on_ok' in [event_unforced.event, event_forced.event]

    @pytest.mark.parametrize("scm_params", [
        dict(scm_clean=False, scm_delete_on_update=False),
        dict(scm_clean=True, scm_delete_on_update=False),
        dict(scm_clean=False, scm_delete_on_update=True),
    ], ids=('first_time', 'scm_clean', 'scm_delete_on_update'))
    def test_project_with_galaxy_requirements_updated_when(self, factories, scm_params):
        project = factories.v2_project(scm_url='https://github.com/jlaska/ansible-playbooks.git',
                                       scm_branch='with_requirements',
                                       scm_update_on_launch=False,
                                       **scm_params)

        (event_unforced, event_forced) = self.get_project_update_galaxy_update_task(project, job_type='check')
        assert False is event_unforced.changed, \
            "Project update of type check should never process requirements.yml"
        assert False is event_forced.changed, \
            "Project update of type check should never process requirements.yml"

        jt = factories.v2_job_template(project=project, playbook='debug.yml')

        assert jt.launch().wait_until_completed().is_successful, \
            "Job Template that triggers SCM update that processes requirements.yml failed"
        (event_unforced, event_forced) = self.get_project_update_galaxy_update_task(project)
        assert 'runner_on_ok' == event_unforced.event, \
            "Empty project directory expected to trigger the processing of requirements.yml"
        assert True is event_unforced.changed, \
            "Empty project directory expected to trigger the processing of requirements.yml"
        assert 'runner_on_skipped' == event_forced.event

        assert 'runner_on_ok' in [event_unforced.event, event_forced.event]
        assert True in [event_unforced.changed, event_forced.changed]

    @pytest.mark.parametrize("scm_url, use_credential",
                             [('https://github.com/ansible/tower.git', True),
                              ('https://github.com/jlaska/ansible-playbooks.git', True),
                              ('https://foobar:barfoo@github.com/ansible/tower.git', False)],
                             ids=['invalid_cred', 'valid_cred', 'cred_in_url'])
    def test_project_update_results_do_not_leak_credential(self, factories, scm_url, use_credential):
        if use_credential:
            cred = factories.v2_credential(kind='scm', username='foobar', password='barfoo')
        else:
            cred = None
        project = factories.v2_project(credential=cred, scm_url=scm_url)
        pu = project.related.project_updates.get().results.pop()
        assert pu.is_completed

        self.check_secret_fields(pu.result_stdout, 'foobar', 'barfoo')
        events = pu.related.events.get(page_size=200).results
        for event in events:
            self.check_secret_fields(event.stdout, 'foobar', 'barfoo')
            self.check_secret_fields(str(event.event_data), 'foobar', 'barfoo')

    @pytest.mark.requires_single_instance
    @pytest.mark.ansible_integration
    def test_git_project_from_file_path(self, request, factories, ansible_runner):
        """Confirms that local file paths can be used for git repos"""
        path = '/home/at_3207_test/'
        request.addfinalizer(lambda: ansible_runner.file(path=path, state='absent'))
        sync = ansible_runner.git(repo='git://github.com/jlaska/ansible-playbooks.git', dest=path)
        rev = sync.values().pop()['after']
        assert rev
        project = factories.project(scm_url='file://{0}'.format(path))
        assert project.is_successful
        assert project.scm_revision == rev
