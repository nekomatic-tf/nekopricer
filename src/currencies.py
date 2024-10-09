import math
class Currencies:
    # Creates a new Currencies instance
    def __init__(self, currencies: dict):
        if currencies == None:
            raise Exception("Missing currencies object")
        
        self.keys = float(currencies.get("keys") or 0)
        self.metal = float(currencies.get("metal") or 0)

        if math.isnan(self.keys) or math.isnan(self.metal):
            raise Exception("Not a valid currencies object")
        
        self.metal = Currencies.toRefined(Currencies.toScrap(self.metal))
    # Get the value of the currencies in scrap
    def toValue(self, conversion: float) -> float:
        if conversion == None and not self.keys == 0:
            # The conversion rate is needed because there are keys
            raise Exception("Missing conversion rate for keys in refined")
        
        value = Currencies.toScrap(self.metal)
        if not self.keys == 0:
            value += self.keys * Currencies.toScrap(conversion)
        
        return value
    # Creates a string that represents this currencies object
    def toString(self) -> str:
        string = ""

        if not self.keys == 0 or self.keys == self.metal:
            # If there are keys, then we will add that to the string
            string = f"{self.keys} key{"s" if self.keys > 1 else ""}"
        
        if not self.metal == 0 or self.keys == self.metal:
            if not string == "":
                # The string is not empty, that means that we have added the keys
                string += ", "
            
            # Add the metal to the string
            string += f"{math.trunc(self.metal * 100) / 100} ref"
            
        return string
    # Creates an object that represents this currencies object
    def toJSON(self) -> dict:
        json = {
            "keys": self.keys,
            "metal": self.metal
        }

        return json
    # Adds refined together
    @staticmethod
    def addRefined(*args: float) -> float:
        value = 0

        for refined in args:
            value += Currencies.toScrap(refined)
        
        metal = Currencies.toRefined(value)
        return metal
    # Rounds a number to the closest step
    @staticmethod
    def round(number: float) -> float:
        step = 0.5
        inv = 1.0 / step

        rounded = round(number * inv) / inv
        return rounded
    # Rounds a number up or down if the value is less than 0 or not
    @staticmethod
    def rounding(number: float) -> float:
        isPositive = number >= 0

        # If we add 0.001 and it is greater than the number rounded up, then we need to round up to fix floating point error
        rounding = round if (number + 0.001 > math.ceil(number)) else math.floor
        rounded = rounding(abs(number))
    
        return rounded if isPositive else -rounded
    # Converts scrap into a currencies object
    @staticmethod
    def toCurrencies(value: float, conversion: float) -> dict:
        if conversion == None:
            # If the conversion rate is missing, convert the value into refined
            metal = Currencies.toRefined(value)

            currencies = {
                "keys": 0,
                "metal": metal
            }
            return currencies
        
        # Convert conversion rate into scrap
        conversion = Currencies.toScrap(conversion)
        # Get the highest amount of keys from the given value
        keys = Currencies.rounding(value / conversion)
        # Find the value that is remaining
        left = value - keys * conversion
        # Convert the missing value to refined
        metal = Currencies.toRefined(left)

        # Create a new instance of Currencies
        currencies = {
            "keys": keys,
            "metal": metal
        }
        return currencies
    # Coverts scrap to refined
    @staticmethod
    def toRefined(scrap: float) -> float:
        # The converstion rate between scrap and refined is 9 scrap/ref
        refined = scrap / 9
        # Truncate it to remove repeating decimals  (10 scrap / 9 scrap/refined = 1.1111...)
        refined = math.trunc(refined * 100) / 100
        return refined
    # Coverts refined to scrap
    @staticmethod
    def toScrap(refined: float) -> float:
        # Get the estimated amount of scrap
        scrap = refined * 9
        # Round it to the nearest half
        scrap = round(scrap * 2) / 2
        return scrap
    # Truncate a number
    @staticmethod
    def truncate(number: float) -> float:
        decimals = 2
        # Get the factor to truncate by
        factor = math.pow(10, decimals)
        # Always round the number by aiming at 0
        truncated = Currencies.rounding(number * factor) / factor
        return truncated