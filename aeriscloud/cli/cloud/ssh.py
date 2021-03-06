import click
import shlex
import socket

from subprocess32 import call, check_output, CalledProcessError
from ansible.errors import AnsibleError

from aeriscloud.ansible import ACHost
from aeriscloud.cli.helpers import Command, fatal
from aeriscloud.cli.cloud import summary
from aeriscloud.log import get_logger
from aeriscloud.utils import quote

logger = get_logger('cloud.ssh')


def _services(ip, timeout, *extra_args):
    args = ['ssh', ip, '-t']

    if extra_args:
        args += list(extra_args)

    args += ['-o', 'StrictHostKeyChecking no',
             '-o', 'ConnectTimeout %d' % timeout,
             '-o', 'BatchMode yes',
             '--',
             'cat', '/etc/aeriscloud.d/*']

    try:
        return [
            dict(zip(
                ['name', 'port', 'path'],
                service.strip().split(',')
            ))
            for service in check_output(args).split('\n')
            if service
        ]
    except CalledProcessError:
        return []


def _ssh(ip, timeout, *args, **kwargs):
    call_args = [
        'ssh', ip, '-t', '-A']

    call_args += ['-o', 'ConnectTimeout %d' % timeout]

    if args:
        call_args += list(args)

    logger.info('Running %s' % ' '.join(map(quote, call_args)))

    return call(call_args, **kwargs)


def _services_args(services, ip):
    args = []

    click.secho('\nThe following SSH forwarding have automatically '
                'been made:\n', fg='green', bold=True)

    for service in services:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 0))
        _, local_port = s.getsockname()
        s.close()

        args += ['-L', '%s:%s:%s' % (
            local_port,
            ip,
            service['port'])
                 ]

        click.echo('%s @ ' % click.style(service['name'], fg='cyan'),
                   nl=False)

        if 'path' in service:
            click.secho('http://localhost:%s%s' % (
                local_port,
                service['path']
            ), fg='magenta')
        else:
            click.secho('localhost:%s' % local_port, fg='magenta')

    click.echo()

    return args


@click.command(cls=Command)
@click.option('--timeout', default=5)
@click.argument('inventory')
@click.argument('host')
@click.argument('extra', nargs=-1)
def cli(timeout, inventory, host, extra):
    """
    Connect to a remote server.
    """
    summary(inventory)

    user = None
    if '@' in host:
        (user, host) = host.split('@', 1)

    try:
        host = ACHost(inventory, host)
    except NameError as e:
        fatal(e.message)
    except IOError as e:
        fatal(e.message)
    except AnsibleError as e:
        fatal(e.message)

    ip = host.ssh_host()
    args = []

    hostvars = host.variables()
    if 'ansible_ssh_common_args' in hostvars:
        args += shlex.split(hostvars['ansible_ssh_common_args'])

    if user:
        args += ['-o', 'User %s' % user]

    services = _services(ip, timeout, *args)

    if services:
        args += _services_args(services, ip)

    if extra:
        args += ['--'] + list(extra)

    _ssh(ip, timeout, *args)


if __name__ == '__main__':
    cli()
