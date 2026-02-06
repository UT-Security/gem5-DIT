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

#ifndef __CPU_O3_LVP_HH__
#define __CPU_O3_LVP_HH__

#include <deque>
#include <vector>

#include "base/sat_counter.hh"
#include "base/statistics.hh"
#include "base/types.hh"
#include "cpu/inst_seq.hh"
#include "cpu/o3/limits.hh"
#include "params/LoadValuePredictor.hh"
#include "sim/sim_object.hh"

namespace gem5
{

namespace o3
{

/** Entry in the LVP prediction table, indexed by load PC. */
struct LVPEntry
{
    Addr tag = 0;
    RegVal value = 0;
    SatCounter8 confidence;
    bool valid = false;

    LVPEntry() : confidence(3, 0) {}
};

/** History entry tracking an in-flight value prediction. */
struct LVPHistory
{
    InstSeqNum seqNum = 0;
    Addr pc = 0;
    ThreadID tid = 0;
    RegVal predictedValue = 0;
    bool predicted = false;
};

/**
 * Load Value Predictor.
 *
 * Implements a last-value predictor that predicts load results based on
 * the load's PC. Each table entry stores the last committed value and a
 * saturating confidence counter. Predictions are only made when confidence
 * meets a configurable threshold.
 *
 * Integration points:
 *  - Predict at dispatch (IEW::dispatchInsts)
 *  - Validate at writeback (IEW::writebackInsts)
 *  - Train at commit (Commit::commitHead)
 */
class LoadValuePredictor : public SimObject
{
  public:
    PARAMS(LoadValuePredictor);

    LoadValuePredictor(const Params &p);

    /**
     * Look up the prediction table for a load PC.
     * @param pc The load instruction's PC.
     * @param tid Thread ID.
     * @param value Output: the predicted value if confident.
     * @return true if a confident prediction was made.
     */
    bool predict(Addr pc, ThreadID tid, RegVal &value);

    /**
     * Validate an in-flight prediction against the actual load value.
     * @param seqNum The instruction's sequence number.
     * @param actualValue The actual value from the memory system.
     * @return true if the prediction was correct.
     */
    bool validate(InstSeqNum seqNum, RegVal actualValue);

    /**
     * Remove history entries for squashed instructions.
     * Removes all entries with seqNum > squashedSeqNum for the given thread.
     * @param squashedSeqNum Sequence number of the squash point.
     * @param tid Thread ID.
     */
    void squash(InstSeqNum squashedSeqNum, ThreadID tid);

    /**
     * Remove a committed history entry.
     * @param seqNum The committed instruction's sequence number.
     * @param tid Thread ID.
     */
    void commitEntry(InstSeqNum seqNum, ThreadID tid);

    /**
     * Update the prediction table with an actual committed load value.
     * Called at commit time to train the predictor.
     * @param pc The load instruction's PC.
     * @param value The actual committed value.
     */
    void update(Addr pc, RegVal value);

    /** Add a history entry for an in-flight prediction. */
    void addHistory(const LVPHistory &entry);

    /** Check if the predictor is enabled. */
    bool isEnabled() const { return enabled; }

  private:
    /** Compute table index from PC. */
    unsigned getIndex(Addr pc) const;

    /** Compute tag from PC. */
    Addr getTag(Addr pc) const;

    /** The prediction table. */
    std::vector<LVPEntry> table;

    /** Number of entries in the table. */
    unsigned tableSize;

    /** Mask for indexing into the table. */
    unsigned indexMask;

    /** Minimum confidence to issue a prediction. */
    unsigned confidenceThreshold;

    /** Number of bits for the confidence counter. */
    unsigned confidenceBits;

    /** Whether the predictor is enabled. */
    bool enabled;

    /** Per-thread history of in-flight predictions. */
    std::deque<LVPHistory> history[MaxThreads];

    struct LVPStats : public statistics::Group
    {
        LVPStats(LoadValuePredictor *lvp);

        statistics::Scalar predictions;
        statistics::Scalar predCorrect;
        statistics::Scalar predIncorrect;
        statistics::Scalar predNotConfident;
        statistics::Scalar squashes;
        statistics::Formula accuracy;
        statistics::Formula coverage;
    } stats;
};

} // namespace o3
} // namespace gem5

#endif // __CPU_O3_LVP_HH__
