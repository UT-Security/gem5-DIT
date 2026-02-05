# Copyright (c) 2023 The University of Edinburgh
# Copyright (c) 2025 Technical University of Munich
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

"""
Fetch directed instruction prefetch (FDP) example with SimPoint support

This gem5 configuration script creates a simulation setup with a single
O3 CPU model (NeoverseV2) and decoupled front-end. It supports:
1. Simple workload execution with FDP
2. SimPoint checkpoint creation (fast-forward with AtomicSimpleCPU)
3. SimPoint checkpoint restoration and detailed simulation with NeoverseV2

Usage
-----

Basic usage (original behavior):
```
scons build/ARM/gem5.opt
./build/ARM/gem5.opt configs/example/arm/fdp_neoverse_v2.py
```

Taking SimPoint checkpoints:
```
./build/ARM/gem5.opt configs/example/arm/fdp_neoverse_v2.py \
    --binary /path/to/benchmark \
    --simpoint-file /path/to/simpoint.txt \
    --weight-file /path/to/weight.txt \
    --simpoint-interval 1000000 \
    --take-checkpoint ./m5out/checkpoints
```

Restoring from SimPoint checkpoint:
```
./build/ARM/gem5.opt configs/example/arm/fdp_neoverse_v2.py \
    --binary /path/to/benchmark \
    --simpoint-file /path/to/simpoint.txt \
    --weight-file /path/to/weight.txt \
    --simpoint-interval 1000000 \
    --warmup-interval 100000 \
    --checkpoint-dir ./m5out/checkpoints \
    --restore-simpoint 0
```
"""

import argparse
from pathlib import Path

import m5
from m5.util import addToPath

m5.util.addToPath("../..")

from common.cores.arm import neoverse_v2

from m5.objects import (
    TAGE_SC_L_64KB,
    BranchPredictor,
    FetchDirectedPrefetcher,
    L2XBar,
    MultiPrefetcher,
    SimpleBTB,
    TaggedPrefetcher,
)

from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.boards.mem_mode import MemMode
from gem5.components.cachehierarchies.classic.caches.mmu_cache import MMUCache
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import (
    PrivateL1PrivateL2CacheHierarchy,
)
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.base_cpu_core import BaseCPUCore
from gem5.components.processors.base_cpu_processor import BaseCPUProcessor
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_core import SimpleCore
from gem5.components.processors.switchable_processor import SwitchableProcessor
from gem5.isas import ISA
from gem5.resources.resource import (
    BinaryResource,
    SimpointDirectoryResource,
    obtain_resource,
)
from gem5.simulate.exit_event import ExitEvent
from gem5.simulate.simulator import Simulator
from gem5.utils.override import overrides
from gem5.utils.requires import requires

workloads = {
    "hello": "arm-hello64-static",
}


parser = argparse.ArgumentParser(
    description="An example configuration script to run FDP."
)


parser.add_argument(
    "--workload",
    type=str,
    default="hello",
    help="The workload to simulate.",
    choices=workloads.keys(),
)

parser.add_argument(
    "--disable-fdp",
    action="store_true",
    help="Disable FDP to evaluate baseline performance.",
)

parser.add_argument(
    "--binary",
    type=str,
    default=None,
    help="Path to custom binary (overrides --workload).",
)

parser.add_argument(
    "--arguments",
    type=str,
    default="",
    help='Arguments to pass to the binary (e.g., --arguments "-I./lib input.txt 100").',
)

parser.add_argument(
    "--simpoint-file",
    type=str,
    default=None,
    help="Path to simpoint.txt file with SimPoint indices.",
)

parser.add_argument(
    "--weight-file",
    type=str,
    default=None,
    help="Path to weight.txt file with SimPoint weights.",
)

parser.add_argument(
    "--simpoint-interval",
    type=int,
    default=None,
    help="SimPoint interval in instructions.",
)

parser.add_argument(
    "--warmup-interval",
    type=int,
    default=0,
    help="Warmup instructions before each SimPoint.",
)

