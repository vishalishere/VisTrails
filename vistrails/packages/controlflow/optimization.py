import copy
from itertools import izip

from vistrails.core.modules.vistrails_module import Module, InvalidOutput, \
    ModuleSuspended, ModuleError, ModuleConnector

from fold import create_constant


class Optimize(Module):
    """
    The Optimize Module runs a module over and over until the condition port
    is true. Then, it returns the result.
    """

    def __init__(self):
        Module.__init__(self)
        self.is_looping_module = True

    def updateUpstream(self):
        """A modified version of the updateUpstream method."""

        # everything is the same except that we don't update anything
        # upstream of FunctionPort
        for port_name, connector_list in self.inputPorts.iteritems():
            if port_name == 'FunctionPort':
                for connector in connector_list:
                    connector.obj.updateUpstream()
            else:
                for connector in connector_list:
                    connector.obj.update()
        for port_name, connectorList in copy.copy(self.inputPorts.items()):
            if port_name != 'FunctionPort':
                for connector in connectorList:
                    if connector.obj.get_output(connector.port) is \
                            InvalidOutput:
                        self.removeInputConnector(port_name, connector)

    def compute(self):
        name_output = self.getInputFromPort('OutputPort')
        name_condition = self.getInputFromPort('ConditionPort')
        name_state_input = self.forceGetInputFromPort('StateInputPorts')
        name_state_output = self.forceGetInputFromPort('StateOutputPorts')
        max_iterations = self.getInputFromPort('MaxIterations')

        if name_state_input or name_state_output:
            if not name_state_input or not name_state_output:
                raise ModuleError(self,
                                  "Passing state between iterations requires "
                                  "BOTH StateInputPorts and StateOutputPorts "
                                  "to be set")
            if len(name_state_input) != len(name_state_output):
                raise ModuleError(self,
                                  "StateInputPorts and StateOutputPorts need "
                                  "to have the same number of ports "
                                  "(got %d and %d)" % (len(name_state_input),
                                                       len(name_state_output)))

        connectors = self.inputPorts.get('FunctionPort')
        if len(connectors) != 1:
            raise ModuleError(self,
                              "Multiple modules connected on FunctionPort")
        module = connectors[0].obj

        state = None

        for i in xrange(max_iterations):
            if not self.upToDate:
                module.upToDate = False
                module.already_computed = False

                # For logging
                module.is_looping = True
                module.first_iteration = i == 0
                module.last_iteration = False
                module.loop_iteration = i

                # Set state on input ports
                if i > 0 and name_state_input:
                    for value, port in izip(state, name_state_input):
                        if port in module.inputPorts:
                            del module.inputPorts[port]
                        new_connector = ModuleConnector(
                                create_constant(value),
                                'value')
                        module.set_input_port(port, new_connector)

            module.update()
            if hasattr(module, 'suspended') and module.suspended:
                raise ModuleSuspended(module._module_suspended)

            if name_condition not in module.outputPorts:
                raise ModuleError(module,
                                  "Invalid output port: %s" % name_condition)
            if module.get_output(name_condition):
                break

            # Get state on output ports
            if name_state_output:
                state = [module.get_output(port) for port in name_state_output]

        if name_output not in module.outputPorts:
            raise ModuleError(module,
                              "Invalid output port: %s" % name_output)
        result = copy.copy(module.get_output(name_output))
        self.setResult('Result', result)
