#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py --test prod-like; sleep 1; done

import argparse
from collections import deque
from enum import Enum
from pickle import GLOBAL
import time
import socket
import json
from datetime import datetime

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "FLATWHITE"

# ~~~~~============== MAIN LOOP ==============~~~~~

# You should put your code here! We provide some starter code as an example,
# but feel free to change/remove/edit/update any of it as you'd like. If you
# have any questions about the starter code, or what to do next, please ask us!
#
# To help you get started, the sample code below tries to buy BOND for a low
# price, and it prints the current prices for VALE every second. The sample
# code is intended to be a working example, but it needs some improvement
# before it will start making good trades!


def main():
    args = parse_arguments()

    BOND_FAIR_VAL = 1000
    VALUE_ESTIMATES = {"BOND": 0, "VALBZ": 0, "VALE": 0, "GS": 0, "MS": 0, "WFC": 0, "XLF": 0}
    BUY_ESTIMATES = {"BOND": 0, "VALBZ": 0, "VALE": 0, "GS": 0, "MS": 0, "WFC": 0, "XLF": 0}
    SELL_ESTIMATES = {"BOND": 0, "VALBZ": 0, "VALE": 0, "GS": 0, "MS": 0, "WFC": 0, "XLF": 0}
    SIZE_ESTIMATES={"BOND_BUY": 0, "BOND_SELL": 0, "VALE_BUY": 0, "VALE_SELL": 0, "VALBZ_BUY": 0, "VALBZ_SELL": 0, "GS_BUY": 0, "GS_SELL": 0, "MS_BUY": 0, "MS_SELL": 0, "WFC_BUY": 0, "WFC_SELL": 0, "XLF_BUY": 0, "XLF_SELL": 0}
    PORTFOLIO = {"BOND": 0, "VALBZ": 0, "VALE": 0, "GS": 0, "MS": 0, "WFC": 0, "XLF": 0}
    LIMITS = {"BOND": 100, "VALBZ": 10, "VALE": 10, "GS": 100, "MS": 100, "WFC": 100, "XLF": 100}
    GLOBAL_ID = 5
    XLF_CONV_FEE = 100

    XLF_LAST_CONVERT = datetime.now()

    def update_portfolio(message):
        if message["dir"] == Dir.BUY:
            PORTFOLIO[message["symbol"]] += message["size"]
        elif message["dir"] == Dir.SELL:
            PORTFOLIO[message["symbol"]] -= message["size"]

    def estimate_value(message):
        if message["buy"]:
            best_buy_price = message["buy"][0][0]
            best_buy_size = message["buy"][0][1]
        if message["sell"]:
            best_sell_price = message["sell"][0][0]
            best_sell_size = message["sell"][0][1]
        
        if message["buy"] and message["sell"]:
            temp = (best_buy_price * best_buy_size + best_sell_price * best_sell_size) / (best_buy_size + best_sell_size)
            est_value = best_buy_price + (best_sell_price - temp)
            #est_value = best_buy_price + best_sell_price / 2
            # TODO (update this function as we develop better ways of estimating stock value)
            return est_value
        return None  # if no data

    def bond_strat_pennying(exchange, best_buy, best_sell, id):
        if (best_buy + 1 <= BOND_FAIR_VAL) and (100-PORTFOLIO["BOND"] > 0):
            exchange.send_add_message(order_id=id, symbol="BOND", dir=Dir.BUY, price=best_buy + 1, size=LIMITS["BOND"]-PORTFOLIO["BOND"]-1)
            
        if best_sell - 1 > BOND_FAIR_VAL:
            exchange.send_add_message(order_id=id, symbol="BOND", dir=Dir.SELL, price=best_sell - 1, size=PORTFOLIO["BOND"])


    def conversion_strat(exchange, vale_buy, vale_sell, valbz_buy, valbz_sell, vale_buy_size, vale_sell_size, valbz_buy_size, valbz_sell_size, id):
        if valbz_sell and vale_buy:
            spread = valbz_sell - vale_buy
            if spread >= 2:
                min_size = 10 // spread + 1
                if vale_buy_size and valbz_sell_size:
                    if (min_size <= vale_buy_size and min_size <= valbz_sell_size):
                        order_size = min(vale_buy_size, valbz_sell_size)
                        exchange.send_add_message(order_id=id, symbol="VALE", dir=Dir.BUY, price=vale_buy, size=order_size)
                        exchange.send_convert_message(order_id=id+1, symbol="VALE", dir=Dir.SELL, size=order_size)
                        exchange.send_add_message(order_id=id+2, symbol="VALBZ", dir=Dir.SELL, price=valbz_sell, size=order_size)
                    return
        if vale_sell and valbz_buy:
            other_spread = vale_sell - valbz_buy
            if other_spread >= 2:
                min_size = 10 // other_spread + 1
                if vale_sell_size and valbz_buy_size:
                    if (min_size <= vale_sell_size and min_size <= valbz_buy_size):
                        order_size = min(vale_sell_size, valbz_buy_size)
                        exchange.send_add_message(order_id=id, symbol="VALBZ", dir=Dir.BUY, price=valbz_buy, size=min_size)
                        exchange.send_convert_message(order_id=id+1, symbol="VALBZ", dir=Dir.SELL, size=min_size)
                        exchange.send_add_message(order_id=id+2, symbol="VALE", dir=Dir.SELL, price=vale_sell, size=min_size)
                    

    def stock_pennying(exchange, symbol, fair, buy_price, sell_price, id):
        if buy_price + 1 < fair:
            capacity = min(LIMITS[symbol] - PORTFOLIO[symbol],SIZE_ESTIMATES[f"{symbol}_BUY"])
            order_size = capacity
            exchange.send_add_message(order_id=id, symbol=symbol, dir=Dir.BUY, price=buy_price + 1, size=order_size)
        elif sell_price - 1 > fair:
            capacity = min(PORTFOLIO[symbol] + LIMITS[symbol], SIZE_ESTIMATES[f"{symbol}_SELL"])
            order_size = capacity
            exchange.send_add_message(order_id=id, symbol=symbol, dir=Dir.SELL, price=sell_price - 1, size=order_size)


    def xlf_conv_strat(exchange,
                        bond_buy, bond_sell,
                        gs_buy, gs_sell,
                        ms_buy, ms_sell,
                        wfc_buy, wfc_sell,
                        xlf_buy, xlf_sell, id):
        
        if bond_buy and gs_buy and ms_buy and wfc_buy:
            xlf_fair = (3 * bond_buy + 2*gs_buy + 3*ms_buy + 2*wfc_buy) / 10
        else:
            return False

        if xlf_sell and xlf_fair:
            spread = xlf_sell - xlf_fair
            if spread * 10 > XLF_CONV_FEE + 50:
                exchange.send_add_message(order_id=id, symbol="BOND", dir=Dir.BUY, price=bond_buy, size=3)
                exchange.send_add_message(order_id=id+1, symbol="GS", dir=Dir.BUY, price=gs_buy, size=2)
                exchange.send_add_message(order_id=id+2, symbol="MS", dir=Dir.BUY, price=ms_buy, size=3)
                exchange.send_add_message(order_id=id+3, symbol="WFC", dir=Dir.BUY, price=wfc_buy, size=2)

                exchange.send_convert_message(order_id=id+4, symbol="XLF", dir=Dir.BUY, size=10)

                exchange.send_add_message(order_id=id+5, symbol="XLF", dir=Dir.SELL, price=xlf_sell, size=10)
                return True

        if bond_sell and gs_sell and ms_sell and wfc_sell:
            xlf_fair = (3 * bond_sell + 2*gs_sell + 3*ms_sell + 2*wfc_sell) / 10
        else:
            return False

        if xlf_fair and xlf_buy:
            other_spread = xlf_fair - xlf_buy
            if other_spread * 10 > XLF_CONV_FEE + 50:
                exchange.send_add_message(order_id=id, symbol="XLF", dir=Dir.BUY, price=xlf_buy, size=10)

                exchange.send_convert_message(order_id=id+1, symbol="XLF", dir=Dir.SELL, size=10)

                exchange.send_add_message(order_id=id+2, symbol="BOND", dir=Dir.SELL, price=bond_sell, size=3)
                exchange.send_add_message(order_id=id+3, symbol="GS", dir=Dir.SELL, price=gs_sell, size=2)
                exchange.send_add_message(order_id=id+4, symbol="MS", dir=Dir.SELL, price=ms_sell, size=3)
                exchange.send_add_message(order_id=id+5, symbol="WFC", dir=Dir.SELL, price=wfc_sell, size=2)
                return True
        
        return False


    exchange = ExchangeConnection(args=args)

    # Store and print the "hello" message received from the exchange. This
    # contains useful information about your positions. Normally you start with
    # all positions at zero, but if you reconnect during a round, you might
    # have already bought/sold symbols and have non-zero positions.
    hello_message = exchange.read_message()
    print("First message from exchange:", hello_message)

    # Send an order for BOND at a good price, but it is low enough that it is
    # unlikely it will be traded against. Maybe there is a better price to
    # pick? Also, you will need to send more orders over time.
    exchange.send_add_message(order_id=1, symbol="BOND", dir=Dir.BUY, price=990, size=1)

    # Set up some variables to track the bid and ask price of a symbol. Right
    # now this doesn't track much information, but it's enough to get a sense
    # of the VALE market.
    #vale_bid_price, vale_ask_price = None, None
    vale_last_print_time = time.time()

    # Here is the main loop of the program. It will continue to read and
    # process messages in a loop until a "close" message is received. You
    # should write to code handle more types of messages (and not just print
    # the message). Feel free to modify any of the starter code below.
    #
    # Note: a common mistake people make is to call write_message() at least
    # once for every read_message() response.
    #
    # Every message sent to the exchange generates at least one response
    # message. Sending a message in response to every exchange message will
    # cause a feedback loop where your bot's messages will quickly be
    # rate-limited and ignored. Please, don't do that!

    while True:
        message = exchange.read_message()

        # Some of the message types below happen infrequently and contain
        # important information to help you understand what your bot is doing,
        # so they are printed in full. We recommend not always printing every
        # message because it can be a lot of information to read. Instead, let
        # your code handle the messages and just print the information
        # important for you!
        if message["type"] == "close":
            print("The round has ended")
            break
        elif message["type"] == "error":
            print(message)
        elif message["type"] == "reject":
            print(message)
        elif message["type"] == "fill":
            print(message)
            update_portfolio(message)
        elif message["type"] == "book":
            # START MESSAGE HELPERS
            def best_price(side):
                if message[side]:
                    return message[side][0][0]
            def best_size(side):
                if message[side]:
                    return message[side][0][1]
            def update_estimates(sym):
                BUY_ESTIMATES[sym] = best_price("buy")
                SELL_ESTIMATES[sym] = best_price("sell")
                SIZE_ESTIMATES[sym+"_BUY"] = best_size("buy")
                SIZE_ESTIMATES[sym+"_SELL"] = best_size("sell")
            # END MESSAGE HELPERS

            temp_est =  estimate_value(message)
            if temp_est:
                #VALUE_ESTIMATES[message["symbol"]] = (VALUE_ESTIMATES[message["symbol"]] + temp_est / 2)
                VALUE_ESTIMATES[message["symbol"]] = temp_est
        
            """
            if message["symbol"] == "VALE":
                update_estimates("VALE")

                now = time.time()

                if now > vale_last_print_time + 1:
                    vale_last_print_time = now
                    print(
                        {
                            "vale_bid_price": BUY_ESTIMATES["VALE"],
                            "vale_ask_price": SELL_ESTIMATES["VALE"]
                        }
                    )
                    conversion_strat(exchange,  BUY_ESTIMATES["VALE"], SELL_ESTIMATES["VALE"], BUY_ESTIMATES["VALBZ"], SELL_ESTIMATES["VALBZ"], SIZE_ESTIMATES["VALE_BUY"], SIZE_ESTIMATES["VALE_SELL"], SIZE_ESTIMATES["VALBZ_BUY"], SIZE_ESTIMATES["VALBZ_SELL"], GLOBAL_ID)
                    GLOBAL_ID += 3

            elif message["symbol"] == "VALBZ":
                update_estimates("VALBZ")

                now = time.time()

                if now > vale_last_print_time + 1:
                    vale_last_print_time = now
                    print(
                        {
                            "valbz_bid_price": BUY_ESTIMATES["VALBZ"],
                            "valbz_ask_price": SELL_ESTIMATES["VALBZ"]
                        }
                    )
                    conversion_strat(exchange,  BUY_ESTIMATES["VALE"], SELL_ESTIMATES["VALE"], BUY_ESTIMATES["VALBZ"], SELL_ESTIMATES["VALBZ"], SIZE_ESTIMATES["VALBZ_BUY"], SIZE_ESTIMATES["VALE_SELL"], SIZE_ESTIMATES["VALBZ_BUY"], SIZE_ESTIMATES["VALBZ_SELL"], GLOBAL_ID)
                    GLOBAL_ID += 3
            """

            if message["symbol"] == "BOND":
                update_estimates("BOND")

                continue
                if BUY_ESTIMATES["BOND"] and SELL_ESTIMATES["BOND"]:
                    bond_strat_pennying(exchange, BUY_ESTIMATES["BOND"], SELL_ESTIMATES["BOND"], GLOBAL_ID)
                    GLOBAL_ID += 1

            
            if message["symbol"] == "GS":
                update_estimates("GS")
                if (datetime.now() - XLF_LAST_CONVERT).total_seconds() >= 5:
                    XLF_LAST_CONVERT = datetime.now()
                    executed = xlf_conv_strat(exchange, BUY_ESTIMATES["BOND"], SELL_ESTIMATES["BOND"], BUY_ESTIMATES["GS"], SELL_ESTIMATES["GS"], BUY_ESTIMATES["MS"], SELL_ESTIMATES["MS"], BUY_ESTIMATES["WFC"], SELL_ESTIMATES["WFC"], BUY_ESTIMATES["XLF"], SELL_ESTIMATES["XLF"], GLOBAL_ID)
                    GLOBAL_ID += 10

                """
                if not executed:
                    if BUY_ESTIMATES["GS"] and SELL_ESTIMATES["GS"]:
                        stock_pennying(exchange, "GS", VALUE_ESTIMATES["GS"], BUY_ESTIMATES["GS"], SELL_ESTIMATES["GS"], GLOBAL_ID)
                        GLOBAL_ID += 1
                """
    
            elif message["symbol"] == "MS":
                update_estimates("MS")
                if (datetime.now() - XLF_LAST_CONVERT).total_seconds() >= 5:
                    XLF_LAST_CONVERT = datetime.now()
                    executed = xlf_conv_strat(exchange, BUY_ESTIMATES["BOND"], SELL_ESTIMATES["BOND"], BUY_ESTIMATES["GS"], SELL_ESTIMATES["GS"], BUY_ESTIMATES["MS"], SELL_ESTIMATES["MS"], BUY_ESTIMATES["WFC"], SELL_ESTIMATES["WFC"], BUY_ESTIMATES["XLF"], SELL_ESTIMATES["XLF"], GLOBAL_ID)
                    GLOBAL_ID += 10

                """
                if not executed:
                    if BUY_ESTIMATES["MS"] and SELL_ESTIMATES["MS"]:
                        stock_pennying(exchange, "MS", VALUE_ESTIMATES["MS"], BUY_ESTIMATES["MS"], SELL_ESTIMATES["MS"], GLOBAL_ID)
                        GLOBAL_ID += 1
                """

            elif message["symbol"] == "WFC":
                update_estimates("WFC")
                if (datetime.now() - XLF_LAST_CONVERT).total_seconds() >= 5:
                    XLF_LAST_CONVERT = datetime.now()
                    executed = xlf_conv_strat(exchange, BUY_ESTIMATES["BOND"], SELL_ESTIMATES["BOND"], BUY_ESTIMATES["GS"], SELL_ESTIMATES["GS"], BUY_ESTIMATES["MS"], SELL_ESTIMATES["MS"], BUY_ESTIMATES["WFC"], SELL_ESTIMATES["WFC"], BUY_ESTIMATES["XLF"], SELL_ESTIMATES["XLF"], GLOBAL_ID)
                    GLOBAL_ID += 10

                """
                if not executed:
                    if BUY_ESTIMATES["WFC"] and SELL_ESTIMATES["WFC"]:
                        stock_pennying(exchange, "WFC", VALUE_ESTIMATES["WFC"], BUY_ESTIMATES["WFC"], SELL_ESTIMATES["WFC"], GLOBAL_ID)
                        GLOBAL_ID += 1
                """

            elif message["symbol"] == "XLF":
                update_estimates("XLF")
                if (datetime.now() - XLF_LAST_CONVERT).total_seconds() >= 5:
                    XLF_LAST_CONVERT = datetime.now()
                    executed = xlf_conv_strat(exchange, BUY_ESTIMATES["BOND"], SELL_ESTIMATES["BOND"], BUY_ESTIMATES["GS"], SELL_ESTIMATES["GS"], BUY_ESTIMATES["MS"], SELL_ESTIMATES["MS"], BUY_ESTIMATES["WFC"], SELL_ESTIMATES["WFC"], BUY_ESTIMATES["XLF"], SELL_ESTIMATES["XLF"], GLOBAL_ID)
                    GLOBAL_ID += 10

                """"
                if not executed:
                    if BUY_ESTIMATES["XLF"] and SELL_ESTIMATES["XLF"]:
                        stock_pennying(exchange, "XLF", VALUE_ESTIMATES["XLF"], BUY_ESTIMATES["XLF"], SELL_ESTIMATES["XLF"], GLOBAL_ID)
                        GLOBAL_ID += 1
                """
                
                



# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questions about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to


class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        self.exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.exchange_socket.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(
        self, order_id: int, symbol: str, dir: Dir, price: int, size: int
    ):
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s.makefile("rw", 1)

    def _write_message(self, message):
        json.dump(message, self.exchange_socket)
        self.exchange_socket.write("\n")

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 25000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args


if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLACEME"
    ), "Please put your team name in the variable [team_name]."

    main()