import functools
import json
import os
import stat
import re

from awxkit import config
import pytest


result_to_str = functools.partial(json.dumps, indent=2, sort_keys=True)


@pytest.fixture(scope='session')
def ansible_collections_path(is_docker):
    """Return the ansible collections path to use depending on the deployment.

    See https://github.com/ansible/ansible/blob/stable-2.9/lib/ansible/config/base.yml#L221.
    """

    if is_docker:
        return '~/.ansible/collections'

    return '/usr/share/ansible/collections'


def _run_uninstall_tower_modules_collection(ansible_adhoc, collection_path):
    collection_install_path = os.path.join(collection_path, 'ansible_collections', 'awx')
    ansible_adhoc.shell('rm -rf {}'.format(collection_install_path))


@pytest.fixture(scope='class')
def tower_modules_collection(request, modified_ansible_adhoc, ansible_collections_path, is_docker):
    '''
    Emulate ansible 2.9 ansible-galaxy collection install. This fixture exists
    because the aforementioned command doesn't yet exist. Thus, our emulation.
    '''
    # On cluster deployments target the `cluster_installer` group which is the
    # group that contains the host that the API calls will be made during
    # testing. This is important, specially for the manual project test,
    # because it needs that a local directory is present on the host's
    # filesystem that is receiving the API call. On the other hand, for
    # standalone deployments the target group should be `tower`
    if not is_docker:
        return

    # Default to installing awx collection from ansible awx repo
    fork = os.environ.get('TOWER_FORK', 'ansible')
    product = os.environ.get('PRODUCT', 'awx')
    branch = os.environ.get('TOWER_BRANCH', 'devel')
    if product == 'tower':
        pytest.skip("Installing the tower collection in docker is not supported")

    ansible_path = ''
    # If we set the venv_group in fixture_args, override the defaults
    fixture_args = request.node.get_closest_marker('fixture_args')
    if fixture_args and fixture_args.kwargs.get('venv_group'):
        limit = fixture_args.kwargs.get('venv_group')
        ansible_adhoc = modified_ansible_adhoc()[limit]
        if os.getenv('VIRTUAL_ENV'):
            venv_path = os.getenv('VIRTUAL_ENV')
            if os.path.exists(os.path.join(venv_path, 'bin', 'ansible-playbook')) and os.path.exists(os.path.join(venv_path, 'bin', 'ansible-galaxy')):
                ansible_path = os.path.join(venv_path, 'bin')
    else:
        try:
            ansible_adhoc = modified_ansible_adhoc()['cluster_installer']
        except KeyError:
            ansible_adhoc = modified_ansible_adhoc()['tower']

    ansible_galaxy_bin = os.path.join(ansible_path, 'ansible-galaxy')
    ansible_playbook_bin = os.path.join(ansible_path, 'ansible-playbook')

    if not config.prevent_teardown:
        uninstall_tower_modules_collection = functools.partial(
            _run_uninstall_tower_modules_collection, ansible_adhoc, ansible_collections_path)
        request.addfinalizer(uninstall_tower_modules_collection)

    try:
        contacted = ansible_adhoc.file(
            dest=ansible_collections_path,
            recurse=True,
            state='directory',
        )
        for result in contacted.values():
            assert result.get('state', None) == 'directory', result_to_str(result)

        build_dir = os.path.join(ansible_collections_path, 'build')

        git_result = ansible_adhoc.git(
            repo=f'https://github.com/{fork}/{product}.git',
            version=f'{branch}',
            depth=1,
            dest=build_dir,
            force=True
        )
        for result in git_result.values():
            assert (result.get('before') or result.get('after')), result_to_str(result)

        # TODO: optionally build as awx or tower
        contacted = ansible_adhoc.shell((
            '{} -i localhost, awx_collection/template_galaxy.yml '
            '-e collection_package=awx -e collection_namespace=awx -e collection_version=0.0.1'.format(ansible_playbook_bin)
        ), chdir=build_dir)
        for result in contacted.values():
            assert result.get('rc', None) == 0, result_to_str(result)

        contacted = ansible_adhoc.shell(
            '{} collection build --force'.format(
                ansible_galaxy_bin
            ),
            chdir=os.path.join(build_dir, 'awx_collection')
        )
        for result in contacted.values():
            assert result.get('rc', None) == 0, result_to_str(result)
            stdout = result['stdout']
            assert 'Created collection' in stdout
            package_name = re.search(r'\b([a-z0-9\.-]*\.tar\.gz)\b', stdout).group(1)

        contacted = ansible_adhoc.shell(
            '{} collection install {} -p {} --force'.format(
                ansible_galaxy_bin,
                os.path.join(build_dir, 'awx_collection', package_name), ansible_collections_path
            )
        )
        for result in contacted.values():
            assert result.get('rc', None) == 0, result_to_str(result)
        contacted = ansible_adhoc.file(
            dest=ansible_collections_path,
            mode=stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
            recurse=True,
            state='directory',
        )
        for result in contacted.values():
            assert result.get('mode', None) == '0755', result_to_str(result)
    except AssertionError as e:
        pytest.fail(
            'Failed to install awx.awx\n{}'.format(e)
        )
