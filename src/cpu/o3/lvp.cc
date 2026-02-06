/*
 * Copyright (c) 2025 All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "cpu/o3/lvp.hh"

#include <algorithm>

#include "base/intmath.hh"
#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/LVP.hh"

namespace gem5
{

namespace o3
{

LoadValuePredictor::LoadValuePredictor(const Params &p)
    : SimObject(p),
      tableSize(p.tableSize),
      indexMask(p.tableSize - 1),
      confidenceThreshold(p.confidenceThreshold),
      confidenceBits(p.confidenceBits),
      enabled(p.enabled),
      stats(this)
{
    fatal_if(!isPowerOf2(tableSize),
             "LVP table size must be a power of 2, got %d", tableSize);

    table.resize(tableSize);
}

unsigned
LoadValuePredictor::getIndex(Addr pc) const
{
    // Shift right by 2 to skip the lowest bits (instruction alignment).
    return (pc >> 2) & indexMask;
}

Addr
LoadValuePredictor::getTag(Addr pc) const
{
    return pc;
}

bool
LoadValuePredictor::predict(Addr pc, ThreadID tid, RegVal &value)
{
    if (!enabled)
        return false;

    unsigned idx = getIndex(pc);
    LVPEntry &entry = table[idx];

    if (entry.valid && entry.tag == getTag(pc) &&
        entry.confidence >= confidenceThreshold) {
        value = entry.value;
        ++stats.predictions;
        DPRINTF(LVP, "Predict [PC:%#x] -> value %#x (confidence %d)\n",
                pc, value, (unsigned)entry.confidence);
        return true;
    }

    ++stats.predNotConfident;
    DPRINTF(LVP, "No prediction for [PC:%#x] (valid=%d, conf=%d)\n",
            pc, entry.valid, entry.valid ? (unsigned)entry.confidence : 0);
    return false;
}

bool
LoadValuePredictor::validate(InstSeqNum seqNum, RegVal actualValue)
{
    // Find the history entry for this instruction.
    for (auto &threadHist : history) {
        for (auto &h : threadHist) {
            if (h.seqNum == seqNum && h.predicted) {
                bool correct = (h.predictedValue == actualValue);
                if (correct) {
                    ++stats.predCorrect;
                    DPRINTF(LVP, "Validated correct [sn:%llu] "
                            "predicted=%#x actual=%#x\n",
                            seqNum, h.predictedValue, actualValue);
                } else {
                    ++stats.predIncorrect;
                    ++stats.squashes;
                    DPRINTF(LVP, "Validated INCORRECT [sn:%llu] "
                            "predicted=%#x actual=%#x\n",
                            seqNum, h.predictedValue, actualValue);
                }
                return correct;
            }
        }
    }

    // No history found — instruction may have been squashed already.
    return true;
}

void
LoadValuePredictor::squash(InstSeqNum squashedSeqNum, ThreadID tid)
{
    auto &hist = history[tid];
    while (!hist.empty() && hist.back().seqNum > squashedSeqNum) {
        DPRINTF(LVP, "Squashing history [sn:%llu] [PC:%#x]\n",
                hist.back().seqNum, hist.back().pc);
        hist.pop_back();
    }
}

void
LoadValuePredictor::commitEntry(InstSeqNum seqNum, ThreadID tid)
{
    auto &hist = history[tid];
    // History entries should be committed in order (oldest first).
    if (!hist.empty() && hist.front().seqNum == seqNum) {
        hist.pop_front();
    }
}

void
LoadValuePredictor::update(Addr pc, RegVal value)
{
    unsigned idx = getIndex(pc);
    LVPEntry &entry = table[idx];

    if (entry.valid && entry.tag == getTag(pc)) {
        if (entry.value == value) {
            // Same value — increase confidence.
            entry.confidence++;
            DPRINTF(LVP, "Update [PC:%#x] same value %#x, confidence -> %d\n",
                    pc, value, (unsigned)entry.confidence);
        } else {
            // Different value — reset confidence and store new value.
            entry.value = value;
            entry.confidence.reset();
            DPRINTF(LVP, "Update [PC:%#x] new value %#x, confidence reset\n",
                    pc, value);
        }
    } else {
        // New entry or tag mismatch — install new entry.
        entry.valid = true;
        entry.tag = getTag(pc);
        entry.value = value;
        entry.confidence.reset();
        DPRINTF(LVP, "Install [PC:%#x] value %#x\n", pc, value);
    }
}

void
LoadValuePredictor::addHistory(const LVPHistory &entry)
{
    history[entry.tid].push_back(entry);
}

LoadValuePredictor::LVPStats::LVPStats(LoadValuePredictor *lvp)
    : statistics::Group(lvp),
      ADD_STAT(predictions, statistics::units::Count::get(),
               "Number of confident load value predictions made"),
      ADD_STAT(predCorrect, statistics::units::Count::get(),
               "Number of correct load value predictions"),
      ADD_STAT(predIncorrect, statistics::units::Count::get(),
               "Number of incorrect load value predictions (mispredictions)"),
      ADD_STAT(predNotConfident, statistics::units::Count::get(),
               "Number of loads not predicted due to low confidence"),
      ADD_STAT(squashes, statistics::units::Count::get(),
               "Number of pipeline squashes due to value misprediction"),
      ADD_STAT(accuracy, statistics::units::Ratio::get(),
               "Load value prediction accuracy",
               predCorrect / predictions),
      ADD_STAT(coverage, statistics::units::Ratio::get(),
               "Load value prediction coverage",
               predictions / (predictions + predNotConfident))
{
    accuracy.precision(6);
    coverage.precision(6);
}

} // namespace o3
} // namespace gem5
