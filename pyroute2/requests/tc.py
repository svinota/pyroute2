from pyroute2.netlink.rtnl.tcmsg import plugins as tc_plugins

from .common import IPRouteFilter


class TcRequestFilter:
    def transform_handle(self, key, context, handle):
        if isinstance(handle, str):
            (major, minor) = [
                int(x if x else '0', 16) for x in handle.split(':')
            ]
            handle = (major << 8 * 2) | minor
        return {key: handle}

    def set_handle(self, context, value):
        return self.transform_handle('handle', context, value)

    def set_target(self, context, value):
        return self.transform_handle('target', context, value)

    def set_parent(self, context, value):
        return self.transform_handle('parent', context, value)

    def set_default(self, context, value):
        return self.transform_handle('default', context, value)


class TcIPRouteFilter(IPRouteFilter):

    def finalize(self, context):

        if self.command.startswith('dump'):
            context.pop('kind', None)
            return

        if 'index' not in context:
            context['index'] = 0
        if 'handle' not in context:
            context['handle'] = 0

        # get & run the plugin
        if 'kind' in context and context['kind'] in tc_plugins:
            plugin = tc_plugins[context['kind']]
            context['parent'] = context.get(
                'parent', getattr(plugin, 'parent', 0)
            )
            if set(context.keys()) > set(('kind', 'index', 'handle')):
                if self.command[-5:] == 'class':
                    context['options'] = plugin.get_class_parameters(context)
                else:
                    context['options'] = plugin.get_parameters(context)
            if hasattr(plugin, 'fix_request'):
                plugin.fix_request(context)
