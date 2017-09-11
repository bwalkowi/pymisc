from inspect import signature, Parameter
from functools import wraps, update_wrapper


FUN_TEMPLATE = '''
def {name}{sig}:
    __wrapper__(__wrapped__, {args})
'''


def sanitize_arg(name, kind):
    if kind == Parameter.VAR_POSITIONAL:
        return f'*{name}'
    elif kind == Parameter.KEYWORD_ONLY:
        return f'{name}={name}'
    elif kind == Parameter.VAR_KEYWORD:
        return f'**{name}'
    else:
        return name


def decorator(wrapper):

    @wraps(wrapper)
    def _wrapper(wrapped):
        sig = signature(wrapped)
        args = (sanitize_arg(name, arg)
                for name, arg
                in sig.parameters.items())

        fun_src = FUN_TEMPLATE.format(name=wrapped.__name__,
                                      sig=str(sig),
                                      args=', '.join(args))
        fun_co = compile(fun_src, filename='fun', mode='exec')

        glob = {'__wrapper__': wrapper, '__wrapped__': wrapped}
        loc = {}
        exec(fun_co, glob, loc)
        return update_wrapper(loc[wrapped.__name__], wrapped)

    return _wrapper


@decorator
def print_args(f, *args, **kwargs):
    print('Args: ', args, '\nKwargs: ', kwargs)
    f(*args, **kwargs)


@print_args
def fun(a: int, b: float, c:str=1, *args, d:list, e='heh', **kwargs) -> dict:
    """doc"""
    return {}
