"""Only the CPU kernel is shipped. Detection does not imply implementation."""
def available_backends():
    return {'cpu': {'implemented': True, 'dtype': ['float64', 'float32_qr']}}

def select_backend(name='cpu'):
    if name != 'cpu':
        raise NotImplementedError(f'{name}: no validated V807 kernel is shipped')
    return 'cpu'
