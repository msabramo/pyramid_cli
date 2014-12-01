import click
from pyramid.config import Configurator
from pyramid.interfaces import IRouteRequest
from pyramid.interfaces import IViewClassifier
from pyramid.interfaces import IView
from zope.interface import Interface


PAD = 3
ANY_KEY = '*'
UNKNOWN_KEY = '<unknown>'


def _get_mapper(registry):
    config = Configurator(registry=registry)
    return config.get_routes_mapper()


def _get_print_format(max_name, max_pattern, max_view, max_method):
    fmt = '%-{0}s %-{1}s %-{2}s %-{3}s'.format(
        max_name + PAD,
        max_pattern + PAD,
        max_view + PAD,
        max_method + PAD,
    )
    return fmt


def _get_request_methods(route_request_methods, view_request_methods):
    has_route_methods = route_request_methods is not None
    has_view_methods = len(view_request_methods) > 0
    has_methods = has_route_methods or has_view_methods

    if has_route_methods is False and has_view_methods is False:
        request_methods = [ANY_KEY]
    elif has_route_methods is False and has_view_methods is True:
        request_methods = view_request_methods
    elif has_route_methods is True and has_view_methods is False:
        request_methods = route_request_methods
    else:
        request_methods = set(route_request_methods).intersection(
            view_request_methods
        )

    if has_methods and not request_methods:
        request_methods = '<route mismatch>'
    elif request_methods:
        request_methods = ','.join(request_methods)

    return request_methods


def _get_view_module(view_callable):
    if view_callable is None:
        return UNKNOWN_KEY

    if hasattr(view_callable, '__name__'):
        view_name = view_callable.__name__
    else:
        view_name = str(view_callable)

    view_module = '%s.%s' % (
        view_callable.__module__,
        view_name,
    )

    # If pyramid wraps something in wsgiapp or wsgiapp2 decorators
    # that is currently returned as pyramid.router.decorator, lets
    # hack a nice name in:
    if view_module == 'pyramid.router.decorator':
        view_module = 'wsgiapp'

    return view_module


def get_route_data(route, registry):
    pattern = route.pattern

    if not pattern.startswith('/'):
        pattern = '/%s' % pattern

    request_iface = registry.queryUtility(
        IRouteRequest,
        name=route.name
    )
    route_request_methods = None
    view_request_methods = {}
    view_callable = None

    route_intr = registry.introspector.get(
        'routes', route.name
    )

    view_callable = registry.adapters.lookup(
        (IViewClassifier, request_iface, Interface),
        IView,
        name='',
        default=None
    )
    view_module = _get_view_module(view_callable)
    # Introspectables can be turned off, so there could be a chance
    # that we have no `route_intr` but we do have a route + callable
    if route_intr is None:
        view_request_methods[view_module] = []
    else:
        route_request_methods = route_intr['request_methods']

        view_intr = registry.introspector.related(route_intr)

        if view_intr:
            for view in view_intr:
                request_method = view.get('request_methods')

                if request_method is not None:
                    view_callable = view['callable']
                    view_module = _get_view_module(view_callable)

                    if view_module not in view_request_methods:
                        view_request_methods[view_module] = []

                    if request_method is not None:
                        view_request_methods[view_module].append(
                            request_method
                        )
                else:
                    if view_module not in view_request_methods:
                        view_request_methods[view_module] = []

        else:
            view_request_methods[view_module] = []

    final_routes = []

    for view_module, methods in view_request_methods.items():
        request_methods = _get_request_methods(
            route_request_methods,
            methods
        )

        final_routes.append((
            route.name,
            pattern,
            view_module,
            request_methods,
        ))

    return final_routes


@click.command()
@click.pass_context
def routes_cli(ctx):
    registry = ctx.obj['env']['registry']
    mapper = _get_mapper(registry)

    max_name = len('Name')
    max_pattern = len('Pattern')
    max_view = len('View')
    max_method = len('Method')

    routes = mapper.get_routes()

    mapped_routes = [
        ('Name', 'Pattern', 'View', 'Method'),
        ('----', '-------', '----', '------')
    ]

    for route in routes:
        route_data = get_route_data(route, registry)

        for name, pattern, view, method in route_data:
            if len(name) > max_name:
                max_name = len(name)

            if len(pattern) > max_pattern:
                max_pattern = len(pattern)

            if len(view) > max_view:
                max_view = len(view)

            if len(method) > max_method:
                max_method = len(method)

            mapped_routes.append((name, pattern, view, method))

    fmt = _get_print_format(max_name, max_pattern, max_view, max_method)

    for route in mapped_routes:
        click.echo(fmt % route)