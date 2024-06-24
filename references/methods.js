var Methods = function() {};

const config = require('./config.json');

// Rounds the metal value to the nearest scrap.
Methods.prototype.getRight = function(v) {
    var i = Math.floor(v),
        f = Math.round((v - i) / 0.11);
    return parseFloat((i + (f === 9 || f * 0.11)).toFixed(2));
};

// This method first takes the amount of keys the item costs and multiplies it by
// the current key metal sell price. This gives us the amount of metal the key cost
// is worth in terms of a keys current sell price. Then it adds this result onto
// the metal cost. It's then rounded down to the nearest 0.11.

// From here, the metal (being both the worth of the keys and the metal value), is
// divided into the sell price of a key. Totalling the amount of keys that could be
// afforded with the pure metal value. The metal component is calculated by taking the
// remainder of the rounded total value divided by keyPrice. This gives the amount of
// metal that couldn't be converted into a whole key.

// This method ensures we make prices that take into account the current price of the key.
Methods.prototype.parsePrice = function(original, keyPrice) {
    var metal = this.getRight(original.keys * keyPrice) + original.metal;
    return {
        keys: Math.trunc(metal / keyPrice),
        metal: this.getRight(metal % keyPrice)
    };
};

Methods.prototype.toMetal = function(obj, keyPriceInMetal) {
    var metal = 0;
    metal += (obj.keys ? obj.keys : 0) * keyPriceInMetal;
    metal += obj.metal;
    return this.getRight(metal);
};

Methods.prototype.calculatePercentageDifference = function(value1, value2) {
    if (value1 === 0) {
        return value2 === 0 ? 0 : 100; // Handle division by zero
    }
    return ((value2 - value1) / Math.abs(value1)) * 100;
};

// Calculate percentage differences and decide on rejecting or accepting the autopricers price
// based on limits defined in config.json.
Methods.prototype.calculatePricingAPIDifferences = function(pricetfItem, final_buyObj, final_sellObj, keyobj) {
    var percentageDifferences = {};

    var sell_Price_In_Metal = this.toMetal(final_sellObj, keyobj.metal);
    var buy_Price_In_Metal = this.toMetal(final_buyObj, keyobj.metal);

    var priceTFSell = {};
    priceTFSell.keys = pricetfItem.sell.keys;
    priceTFSell.metal = pricetfItem.sell.metal;

    var priceTFBuy = {};
    priceTFBuy.keys = pricetfItem.buy.keys;
    priceTFBuy.metal = pricetfItem.buy.metal;

    var priceTF_Sell_Price_In_Metal = this.toMetal(priceTFSell, keyobj.metal);
    var priceTF_Buy_Price_In_Metal = this.toMetal(priceTFBuy, keyobj.metal);

    var results = {};
    results.priceTFSellPrice = priceTF_Sell_Price_In_Metal;
    results.autopricerSellPrice = sell_Price_In_Metal;
    results.priceTFBuyPrice = priceTF_Buy_Price_In_Metal;
    results.autopricerBuyPrice = buy_Price_In_Metal;

    percentageDifferences.buyDifference = this.calculatePercentageDifference(
        results.priceTFBuyPrice,
        results.autopricerBuyPrice
    );
    percentageDifferences.sellDifference = this.calculatePercentageDifference(
        results.priceTFSellPrice,
        results.autopricerSellPrice
    );

    // Ensures that data we're going to use in comparison are numbers. If not we throw an error.
    if (isNaN(percentageDifferences.buyDifference) || isNaN(percentageDifferences.sellDifference)) {
        // Can't compare percentages because the external API likely returned malformed data.
        throw new Error('External API returned NaN. Critical error.');
    }
    // Calls another method that uses this percentage difference object to make decision on whether to use our autopricers price or not.
    try {
        var usePrice = this.validatePrice(percentageDifferences);
        // We should use this price, resolves as true.
        return usePrice;
    } catch (e) {
        // We should not use this price.
        throw new Error(e);
    }
};

Methods.prototype.validatePrice = function(percentageDifferences) {
    // If the percentage difference in how much our pricer has determined we should buy an item
    // for compared to prices.tf is greater than the limit set in the config, we reject the price.

    // And if the percentage difference in how much our pricer has determined we should sell an item
    // for compared to prices.tf is less than the limit set in the config, we reject the price.

    // A greater percentage difference for buying, means that our pricer is buying for more than prices.tf.
    // A lesser percentage difference for selling, means that our pricer is selling for less than prices.tf.
    if (percentageDifferences.buyDifference > config.maxPercentageDifferences.buy) {
        throw new Error('Autopricer is buying for too much.');
    } else if (percentageDifferences.sellDifference < config.maxPercentageDifferences.sell) {
        throw new Error('Autopricer is selling for too cheap.');
    }
    return true;
};

Methods.prototype.validateObject = function(obj) {
    // Check if the object is undefined, empty etc.
    if(!obj) {
        return false;
    }
    if(Object.keys(obj).length > 0) {
        if(obj.hasOwnProperty('keys') || obj.hasOwnProperty('metal')) {
            // The object is valid as it contains at least one expected key.
            return true;
        } else {
            // The object is invalid as it doesn't contain any expected keys.
            return false;
        }
    } else {
        // The object is empty.
        return false;
    }
};

Methods.prototype.createCurrencyObject = function(obj) {
    let newObj = {
        keys: 0,
        metal: 0
    };

    if (obj.hasOwnProperty('keys')) {
        newObj.keys = obj.keys;
    }

    if (obj.hasOwnProperty('metal')) {
        newObj.metal = obj.metal;
    }

    return newObj;
};