parser.add_argument(
    "--checkpoint-dir",
    type=str,
    default=None,
    help="Directory containing SimPoint checkpoints to restore from.",
)

parser.add_argument(
    "--take-checkpoint",
    type=str,
    default=None,
    help="Directory to save SimPoint checkpoints to.",
)

parser.add_argument(
    "--restore-simpoint",
    type=int,
    default=0,
    help="Which SimPoint index to restore (0, 1, 2, etc.).",
)

args = parser.parse_args()


requires(isa_required=ISA.ARM)

# We use a single channel DDR3_1600 memory system
memory = SingleChannelDDR3_1600(size="3GiB")


# 1. SimPoint-aware Switchable Processor --------------------------------
# A custom processor that switches between AtomicSimpleCPU (for fast-forward)
# and NeoverseV2 O3 CPU (for detailed simulation).


class FDPSwitchableProcessor(SwitchableProcessor):
    """
    A switchable processor that uses AtomicSimpleCPU for fast-forwarding
    and NeoverseV2 O3 CPU for detailed simulation with FDP support.
    """

    def __init__(self, num_cores: int = 1, disable_fdp: bool = False):
        self._start_key = "start"
        self._switch_key = "switch"
        self._current_is_start = True
        self._disable_fdp = disable_fdp

        # Atomic cores for fast-forward
        start_cores = [
            SimpleCore(cpu_type=CPUTypes.ATOMIC, core_id=i, isa=ISA.ARM)
            for i in range(num_cores)
        ]

        # NeoverseV2 cores for detailed simulation
        switch_cores = []
        for i in range(num_cores):
            neoverse_cpu = neoverse_v2.NeoverseV2()
            neoverse_cpu.cpu_id = i
            neoverse_cpu.decoupledFrontEnd = not disable_fdp
            switch_cores.append(BaseCPUCore(neoverse_cpu, isa=ISA.ARM))

        self._detailed_cores = switch_cores

        super().__init__(
            switchable_cores={
                self._start_key: start_cores,
                self._switch_key: switch_cores,
            },
            starting_cores=self._start_key,
        )

    def get_detailed_cores(self):
        """Returns the NeoverseV2 cores for FDP registration."""
        return self._detailed_cores

    @overrides(SwitchableProcessor)
    def incorporate_processor(self, board: AbstractBoard) -> None:
        super().incorporate_processor(board=board)
        # Start with atomic memory mode for fast-forward
        board.set_mem_mode(MemMode.ATOMIC)

    def switch(self):
        """Switches between start (atomic) and switch (detailed) cores."""
        if self._current_is_start:
            self.switch_to_processor(self._switch_key)
            # After switching to detailed CPU, update memory mode to timing
            self._board.set_mem_mode(MemMode.TIMING)
        else:
            self.switch_to_processor(self._start_key)
            self._board.set_mem_mode(MemMode.ATOMIC)
        self._current_is_start = not self._current_is_start


# 2. Instruction prefetcher ---------------------------------------------
# The decoupled front-end is only the first part.
# Now we also need the instruction prefetcher which listens to the
# insertions into the fetch target queue (FTQ) to issue prefetches.


