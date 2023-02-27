from time import time
import json
import asyncio
import logging

from pyinjective.proto.injective.types.v1beta1 import tx_response_pb2 as tx_response_pb
from pyinjective.proto.google.protobuf import any_pb2, timestamp_pb2
from pyinjective.proto.cosmos.base.v1beta1 import coin_pb2 as cosmos_base_coin_pb

from pyinjective.composer import Composer as ProtoMsgComposer

from pyinjective.async_client import AsyncClient
from pyinjective.transaction import Transaction
from pyinjective.constant import Network
from pyinjective.wallet import PrivateKey

from pyinjective.constant import Denom
from pyinjective.utils import *
from typing import List

from pyinjective.proto.injective.exchange.v1beta1 import tx_pb2 as injective_exchange_tx_pb

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)

class Composer:

    def __init__(self, network: str):
        self.network = network

    def Coin(self, amount: int, denom: str):
        return cosmos_base_coin_pb.Coin(amount=str(amount), denom=denom)
    
    def MsgSpotMarketLaunchProposal(
        self,
        title: str,
        description: str,
        ticker: str,
        base_denom: str,
        quote_denom: str,
        min_price_tick_size: float,
        min_quantity_tick_size: float,
        maker_fee_rate: float,
        taker_fee_rate: float,
        quote_decimals: int,
    ):

        scaled_maker_fee_rate = Decimal((maker_fee_rate * pow(10, 18)))
        maker_fee_to_bytes = bytes(str(scaled_maker_fee_rate), "utf-8")

        scaled_taker_fee_rate = Decimal((taker_fee_rate * pow(10, 18)))
        taker_fee_to_bytes = bytes(str(scaled_taker_fee_rate), "utf-8")

        scaled_min_price_tick_size = Decimal(
            (min_price_tick_size * pow(10, quote_decimals + 18))
        )
        min_price_to_bytes = bytes(str(scaled_min_price_tick_size), "utf-8")

        scaled_min_quantity_tick_size = Decimal((min_quantity_tick_size * pow(10, 18)))
        min_quantity_to_bytes = bytes(str(scaled_min_quantity_tick_size), "utf-8")

        return injective_exchange_tx_pb.SpotMarketLaunchProposal(
            title=title,
            description=description,
            ticker=ticker,
            maker_fee_rate=maker_fee_to_bytes,
            taker_fee_rate=taker_fee_to_bytes,
            base_denom=base_denom,
            quote_denom=quote_denom,
            min_price_tick_size=min_price_to_bytes,
            min_quantity_tick_size=min_quantity_to_bytes,
        )
    
    @staticmethod
    def MsgResponses(data, simulation=False):
        if not simulation:
            data = bytes.fromhex(data)
        header_map = {

            "/injective.exchange.v1beta1.MsgSpotMarketLaunchProposal": injective_exchange_tx_pb.SpotMarketLaunchProposal,
        }

        response = tx_response_pb.TxResponseData.FromString(data)
        msgs = []
        for msg in response.messages:
            msgs.append(header_map[msg.header].FromString(msg.data))

        return msgs

    @staticmethod
    def UnpackMsgExecResponse(msg_type, data):
        header_map = {
            "SpotMarketLaunchProposal": injective_exchange_tx_pb.SpotMarketLaunchProposal
        }

        return header_map[msg_type].FromString(bytes(data, "utf-8"))


async def main() -> None:
    # select network: local, testnet, mainnet
    network = Network.testnet()
    composer = Composer(network=network.string())

    # initialize grpc client
    client = AsyncClient(network, insecure=False)
    await client.sync_timeout_height()

    # load account
    priv_key = PrivateKey.from_hex("0b0956a7c69e926931caf53eddf4f1cb84e1e3165d6f1d861e9bef91ce3cf568")
    pub_key = priv_key.to_public_key()
    address = pub_key.to_address()
    account = await client.get_account(address.to_acc_bech32())

    # prepare tx msg
    msg = composer.MsgSpotMarketLaunchProposal(
        title="Wavely Listing Proposal to List PUG/USDT Spot Pair",
        description="PUG (Puggo) is a token created by Wavely to be launched for the first time on Injective. This proposal will launch the PUG/USDT Spot Market with maker and taker fees at 0.01% and 0.1% respectively. For more info: https://www.wavely.app/puggo/",
        ticker="PUG/USDT",
        base_denom="peggy0xf9a06dE3F6639E6ee4F079095D5093644Ad85E8b",
        quote_denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
        quote_decimals=6,
        maker_fee_rate=0.0001, # 0.01%
        taker_fee_rate=0.0010, # 0.10%
        min_price_tick_size=1.000000000000000000,
        min_quantity_tick_size=1.000000000000000000
    )

    # build sim tx
    tx = (
        Transaction()
        .with_messages(msg)
        .with_sequence(client.get_sequence())
        .with_account_num(client.get_number())
        .with_chain_id(network.chain_id)
    )
    sim_sign_doc = tx.get_sign_doc(pub_key)
    sim_sig = priv_key.sign(sim_sign_doc.SerializeToString())
    sim_tx_raw_bytes = tx.get_tx_data(sim_sig, pub_key)

    # simulate tx
    (sim_res, success) = await client.simulate_tx(sim_tx_raw_bytes)
    if not success:
        print(sim_res)
        return

    sim_res_msg = composer.MsgResponses(sim_res.result.data, simulation=True)
    print("---Simulation Response---")
    print(sim_res_msg)

    # build tx
    gas_price = 500000000
    gas_limit = sim_res.gas_info.gas_used + 20000  # add 20k for gas, fee computation
    gas_fee = '{:.18f}'.format((gas_price * gas_limit) / pow(10, 18)).rstrip('0')
    fee = [composer.Coin(
        amount=gas_price * gas_limit,
        denom=network.fee_denom,
    )]
    tx = tx.with_gas(gas_limit).with_fee(fee).with_memo('').with_timeout_height(client.timeout_height)
    sign_doc = tx.get_sign_doc(pub_key)
    sig = priv_key.sign(sign_doc.SerializeToString())
    tx_raw_bytes = tx.get_tx_data(sig, pub_key)

    # broadcast tx: send_tx_async_mode, send_tx_sync_mode, send_tx_block_mode
    res = await client.send_tx_sync_mode(tx_raw_bytes)
    print("---Transaction Response---")
    print(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.get_event_loop().run_until_complete(main())
