def decorate(function):
    def wrapper():
        function()
    return wrapper


@decorate
def say_hello():
    print("Hello")

decorated = decorate(say_hello)
decorated()