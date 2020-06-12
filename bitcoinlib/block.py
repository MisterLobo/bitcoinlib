# -*- coding: utf-8 -*-
#
#    BitcoinLib - Python Cryptocurrency Library
#    BLOCK parsing and construction
#    © 2020 Juni - 1200 Web Development <http://1200wd.com/>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from bitcoinlib.encoding import *
from bitcoinlib.transactions import transaction_deserialize


class Block:

    def __init__(self, blockhash, version, prev_block, merkle_root, timestamp, bits, nonce, transactions=None,
                 block_height=None, network=DEFAULT_NETWORK):
        self.blockhash = blockhash
        self.version = version
        self.version_int = struct.unpack('>L', version)[0]
        self.prev_block = prev_block
        self.merkle_root = merkle_root
        self.timestamp = struct.unpack('>L', timestamp)[0]
        self.bits = bits
        self.bits_int = struct.unpack('>L', bits)[0]
        self.nonce = nonce
        self.nonce_int = struct.unpack('>L', nonce)[0]
        self.transactions = transactions
        self.txs_data = None
        self.block_height = block_height
        self.network = network
        if not block_height and len(self.transactions):
            # first bytes of unlocking script of coinbase transaction contain block height
            self.block_height = struct.unpack('<L', self.transactions[0].inputs[0].unlocking_script[1:4] + b'\x00')[0]

    def __repr__(self):
        return "<Block (%s, %d, transactions: %d" % (to_hexstring(self.blockhash), self.block_height, len(self.transactions))

    @classmethod
    def from_raw(cls, rawblock, blockhash=None, parse_transactions=True, network=DEFAULT_NETWORK):
        blockhash_calc = double_sha256(rawblock[:80])[::-1]
        if not blockhash:
            blockhash = blockhash_calc
        elif blockhash != blockhash_calc:
            raise ValueError("Provided blockhash does not correspond to calculated blockhash %s" % blockhash_calc)

        version = rawblock[0:4][::-1]
        prev_block = rawblock[4:36][::-1]
        merkle_root = rawblock[36:68][::-1]
        timestamp = rawblock[68:72][::-1]
        bits = rawblock[72:76][::-1]
        nonce = rawblock[76:80][::-1]
        tx_count, size = varbyteint_to_int(rawblock[80:89])
        txs_data = rawblock[80+size:]

        # Parse coinbase transaction so we can extract extra information
        transactions = [transaction_deserialize(txs_data, network=network, check_size=False)]
        txs_data = txs_data[transactions[0].size:]

        while parse_transactions and txs_data:
            t = transaction_deserialize(txs_data, network=network, check_size=False)
            transactions.append(t)
            txs_data = txs_data[t.size:]
            # TODO: verify transactions, need input value from previous txs
            # if verify and not t.verify():
            #     raise ValueError("Could not verify transaction %s in block %s" % (t.txid, blockhash))

        block = cls(blockhash, version, prev_block, merkle_root, timestamp, bits, nonce, transactions, network=network)
        block.txs_data = txs_data
        return block

    def parse_transactions(self, limit=0):
        n = 0
        while self.txs_data and (limit == 0 or n < limit):
            t = transaction_deserialize(self.txs_data, network=self.network, check_size=False)
            self.transactions.append(t)
            self.txs_data = self.txs_data[t.size:]
            n += 1

    def as_dict(self):
        return {
            'blockhash': to_hexstring(self.blockhash),
            'version': self.version_int,
            'prev_block': to_hexstring(self.prev_block),
            'merkle_root': to_hexstring(self.merkle_root),
            'timestamp': self.timestamp,
            'bits': self.bits_int,
            'nonce': self.nonce_int,
            'target': self.target_hex,
            'difficulty': self.difficulty,
            'n_transactions': len(self.transactions),
        }

    @property
    def target(self):
        exponent = self.bits[0]
        coefficient = struct.unpack('>L', b'\x00' + self.bits[1:])[0]
        return coefficient * 256 ** (exponent - 3)

    @property
    def target_hex(self):
        return hex(self.target)[2:].zfill(64)

    @property
    def difficulty(self):
        difficulty = 0xffff * 256 ** (0x1d - 3) / self.target
        return 0xffff001d if difficulty < 0xffff001d else difficulty
