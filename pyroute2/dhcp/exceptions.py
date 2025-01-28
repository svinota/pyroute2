from pyroute2.dhcp.enums.dhcp import Option


class DHCPError(Exception):
    '''
    Base dhcp error
    '''

    pass


class DHCPOptionMissingError(DHCPError):
    '''
    Missing dhcp option
    '''

    def __init__(self, option):
        if isinstance(option, int):
            option = Option(option)
        if isinstance(option, str):
            option = Option[option.upper()]
        msg = f'Missing DHCP option #{option.value}: {option.name.lower()}'
        super(DHCPError, self).__init__(msg)
