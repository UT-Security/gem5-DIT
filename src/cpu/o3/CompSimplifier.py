from m5.params import *
from m5.SimObject import SimObject


class CompSimplifier(SimObject):
    type = "CompSimplifier"
    cxx_class = "gem5::o3::CompSimplifier"
    cxx_header = "cpu/o3/comp_simplifier.hh"

    enabled = Param.Bool(False, "Enable computation simplification "
                         "for trivial IntMult/IntDiv operations")
