# The gem5 Simulator

This is the repository for the gem5 simulator. It contains the full source code
for the simulator and all tests and regressions.

The gem5 simulator is a modular platform for computer-system architecture
research, encompassing system-level architecture as well as processor
microarchitecture. It is primarily used to evaluate new hardware designs,
system software changes, and compile-time and run-time system optimizations.

The main website can be found at <http://www.gem5.org>.

## Getting started

Step 1. `scons build/ARM/gem5.opt -j16`

Step 2. Acquire `spec2006_simpoints.tar` file and extract to `gem5/` root

### Example on how to take checkpoints for Spec2006 

Step 1. `cd spec2006_simpoints/binaries/400.perlbench`

Step 2. `../../../build/ARM/gem5.opt ../../../configs/example/arm/fdp_neoverse_v2.py --binary ./perlbench_base.aarch64-gcc-nn --arguments '-I./lib checkspam.pl 2500 5 25 11 150 1 1 1 1' --simpoint-file ../../simpoints/400.perlbench/simpoints_1.txt --weight-file ../../simpoints/400.perlbench/weights_1.txt --simpoint-interval 50000000 --take-checkpoint ./m5out/checkpoints`

Modify arguments as needed

### Example on how to run any binary

`./build/ARM/gem5.opt ./configs/example/arm/fdp_neoverse_v2_binary.py --binary 'any_binary' --arguments 'arg0 arg1 arg2'`

### Development

1. Operate on seperate branch other than master
2. make sure you add --no-verify at end of commit (Ex. `git commit -m "example" --no-verify`)
3. git push branch_name