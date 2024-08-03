import threading

def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

def set_interval_and_wait(func, sec):
    is_running = False

    def func_wrapper():
        nonlocal is_running
        if not is_running:
            is_running = True
            func()
            is_running = False
            set_interval_and_wait(func, sec)

    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

def compare_prices(item_1, item_2):
    return item_1["keys"] == item_2["keys"] and item_1["metal"] == item_2["metal"]

# Thanks ChatGPT
class PricerException(Exception):
    def __init__(self, data):
        super().__init__(data["reason"])  # Initialize the base class with the message
        self.data = data  # Store the dictionary in the instance

    def get_data(self):
        return self.data  # Provide a method to access the dictionary