class CacheHierarchy(PrivateL1PrivateL2CacheHierarchy):
    def __init__(self, disable_fdp: bool = False):
        super().__init__("", "", "")
        self._disable_fdp = disable_fdp
        self._detailed_cores = None

    def set_detailed_cores(self, cores):
        """Set the cores to register FDP prefetcher with (for switchable processor)."""
        self._detailed_cores = cores

    def incorporate_cache(self, board: AbstractBoard) -> None:
        board.connect_system_port(self.membus.cpu_side_ports)

        for _, port in board.get_memory().get_mem_ports():
            self.membus.mem_side_ports = port

        self.l1icaches = [
            neoverse_v2.L1I()
            for i in range(board.get_processor().get_num_cores())
        ]

        # Add the prefetchers to the L1I caches and register the MMU.
        for i in range(board.get_processor().get_num_cores()):
            # Use detailed cores if set (switchable mode), else current cores
            if self._detailed_cores:
                cpu = self._detailed_cores[i].core
            else:
                cpu = board.get_processor().cores[i].core

            self.l1icaches[i].prefetcher = MultiPrefetcher()
            if not self._disable_fdp:
                pf = FetchDirectedPrefetcher(
                    use_virtual_addresses=True, cpu=cpu
                )
                # Optionally register the cache to prefetch into to enable
                # cache snooping
                pf.registerCache(self.l1icaches[i])
                self.l1icaches[i].prefetcher.prefetchers.append(pf)

            self.l1icaches[i].prefetcher.prefetchers.append(
                TaggedPrefetcher(use_virtual_addresses=True)
            )

            for pf in self.l1icaches[i].prefetcher.prefetchers:
                pf.registerMMU(cpu.mmu)

        self.l1dcaches = [
            neoverse_v2.L1D()
            for i in range(board.get_processor().get_num_cores())
        ]
        self.l2buses = [
            L2XBar() for i in range(board.get_processor().get_num_cores())
        ]
        self.l2caches = [
            neoverse_v2.L2()
            for i in range(board.get_processor().get_num_cores())
        ]
        self.mmucaches = [
            MMUCache(size="8KiB")
            for _ in range(board.get_processor().get_num_cores())
        ]

        self.mmubuses = [
            L2XBar(width=64)
            for i in range(board.get_processor().get_num_cores())
        ]

        if board.has_coherent_io():
            self._setup_io_cache(board)

        for i, cpu in enumerate(board.get_processor().get_cores()):

            cpu.connect_icache(self.l1icaches[i].cpu_side)
            self.l1icaches[i].mem_side = self.l2buses[i].cpu_side_ports

            cpu.connect_dcache(self.l1dcaches[i].cpu_side)
            self.l1dcaches[i].mem_side = self.l2buses[i].cpu_side_ports

            self.mmucaches[i].mem_side = self.l2buses[i].cpu_side_ports

            self.mmubuses[i].mem_side_ports = self.mmucaches[i].cpu_side
            self.l2buses[i].mem_side_ports = self.l2caches[i].cpu_side

            self.membus.cpu_side_ports = self.l2caches[i].mem_side

            cpu.connect_walker_ports(
                self.mmubuses[i].cpu_side_ports,
                self.mmubuses[i].cpu_side_ports,
            )

            cpu.connect_interrupt()


# Determine if we're using SimPoint mode
use_simpoint_mode = args.simpoint_file is not None and args.weight_file is not None

# Create cache hierarchy
cache_hierarchy = CacheHierarchy(disable_fdp=args.disable_fdp)


# 3. Decoupled front-end ------------------------------------------------
# Next setup the decoupled front-end. Its implemented in the O3 core.
# Create the processor with one core

if use_simpoint_mode:
    # SimPoint mode: use switchable processor for fast-forward + detailed
    processor = FDPSwitchableProcessor(num_cores=1, disable_fdp=args.disable_fdp)
    # Register detailed cores with cache hierarchy for FDP prefetcher
    cache_hierarchy.set_detailed_cores(processor.get_detailed_cores())
    print(
        f"SimPoint mode: AtomicSimpleCPU (fast-forward) -> NeoverseV2 (detailed) "
        f"FDP {'disabled' if args.disable_fdp else 'enabled'}"
    )
else:
    # Original mode: direct NeoverseV2
    processor = BaseCPUProcessor(
        cores=[BaseCPUCore(neoverse_v2.NeoverseV2(), isa=ISA.ARM)]
    )

    for core in processor.cores:
        cpu = core.core
        # The `decoupledFrontEnd` parameter enables the decoupled front-end.
        # Disable it to get the baseline.
        if args.disable_fdp:
            cpu.decoupledFrontEnd = False
        else:
            cpu.decoupledFrontEnd = True

    print(
        f"Running {args.workload} on NeoverseV2 "
        f"FDP {'disabled' if args.disable_fdp else 'enabled'}"
    )


