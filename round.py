#
# round.py
#
# By Ross Ridge
# Public Domain
#
# Simple rounding functions.
#

_SCCS_ID = "@(#) mysc round.py 1.3 07/04/17 02:10:27\n"

def div_round_up(a, b):
	return (a + b - 1) / b

def round_up(a, b):
	return (a + b - 1) / b * b

def round_down(a, b):
	return a / b * b


