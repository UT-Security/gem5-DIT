from m5.params import *
from m5.SimObject import SimObject


class LoadValuePredictor(SimObject):
    type = "LoadValuePredictor"
    cxx_class = "gem5::o3::LoadValuePredictor"
    cxx_header = "cpu/o3/lvp.hh"

    tableSize = Param.Unsigned(4096, "Number of entries in the LVP table "
                               "(must be a power of 2)")
    confidenceThreshold = Param.Unsigned(7, "Minimum confidence counter "
                                         "value required to make a prediction")
    confidenceBits = Param.Unsigned(3, "Number of bits for the saturating "
                                    "confidence counter")
    enabled = Param.Bool(False, "Enable load value prediction")
