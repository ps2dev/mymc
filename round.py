#
# round.py
#
# By Ross Ridge
# Public Domain
#
# Simple rounding functions.
#

_SCCS_ID = "@(#) mymc round.py 1.4 23/07/06 02:44:14\n"

def div_round_up(a, b):
	return int((a + b - 1) / b)

def round_up(a, b):
	return int((a + b - 1) / b * b)

def round_down(a, b):
	return int(a / b * b)