# The gem5 library simple board which can be used to run simple SE-mode
# simulations.
board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

# Determine binary to use
if args.binary:
    binary = BinaryResource(local_path=args.binary)
else:
    binary = obtain_resource(workloads[args.workload])

# Parse arguments string into list
binary_args = args.arguments.split() if args.arguments else []

# Set workload based on mode
if use_simpoint_mode:
    # Create SimPoint resource from files
    simpoint_dir = Path(args.simpoint_file).parent
    simpoint = SimpointDirectoryResource(
        local_path=str(simpoint_dir),
        simpoint_file=Path(args.simpoint_file).name,
        weight_file=Path(args.weight_file).name,
        simpoint_interval=args.simpoint_interval,
        warmup_interval=args.warmup_interval,
    )

    if args.checkpoint_dir:
        # Restore from specific SimPoint checkpoint
        cpt_path = Path(args.checkpoint_dir) / f"cpt.SimPoint{args.restore_simpoint}"
        print(f"Restoring from checkpoint: {cpt_path}")
        board.set_se_simpoint_workload(
            binary=binary,
            arguments=binary_args,
            simpoint=simpoint,
            checkpoint=cpt_path,
        )
    else:
        board.set_se_simpoint_workload(
            binary=binary,
            arguments=binary_args,
            simpoint=simpoint,
        )
else:
    # Original mode: simple binary workload
    board.set_se_binary_workload(binary, arguments=binary_args)


# Exit event handlers for SimPoint mode
def simpoint_checkpoint_handler(checkpoint_dir: Path):
    """Generator to save checkpoints at each SimPoint."""
    idx = 0
    while True:
        cpt_path = checkpoint_dir / f"cpt.SimPoint{idx}"
        m5.checkpoint(str(cpt_path))
        print(f"Saved checkpoint to {cpt_path}")
        idx += 1
        yield False  # Continue simulation


# Create simulator with appropriate exit event handlers
if use_simpoint_mode:
    if args.take_checkpoint:
        # Taking checkpoints: use SIMPOINT_BEGIN handler
        checkpoint_path = Path(args.take_checkpoint)
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        simulator = Simulator(
            board=board,
            on_exit_event={
                ExitEvent.SIMPOINT_BEGIN: simpoint_checkpoint_handler(checkpoint_path)
            },
        )
    elif args.checkpoint_dir:
        # Restoring from checkpoint: use MAX_INSTS handler for warmup/measurement
        # Define the generator here so it can reference simulator via closure
        def simpoint_restore_handler():
            """Generator to handle warmup -> measurement phases after checkpoint restore."""
            warmed_up = False
            while True:
                if warmed_up:
                    print("SimPoint interval complete")
                    m5.stats.dump()
                    yield True  # Exit after measurement
                else:
                    print("Warmup complete, switching to NeoverseV2 for measurement")
                    warmed_up = True
                    # Switch to detailed CPU
                    simulator.switch_processor()
                    m5.stats.reset()
                    # Schedule measurement interval
                    simulator.schedule_max_insts(
                        board.get_simpoint().get_simpoint_interval()
                    )
                    yield False

        simulator = Simulator(
            board=board,
            on_exit_event={ExitEvent.MAX_INSTS: simpoint_restore_handler()},
        )
        # Schedule warmup exit
        warmup_insts = board.get_simpoint().get_warmup_list()[args.restore_simpoint]
        print(f"Scheduling warmup for {warmup_insts} instructions")
        simulator.schedule_max_insts(warmup_insts)
    else:
        # Just running with SimPoints, no checkpointing
        simulator = Simulator(board=board)
else:
    # Original mode
    simulator = Simulator(board=board)

simulator.run()

print("Simulation done.")
