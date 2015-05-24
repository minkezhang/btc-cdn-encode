import BTCCDN_op_return

import os
import binascii
import struct

from bitcoin.rpc import Proxy as btc_proxy
from bitcoin.wallet import P2PKHBitcoinAddress as btc_address

LEN_HEAD = 1
VERSION = 0

class BTCCDNCommand(object):
	global VERSION
	COMMAND = {
		'MSG' : 32,
		'FILESTART' : 33,
		'FILETERM' : 34,
		'TERMACCT' : 1,
	}
	v = VERSION

	##
	# CMD is numerical input
	# payload is a hex-encoded string
	##
	def __init__(self, cmd, payload, aux=None):
		self._c = cmd
		self._p = payload
		if not aux:
			aux = []
		self._a = aux

	@property
	def aux(self):
		return self._a

	@property
	def command(self):
		for k, v in self.COMMAND:
			if self._c == v:
				return k

	@property
	def data(self):
		body = ''.join([ struct.pack(f, d) for (f, d) in self.aux ]) + self._p
		return self.header + body

	# return the command header as a hex string
	@property
	def header(self):
		return struct.pack('>B', self.v << 5 | self._c)
		

class AddrLog(object):
	@staticmethod
	def _counter_log_name(dest):
		return '_' + dest + '.counter'

	@staticmethod
	def _verbose_log_name(dest):
		return '_' + dest + '.log'

	@staticmethod
	def delete(dest):
		os.remove(AddrLog._counter_log_name(dest))

	# FAST : if we should check the counter log after every tx
	# VERBOSE : if a { TXID : OP_RETURN DATA } log should be kept
	def __init__(self, src, dest, verbose=False, fast=False):
		self._d = dest
		self._s = src
		self._p = btc_proxy()
		# populated next AddrLog in case self.COUNTER overflows
		self._n = None

		# if log file does not exist, create it, get count
		self._c = 0
		if not os.path.isfile(self.counter_log_name):
			with open(self.counter_log_name, 'w') as fp:
				fp.write(str(0))
		with open(self.counter_log_name, 'r') as fp:
			self._c = int(fp.readline())

		# initialize the verbose log
		if not os.path.isfile(self.verbose_log_name):
			with open(self.verbose_log_name, 'w'):
				pass

		self._f = fast
		self._v = verbose

	@property
	def verbose(self):
		return self._v

	@property
	def fast(self):
		return self._f

	@property
	def counter_log_name(self):
		return AddrLog._counter_log_name(self.dest)

	@property
	def verbose_log_name(self):
		return AddrLog._verbose_log_name(self.dest)

	@property
	def proxy(self):
		return self._p

	@property
	def next(self):
		return self._n

	# money from which BTC is drawn SRC = '' is allowed
	@property
	def src(self):
		return self._s

	# where messages will be sent
	@property
	def dest(self):
		return self._d

	@property
	def count(self):
		return self._c

	@count.setter
	def count(self, v):
		self._c = v
		if not self.fast:
			self.update()

	def update(self):
		with open(self.counter_log_name, 'w') as fp:
			fp.write(str(self.count))

	def write(self, data):
		with open(self.verbose_log_name, 'a') as fp:
			fp.write(data + '\n')
		

	# return how much spending potential the current ADDRESS has
	@property
	def funds(self):
		candidates = self.proxy.listunspent()
		if self.src != '':
			candidates = filter(lambda x: x['address'] == btc_address(self.src), candidates)
		return sum([ x['amount'] for x in candidates ])

	# sends hex-encoded data to destination address; if final = True, terminate this account
	def send(self, first, last, data):
		c = BTCCDNCommand.COMMAND['MSG']
		if first:
			c |= BTCCDNCommand.COMMAND['FILESTART']
		if last:
			c |= BTCCDNCommand.COMMAND['FILETERM']
		d = BTCCDNCommand(c, data, [ ('>L', self.count) ]).data
		txid = BTCCDN_op_return.OPReturnTx(self.src, self.dest, d).send()
		if self.verbose:
			self.write('\t'.join([ txid, binascii.b2a_hex(d) ]))
		if True: # self.count == 0xffffffff:
			_n = self.proxy.getnewaddress()
			self._n = AddrLog(self.src, str(_n), self.fast)
			AddrLog.delete(self.dest)
			self.term(self.next)
		else:
			self.count += 1
			# update file
			if last:
				self.update()
		return txid

	def term(self, next=''):
		d = BTCCDNCommand(BTCCDNCommand.COMMAND['TERMACCT'], self.next.dest).data
		txid = BTCCDN_op_return.OPReturnTx(self.src, self.dest, d).send()
		if self.verbose:
			self.write('\t'.join([ txid, binascii.b2a_hex(d) ]))
		return txid

"""
class FileBase(object):
	def __init__(self, name):
		self._fn = name

	@property
	def name(self):
		return self._fn

	# returns the size of the file in bytes
	@property
	def size(self):
		return os.stat(self.name).st_size

	@property
	def data(self):
		return ''

	# sends self to the target address dest, with any leftover funds going to address change
	# throws NoFunds exception if insufficient funds
	# returns first txid of the transaction
	def send(self, change, dest):
		return AddrLog(change).send(dest, self.data)
"""
