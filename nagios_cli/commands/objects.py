from nagios_cli import objects
from nagios_cli.commands.base import Command
from nagios_cli.ui import Formatted
from nagios_cli.util import get_username


class Host(Command):
    def run(self, hostname=None):
        '''
        Switch to a host object.

        Usage: host

            Show the number of available hosts.

        Usage: host <hostname>

            Switch to host object.
        '''
        if not hostname:
            self.cli.sendline('%d hosts available' % (len(self.cli.objects.hosts),))
            self.cli.sendline('')
            self.cli.sendline('To switch objects, use: host <hostname>')
            return

        if hostname in self.cli.objects.hosts:
            self.cli.context.set(self.cli.objects.hosts[hostname])
            self.cli.setup_prompt()
        else:
            self.cli.error('Host "%s" not found' % (hostname,))

    def complete(self, text, state):
        if state == 0:
            part = text.split()
            if not part:
                self.matches = self.cli.objects.hosts.keys()
            elif len(part) == 1:
                self.matches = [hostname
                    for hostname in self.cli.objects.hosts
                    if hostname.startswith(part[0])]
            else:
                self.matches = []

            self.matches.sort()

        return self.matches


class Service(Command):
    is_global = False

    def valid_in_context(self, context):
        obj = context.get()
        return isinstance(obj, objects.Host)

    def run(self, service=None):
        '''
        Switch to service object.

        Usage: service

            Show available services in current host object.

        Usage: service <name>

            Switch to service object.
        '''

        host = self.cli.context.get()
        if not service:
            self.cli.sendline('%s services for this host' % (len(host.services),))
            self.cli.sendline('')
            format = Formatted(self.cli.ui)
            for service in sorted(host.services):
                name = host.services[service].service_description
                self.cli.sendline('%s: %s, %s' % (name.ljust(20, ' '),
                    format.to_state(host.services[service].current_state),
                    host.services[service].plugin_output[:48]))

        elif service in host.services:
            self.cli.context.add(host.services[service])
            self.cli.setup_prompt()

        else:
            self.cli.error('Service "%s" not found' % (service,))

    def complete(self, text, state):
        if state == 0:
            part = text.split()
            host = self.cli.context.get()
            if not part:
                self.matches = host.services.keys()
            elif len(part) == 1:
                self.matches = [service
                    for service in host.services
                    if service.startswith(part[0])]
            else:
                self.matches = []

            self.matches.sort()

        return self.matches


class Acknowledge(Command):
    is_global = False
        
    def valid_in_context(self, context):
        obj = context.get()
        return isinstance(obj, objects.Object)

    def run(self, comment=None, sticky=None, notify=None, persistent=None):
        '''
        Acknowledge a problem on a host/service object.

        Syntax:
            acknowledge <comment> [<sticky> [<notify> [<persistent>]]]

        Options:
            comment         textual comment
            sticky          the acknowledgement will remain until the object
                            returns to an UP state
            notify          notification will be sent out to contacts indicating
                            that the current host problem has been acknowledged
            persistent      the comment associated with the acknowledgement will
                            survive across restarts

        Example:
            acknowledge "Problem will be fixed" 1 1 0
        '''

        try:
            if comment is None:
                comment = self.cli.ask_str('comment', 15)
            if sticky is None:
                sticky = int(self.cli.ask_bool('sticky', 10, default=True))
            if notify is None:
                notify = int(self.cli.ask_bool('notify', 10, default=True))
            if persistent is None:
                persistent = int(self.cli.ask_bool('persistent', 10, default=True))
        except KeyboardInterrupt:
            self.cli.sendline('')
            self.cli.sendline('Aborted')
            return

        obj = self.cli.context.get()
        if isinstance(obj, objects.Host):
            self.run_host(obj, comment, sticky, notify, persistent)
        elif isinstance(obj, objects.Service):
            self.run_service(obj, comment, sticky, notify, persistent)

    def run_host(self, obj, comment, sticky, notify='1', persistent='1'):
        self.cli.command('ACKNOWLEDGE_HOST_PROBLEM',
            obj.host_name,
            sticky,
            notify,
            persistent,
            get_username(),
            comment)
        self.cli.sendline('Host problem acknowledged')

    def run_service(self, obj, comment, sticky, notify='1', persistent='1'):
        self.cli.command('ACKNOWLEDGE_SVC_PROBLEM',
            obj.host_name,
            obj.service_description,
            sticky,
            notify,
            persistent,
            get_username(),
            comment)
        self.cli.sendline('Host problem acknowledged')
            

class Status(Command):
    is_global = False

    def valid_in_context(self, context):
        obj = context.get()
        return isinstance(obj, objects.Object)

    def run(self):
        '''
        Show detailed status information about active object.
        '''

        obj = self.cli.context.get()
        if isinstance(obj, objects.Host):
            self.run_host(obj)
        elif isinstance(obj, objects.Service):
            self.run_service(obj)

    def run_host(self, instance):
        # Show info about host
        format = Formatted(self.cli.ui)
        fields = (
            ('host_name',           format.to_str),
            ('address',             format.to_str),
            ('current_state',       format.to_state),
            ('is_flapping',         format.to_bool),
            ('plugin_output',       format.to_str),
            ('last_check',          format.to_time),
            ('last_time_down',      format.to_time),
            ('last_state_change',   format.to_time),
            ('check_period',        format.to_str),
            ('notification_period', format.to_str),
            ('current_attempt',     format.to_str),
            ('max_attempts',        format.to_str),
        )
        for field, formatter in fields:
            value = instance.get(field)
            self.cli.sendline('%s: %s' % (field.ljust(20, ' ').replace('_', ' '),
                self.cli.ui.color('.'.join(['host', field]),
                    formatter(value))))

        # Show associated services and their status (in short version)
        for service in sorted(instance['services'].keys()):
            svc = instance['services'][service]
            self.cli.sendline('%s: %-20s %s' % ('service'.ljust(20, ' '),
                format.to_str(svc.service_description, max_length=20),
                format.to_state(svc.current_state)))

    def run_service(self, instance):
        # Show info about service
        format = Formatted(self.cli.ui)
        fields = (
            ('host_name',           format.to_str),
            ('service_description', format.to_str),
            ('current_state',       format.to_state),
            ('is_flapping',         format.to_bool),
            ('plugin_output',       format.to_str),
            ('last_time_down',      format.to_time),
            ('last_state_change',   format.to_time),
            ('last_check',          format.to_time),
            ('next_check',          format.to_time),
            ('check_interval',      format.to_str),
            ('check_latency',       format.to_str),
            ('check_period',        format.to_str),
            ('notification_period', format.to_str),
            ('current_attempt',     format.to_str),
            ('max_attempts',        format.to_str),
        )
        for field, formatter in fields:
            value = instance.get(field)
            self.cli.sendline('%s: %s' % (field.ljust(20, ' ').replace('_', ' '),
                self.cli.ui.color('.'.join(['service', field]),
                    formatter(value))))


# Default commands
DEFAULT = (
    # Host context
    Host('host'),   
    # Service context
    Service('service'),
    # Available in host/service context
    Acknowledge('acknowledge'),
    Status('status'),
    #Enable('enable'),
    #Disable('disable'),
)