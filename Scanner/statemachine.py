# -*- coding: UTF-8 -*-

from string import upper


class StateMachine(object):
    """
    Defines a generic FSM.
    """
    handlers = {}
    initial_state = None
    end_states = []

    def __init__(self, initial_state=None):
        """
        Construction
        :param initial_state:
        """
        self.set_start_state(initial_state)
        return

    def add_state(self, name, handler, is_end_state=False):
        """
        Adds states by name and handler,
        :param name:
        :param handler:
        :param is_end_state:
        :return:
        """
        name = upper(name)
        self.handlers[name] = handler
        if is_end_state == True:
            self.end_states.append(name)

        return

    def set_start_state(self, name):
        """
        Sets the initial state.
        :param name:
        :return:
        """
        self.initial_state = upper(name)
        return

    def run(self, payload):
        """
        Run the state machine.
        :param payload:
        :return:
        """
        try:
            handler = self.handlers[self.initial_state]
        except:
            raise Exception("InitializationError"), "must call .set_start() before .run()"

        if not self.end_states:
            raise Exception("InitializationError"), "at least one state must be an end_state"

        while True:
            (new_state, payload) = handler(payload)
            if upper(new_state) in self.end_states:
                break
            else:
                handler = self.handlers[upper(new_state)]

        return
