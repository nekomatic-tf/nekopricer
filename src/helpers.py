import threading

def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

def compare_prices(item_1, item_2):
    return item_1["keys"] == item_2["keys"] and item_1["metal"] == item_2["metal"]