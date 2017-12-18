# pylint: disable=C0103

"""
create_routes.py

Dynamically loads the generated protobuf python files and creates flask routes
to handle RPCs advertized by the server.
"""

import os
import sys
import mako.template
import mako.runtime

def CreateRoutes(templateFile):
    """
    Create flask routes for each RPC endpoint for all services.
    """

    # The name of a type in the .proto doesn't exactly match the name of
    # the generated python type.  We'll use this typemap to translate between
    # the two so we can generate correct code in the routes.py file.
    typemap = {}

    # Accumulate a list of all the services we find so we can iterate through
    # them in the template
    services = []

    # Keep a list of all the protobuf python generated files we process so we
    # can mass import them at the top of the routes.py file.
    imports = []

    for root, _, files in os.walk('.'):
        for f in files:
            if f.endswith('_pb2.py'):
                filename = os.path.join(root, f[:-3]) # make sure we pull off the .py at the end
                parts = os.path.normpath(filename).split(os.sep)
                modulename = '.'.join(parts)

                # load the module.  since modulename is some dotted path (e.g. tbmatch.session_pb2)
                # the actual module with the protobuf definition is contained therein.
                imports.append(modulename)
                module = __import__(modulename)
                for part in parts[1:]:
                    module = getattr(module, part)

                # iterate through all the symbols in the module, looking for services and message
                # declarations
                for name in dir(module):
                    obj = getattr(module, name)
                    typename = str(type(obj))
                    if 'GeneratedProtocolMessageType' in typename or 'EnumTypeWrapper' in typename:
                        # This is a protocol message or an enum.  Keep track of it in the typemap
                        # The full_name is something like 'tbrpc.Empty', which is actually defined
                        # in 'tbrpc.tbrpc_pb2.Empty'.
                        typemap[obj.DESCRIPTOR.full_name] = modulename + '.' + name
                        continue

                    if 'ServiceDescriptor' in typename:
                        # This is a service!  Accumulate information on all the rpc entry points
                        # it defines, then add it to the services list
                        methods = []
                        for method in obj.methods:
                            if '--ignore' + method.name not in sys.argv:
                                methods.append({
                                    'name' : method.name,
                                    'input' : method.input_type.full_name,
                                    'output' : method.output_type.full_name,
                                })

                        services.append({
                            'name' : obj.full_name,
                            'methods' : methods,
                        })

    # Create a mako context with all the data the template will need, then render it
    # to routes.py.
    ctx = {
        'imports' : imports,
        'services' : services,
        'typemap' : typemap,
    }
    print mako.template.Template(filename=templateFile).render(**ctx).replace('\r', '')
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print 'syntax: {0} template-file'.format(__file__)
        sys.exit(1)
    CreateRoutes(sys.argv[1])
